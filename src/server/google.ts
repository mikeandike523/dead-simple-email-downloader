import { fetchWithTimeout } from "@/utils/fetchWithTimeout";
import summarizeResponse, { JsonValue } from "@/utils/summarizeResponse";
import { PoolConnection } from "mysql2/promise";
import logger from "./logger";
import {
  dateToSqlUtcTimestamp,
  sqlUtcTimestampToDate,
} from "../utils/time-and-date";
import { dbExec, dbQuery, withTransaction } from "./db";

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
type Primitive = string | number | boolean | null | undefined;
type UrlParams = Record<string, Primitive | Primitive[]>;

async function getNewAccessToken(
  openidSub: string,
  provider: string,
  product: string,
  txn?: PoolConnection
) {
  await withTransaction(
    async (txn) => {
      logger.info(`Getting new Google access token for user ${openidSub} (${provider}/${product})`);

      const rows = await dbQuery(
        `SELECT refresh_token FROM oauth_tokens WHERE openid_sub = ? AND provider = ?`,
        [openidSub, provider],
        txn
      );
      if (rows.length === 0) {
        throw new Error(`No refresh token found for user ${openidSub} / provider ${provider}`);
      }
      const refreshToken = rows[0].refresh_token;

      const body = new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: process.env.GCLOUD_CLIENT_ID!,
        client_secret: process.env.GCLOUD_CLIENT_SECRET!,
      });

      const tokenResponse = await summarizeResponse(
        await fetchWithTimeout(process.env.GCLOUD_TOKEN_URI!, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
          timeoutMs: 5000,
        })
      );

      if (!tokenResponse.ok) {
        throw new Error(
          `Failed to get new Google access token (status ${tokenResponse.status}): ${tokenResponse.text}`
        );
      }

      const td = tokenResponse.data as {
        access_token: string;
        expires_in: number;
        token_type: string;
        scope?: string;
      };

      // Google does not rotate refresh tokens on refresh — no update needed.
      const expiresAt = dateToSqlUtcTimestamp(new Date(Date.now() + td.expires_in * 1000));

      await dbExec(
        `
INSERT INTO access_tokens (openid_sub, provider, product, access_token, expires_at) VALUES (?,?,?,?,?)
ON DUPLICATE KEY UPDATE access_token = VALUES(access_token), expires_at = VALUES(expires_at)
`,
        [openidSub, provider, product, td.access_token, expiresAt],
        txn
      );
    },
    { connection: txn }
  );
}

async function checkAccessToken(
  openidSub: string,
  provider: string,
  product: string,
  txn?: PoolConnection
) {
  const rows = await dbQuery(
    `SELECT access_token FROM access_tokens WHERE openid_sub = ? AND provider = ? AND product = ?`,
    [openidSub, provider, product],
    txn
  );
  if (rows.length === 0) return false;

  const accessToken = rows[0].access_token;
  const resp = await summarizeResponse(
    await fetchWithTimeout("https://www.googleapis.com/oauth2/v3/userinfo", {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeoutMs: 5000,
    })
  );

  if (resp.status === 200) return true;
  if (resp.status === 401 || resp.status === 403) return false;
  return false;
}

export async function ensureAccessToken(
  openidSub: string,
  provider = "google",
  product = "gmail",
  minMinutesRemaining = 30,
  txn?: PoolConnection
) {
  await withTransaction(
    async (txn) => {
      const rows = await dbQuery(
        `SELECT access_token, expires_at FROM access_tokens WHERE openid_sub = ? AND provider = ? AND product = ?`,
        [openidSub, provider, product],
        txn
      );

      if (rows.length === 0) {
        return await getNewAccessToken(openidSub, provider, product, txn);
      }

      const expiresAt = sqlUtcTimestampToDate(rows[0].expires_at);
      const remainingMinutes = (expiresAt.getTime() - Date.now()) / 60000;
      if (remainingMinutes <= minMinutesRemaining) {
        return await getNewAccessToken(openidSub, provider, product, txn);
      }

      const isValid = await checkAccessToken(openidSub, provider, product, txn);
      if (!isValid) {
        return await getNewAccessToken(openidSub, provider, product, txn);
      }
    },
    { connection: txn }
  );
}

export async function getCurrentAccessToken(
  openidSub: string,
  provider = "google",
  product = "gmail"
): Promise<string | null> {
  const rows = await dbQuery(
    `SELECT access_token FROM access_tokens WHERE openid_sub = ? AND provider = ? AND product = ?`,
    [openidSub, provider, product]
  );
  if (rows.length === 0) return null;
  return rows[0].access_token;
}

// ---------------------------------------------------------------------------
// Query string helper
// ---------------------------------------------------------------------------

function buildQueryString(params?: UrlParams): string {
  if (!params) return "";
  const usp = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val === null || val === undefined) continue;
    if (Array.isArray(val)) {
      for (const v of val) {
        if (v !== null && v !== undefined) usp.append(key, String(v));
      }
    } else {
      usp.set(key, String(val));
    }
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------------
// Retry helpers (same strategy as msgraph.ts)
// ---------------------------------------------------------------------------

const DEFAULT_MAX_ATTEMPTS = 5;
const BASE_DELAY_MS = 300;
const MAX_BACKOFF_MS = 8_000;
const JITTER_RATIO = 0.2;
const EXPLICIT_JITTER_MAX_MS = 250;
const EXPLICIT_JITTER_RATIO = 0.1;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function getRetryAfterMs(headers: Headers): number | null {
  const ra = headers.get("Retry-After");
  if (ra) {
    const secs = Number(ra);
    if (!Number.isNaN(secs)) return Math.max(0, secs * 1000);
    const date = Date.parse(ra);
    if (!Number.isNaN(date)) return Math.max(0, date - Date.now());
  }
  return null;
}

function isRetriableStatus(status: number): boolean {
  return status === 429 || status === 503;
}

function computeBackoffMs(attempt: number, explicitMs: number | null): number {
  if (explicitMs !== null) {
    const base = Math.max(0, explicitMs);
    const additiveJitter = Math.min(EXPLICIT_JITTER_MAX_MS, base * EXPLICIT_JITTER_RATIO);
    const jitter = additiveJitter > 0 ? Math.random() * additiveJitter : 0;
    return Math.min(MAX_BACKOFF_MS, Math.floor(base + jitter));
  }
  const exp = Math.min(MAX_BACKOFF_MS, BASE_DELAY_MS * 2 ** (attempt - 1));
  const jitter = exp * JITTER_RATIO;
  return Math.floor(Math.max(0, exp - jitter) + Math.random() * jitter * 2);
}

// ---------------------------------------------------------------------------
// callGoogleJSON
// ---------------------------------------------------------------------------

export async function callGoogleJSON<
  T extends JsonValue | undefined | unknown = unknown
>({
  openidSub,
  provider = "google",
  product = "gmail",
  url,
  urlParams,
  method = "GET",
  body,
  minMinutesRemaining = 30,
  timeoutMs,
  silent = false,
  additionalHeaders = {},
}: {
  openidSub: string;
  provider?: string;
  product?: string;
  url: string;
  urlParams?: UrlParams;
  method?: HttpMethod;
  body?: unknown;
  minMinutesRemaining?: number;
  timeoutMs?: number;
  silent?: boolean;
  additionalHeaders?: Record<string, string>;
}) {
  const now =
    typeof performance !== "undefined" ? () => performance.now() : () => Date.now();

  const fullUrl = url + buildQueryString(urlParams);
  const label = new URL(url).pathname;

  const tEnsureStart = now();
  try {
    await ensureAccessToken(openidSub, provider, product, minMinutesRemaining);
  } catch (err) {
    const ms = now() - tEnsureStart;
    if (!silent) logger.info(`[callGoogleJSON] ${method} ${label} | ensure=${ms.toFixed(0)}ms | fetch=skipped | error=${(err as Error)?.message ?? err}`);
    throw err;
  }
  const ensureMs = now() - tEnsureStart;

  const token = await getCurrentAccessToken(openidSub, provider, product);

  const baseHeaders: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    ...additionalHeaders,
  };
  if (body !== undefined && method !== "GET" && method !== "DELETE") {
    baseHeaders["Content-Type"] = "application/json";
  }

  const initBase: RequestInit = { method, headers: baseHeaders };
  if (body !== undefined && method !== "GET" && method !== "DELETE") {
    (initBase as any).body = JSON.stringify(body);
  }

  let attempt = 0;
  for (;;) {
    attempt++;
    const tFetch = now();
    try {
      const res = await fetchWithTimeout(fullUrl, { ...initBase, timeoutMs });
      const fetchMs = now() - tFetch;

      if (!res.ok && isRetriableStatus(res.status) && attempt < DEFAULT_MAX_ATTEMPTS) {
        const delayMs = computeBackoffMs(attempt, getRetryAfterMs(res.headers));
        if (!silent) logger.info(`[callGoogleJSON] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms | status=${res.status} -> retry in ${delayMs}ms (${attempt}/${DEFAULT_MAX_ATTEMPTS})`);
        await sleep(delayMs);
        continue;
      }

      if (!silent) logger.info(`[callGoogleJSON] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms`);
      return await summarizeResponse<T>(res);
    } catch (err) {
      const fetchMs = now() - tFetch;
      if (attempt < DEFAULT_MAX_ATTEMPTS) {
        const delayMs = computeBackoffMs(attempt, null);
        if (!silent) logger.info(`[callGoogleJSON] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms (network error) -> retry in ${delayMs}ms (${attempt}/${DEFAULT_MAX_ATTEMPTS}) | error=${(err as Error)?.message ?? err}`);
        await sleep(delayMs);
        continue;
      }
      if (!silent) logger.info(`[callGoogleJSON] ${method} ${label} | retries exhausted | error=${(err as Error)?.message ?? err}`);
      throw err;
    }
  }
}

// ---------------------------------------------------------------------------
// callGoogleBinary
// ---------------------------------------------------------------------------

export async function callGoogleBinary({
  openidSub,
  provider = "google",
  product = "gmail",
  url,
  urlParams,
  method = "GET",
  minMinutesRemaining = 30,
  timeoutMs,
  silent = false,
  additionalHeaders = {},
}: {
  openidSub: string;
  provider?: string;
  product?: string;
  url: string;
  urlParams?: UrlParams;
  method?: HttpMethod;
  minMinutesRemaining?: number;
  timeoutMs?: number;
  silent?: boolean;
  additionalHeaders?: Record<string, string>;
}): Promise<Response> {
  const now =
    typeof performance !== "undefined" ? () => performance.now() : () => Date.now();

  const fullUrl = url + buildQueryString(urlParams);
  const label = new URL(url).pathname;

  const tEnsureStart = now();
  await ensureAccessToken(openidSub, provider, product, minMinutesRemaining);
  const ensureMs = now() - tEnsureStart;

  const token = await getCurrentAccessToken(openidSub, provider, product);
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...additionalHeaders,
  };

  const initBase: RequestInit = { method, headers };
  let attempt = 0;
  for (;;) {
    attempt++;
    const tFetch = now();
    try {
      const res = await fetchWithTimeout(fullUrl, { ...initBase, timeoutMs });
      const fetchMs = now() - tFetch;

      if (!res.ok && isRetriableStatus(res.status) && attempt < DEFAULT_MAX_ATTEMPTS) {
        const delayMs = computeBackoffMs(attempt, getRetryAfterMs(res.headers));
        if (!silent) logger.info(`[callGoogleBinary] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms | status=${res.status} -> retry in ${delayMs}ms (${attempt}/${DEFAULT_MAX_ATTEMPTS})`);
        await sleep(delayMs);
        continue;
      }

      if (!silent) logger.info(`[callGoogleBinary] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms`);
      return res;
    } catch (err) {
      const fetchMs = now() - tFetch;
      if (attempt < DEFAULT_MAX_ATTEMPTS) {
        const delayMs = computeBackoffMs(attempt, null);
        if (!silent) logger.info(`[callGoogleBinary] ${method} ${label} | ensure=${ensureMs.toFixed(0)}ms | fetch=${fetchMs.toFixed(0)}ms (network error) -> retry in ${delayMs}ms (${attempt}/${DEFAULT_MAX_ATTEMPTS}) | error=${(err as Error)?.message ?? err}`);
        await sleep(delayMs);
        continue;
      }
      if (!silent) logger.info(`[callGoogleBinary] ${method} ${label} | retries exhausted | error=${(err as Error)?.message ?? err}`);
      throw err;
    }
  }
}

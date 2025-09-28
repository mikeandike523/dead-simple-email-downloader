import { dbExec, dbQuery, withTransaction } from "./db";
import {
  dateToSqlUtcTimestamp,
  sqlUtcTimestampToDate,
} from "../utils/time-and-date";
import summarizeResponse, {
  JsonValue,
  ResponseSummary,
} from "@/utils/summarizeResponse";
import { fetchWithTimeout } from "@/utils/fetchWithTimeout";
import { PoolConnection } from "mysql2/promise";

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";
type Primitive = string | number | boolean | null | undefined;
type UrlParams = Record<string, Primitive | Primitive[]>;

/**
 * Calls the microsoft graph token endpoint and gets a new access token
 * and saves in database
 *
 * @param openidSub
 */
async function getNewAccessToken(openidSub: string, txn?: PoolConnection) {
  await withTransaction(
    async (txn) => {
      console.info(`Getting new access token for user ${openidSub}`);

      const refreshTokensResult = await dbQuery(
        `SELECT refresh_token from oauth_tokens WHERE openid_sub = ?`,
        [openidSub],
        txn
      );
      if (refreshTokensResult.length === 0) {
        throw new Error("No refresh token found for this user");
      }
      const refreshToken = refreshTokensResult[0].refresh_token;
      const body = new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: process.env.AZURE_CLIENT_ID!, // required
        // If this is a confidential client (server app), include client_secret:
        ...(process.env.AZURE_CLIENT_SECRET
          ? { client_secret: process.env.AZURE_CLIENT_SECRET }
          : {}),
        // Optional: request the same (or subset) scopes you already had
        // scope: "User.Read Mail.Read"
      });

      const tokenResponse = await summarizeResponse(
        await fetchWithTimeout(
          "https://login.microsoftonline.com/common/oauth2/v2.0/token",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
            body,
            timeoutMs: 5000, // 5 seconds timeout
          }
        )
      );

      if (!tokenResponse.ok) {
        throw new Error(
          `Failed to get new access token (status ${tokenResponse.status}): ${tokenResponse.text}`
        );
      }

      const tokenData = tokenResponse.data;

      if (typeof tokenData !== "object" || tokenData === null) {
        throw new Error("Failed to parse token response as JSON");
      }

      const td = tokenData as {
        token_type: "Bearer";
        access_token: string;
        expires_in: number; // seconds
        scope?: string;
        refresh_token?: string; // may be present (rotation)
      };

      if (td.refresh_token) {
        const execResponse = await dbExec(
          `
UPDATE oauth_tokens SET refresh_token = ? WHERE openid_sub = ?        
        `,
          [td.refresh_token, openidSub],
          txn
        );
        if (execResponse.affectedRows !== 1) {
          throw new Error("Failed to update refresh token in database");
        }
      }

      const accessToken = td.access_token;
      const expiresAt = dateToSqlUtcTimestamp(
        new Date(Date.now() + td.expires_in * 1000)
      );
      await dbExec(
        `
INSERT INTO access_tokens (openid_sub, access_token, expires_at) VALUES (?,?,?)
on DUPLICATE KEY UPDATE access_token = VALUES(access_token), expires_at = VALUES(expires_at)

`,
        [openidSub, accessToken, expiresAt],
        txn
      );
    },
    {
      connection: txn,
    }
  );
}

/**
 *
 * Calls microsoft graph endpoint to see if access token is still valid
 *
 * @param openidSub
 */
async function checkAccessToken(openidSub: string, txn?: PoolConnection) {
  const accessTokensResult = await dbQuery(
    `
        SELECT access_token from access_tokens WHERE openid_sub = ?
            `,
    [openidSub],
    txn
  );

  if (accessTokensResult.length === 0) {
    return false;
  }

  // at this point, we know accessTokens.length === 1 due to unique constraint over openid_sub

  const accessTokenData = accessTokensResult[0];

  const accessToken = accessTokenData.access_token;

  const tokenResponse = await summarizeResponse(
    await fetchWithTimeout("https://graph.microsoft.com/v1.0/me", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
      timeoutMs: 5000, // 5 seconds timeout
    })
  );

  // 3) Simple rule: 200 means OK, 401/403 means not OK
  if (tokenResponse.status === 200) return true;
  if (tokenResponse.status === 401 || tokenResponse.status === 403)
    return false;

  // Any other status: treat as invalid (or log it if you care)
  return false;
}

/**
 *
 * Ensures that the access token stored in the database
 * is fresh for at least `minMinutesRemaining` minutes.
 *
 * @param sub
 * @param minMinutesRemaining
 */
export async function ensureAccessToken(
  openidSub: string,
  minMinutesRemaining = 30,
  txn?: PoolConnection
) {
  await withTransaction(
    async (txn) => {
      const accessTokensResult = await dbQuery(
        `
SELECT access_token, expires_at from access_tokens WHERE openid_sub = ?
    `,
        [openidSub],
        txn
      );

      // If no tokens yet, then we know we need to call getNewAccessToken
      if (accessTokensResult.length === 0) {
        return await getNewAccessToken(openidSub, txn);
      }

      // We know accessTokens.length === 1 due to unique constraint over openid_sub
      const accessTokenData = accessTokensResult[0];
      const expiresAt = sqlUtcTimestampToDate(accessTokenData.expires_at);
      const now = new Date();
      const remainingMinutes = (expiresAt.getTime() - now.getTime()) / 60000;
      // If we don't have enough time left, then we need to call getNewAccessToken
      if (remainingMinutes <= minMinutesRemaining) {
        return await getNewAccessToken(openidSub, txn);
      }

      // At this point, we now need to touch the graph endpoint to make sure the token
      // we have is good, and if not, then we need to call getNewAccessToken
      const isValid = await checkAccessToken(openidSub, txn);
      if (!isValid) {
        return await getNewAccessToken(openidSub, txn);
      }
    },
    { connection: txn }
  );
}

export async function getCurrentAccessToken(
  openidSub: string
): Promise<string | null> {
  const accessTokensResult = await dbQuery(
    `
        SELECT access_token from access_tokens WHERE openid_sub =?
            `,
    [openidSub]
  );

  if (accessTokensResult.length === 0) {
    return null;
  }

  // We know accessTokens.length === 1 due to unique constraint over openid_sub
  const accessTokenData = accessTokensResult[0];
  return accessTokenData.access_token;
}

/**
 * Convert values to strings suitable for query strings.
 */
function toQSValue(v: Primitive): string | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : null;
  // strings pass through
  return String(v);
}

/**
 * Build a Microsoft Graph–friendly query string.
 * - $select/$expand/$orderby arrays are comma-joined (OData style)
 * - other keys are repeated for arrays (foo=a&foo=b)
 * - null/undefined are skipped
 */
export function buildGraphQueryString(params?: UrlParams): string {
  if (!params) return "";
  const usp = new URLSearchParams();

  for (const [rawKey, rawVal] of Object.entries(params)) {
    if (rawVal === null || rawVal === undefined) continue;

    const key = rawKey; // Graph is fine with %24, but leaving as-is is OK; URLSearchParams will encode.
    const isODataList =
      key === "$select" || key === "$expand" || key === "$orderby";

    if (Array.isArray(rawVal)) {
      const vals = rawVal
        .map(toQSValue)
        .filter((s): s is string => s !== null && s.length > 0);

      if (!vals.length) continue;

      if (isODataList) {
        // comma-separated for OData list keys
        usp.set(key, vals.join(","));
      } else {
        // repeat the key
        for (const v of vals) usp.append(key, v);
      }
    } else {
      const v = toQSValue(rawVal);
      if (v === null) continue;
      usp.set(key, v);
    }
  }

  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export async function callGraphJSON<
  T extends JsonValue | undefined | unknown = unknown
>({
  minMinutesRemaining = 30,
  openidSub,
  route,
  method = "GET",
  urlParams,
  body, // optional JSON body for POST/PUT/PATCH-like calls
  version = "v1.0", // or "beta"
  baseUrl = "https://graph.microsoft.com",
  timeoutMs,
  silent = false,
}: {
  minMinutesRemaining?: number;
  openidSub: string;
  route: string; // e.g. "/me/messages" or "me/messages"
  method?: HttpMethod;
  urlParams?: UrlParams;
  body?: unknown;
  version?: "v1.0" | "beta";
  baseUrl?: string;
  timeoutMs?: number; // optional fetch timeout in milliseconds
  silent?: boolean; // if true, suppress console.info logs
}) {
  const now =
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? () => performance.now()
      : () => Date.now();

  const cleanRoute = route.startsWith("/") ? route : `/${route}`;

  // --- ensureAccessToken timing ---
  const tEnsureStart = now();
  try {
    await ensureAccessToken(openidSub, minMinutesRemaining);
  } catch (err) {
    const ensureMs = now() - tEnsureStart;
    if (!silent) {
      console.info(
        `[callGraphJSON] ${method} ${cleanRoute} | ensureAccessToken=${ensureMs.toFixed(
          0
        )}ms | fetch=skipped (token ensure failed) | error=${(err as Error)?.message ?? err}`
      );
    }
    throw err;
  }
  const ensureMs = now() - tEnsureStart;

  const token = await getCurrentAccessToken(openidSub);

  const qs = buildGraphQueryString(urlParams);
  const url = `${baseUrl}/${version}${cleanRoute}${qs}`;

  const init: RequestInit = {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  };

  if (body !== undefined && method !== "GET" && method !== "DELETE") {
    (init.headers as Record<string, string>)["Content-Type"] =
      "application/json";
    init.body = JSON.stringify(body);
  }

  // --- fetch timing ---
  const tFetchStart = now();
  try {
    const res = await fetchWithTimeout(url, { ...init, timeoutMs });
    const fetchMs = now() - tFetchStart;

    if (!silent) {
      console.info(
        `[callGraphJSON] ${method} ${cleanRoute} | ensureAccessToken=${ensureMs.toFixed(
          0
        )}ms | graphFetch=${fetchMs.toFixed(0)}ms`
      );
    }

    return await summarizeResponse<T>(res);
  } catch (err) {
    const fetchMs = now() - tFetchStart;
    if (!silent) {
      console.info(
        `[callGraphJSON] ${method} ${cleanRoute} | ensureAccessToken=${ensureMs.toFixed(
          0
        )}ms | graphFetch=${fetchMs.toFixed(
          0
        )}ms (failed) | error=${(err as Error)?.message ?? err}`
      );
    }
    throw err;
  }
}

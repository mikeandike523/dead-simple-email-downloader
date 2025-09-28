// src/server/auth.ts
import type { NextApiRequest } from "next";
import { jwtVerify, JWTPayload } from "jose";

const enc = (s: string) => new TextEncoder().encode(s);

// Secrets (HS256). Make them long & distinct.
const WEB_SECRET = enc(process.env.WEB_JWT_SECRET!);
const CLI_SECRET = enc(process.env.CLI_JWT_SECRET!);

// Issuer you set when signing
export const ISSUER = "your-app";
// Cookie name you use for the browser session JWT
export const WEB_COOKIE_NAME = "session";

export type AuthAudience = "web" | "cli";
export type AuthUser = {
  sub: string;
  aud: AuthAudience;
  raw?: JWTPayload; // optional: keep full payload for roles/scopes
};

// --- helpers ---
function parseCookie(header: string | undefined, name: string): string | null {
  if (!header) return null;
  const m = header.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

export async function verifyCliToken(token: string): Promise<AuthUser> {
  const { payload } = await jwtVerify(token, CLI_SECRET, {
    issuer: ISSUER,
    audience: "cli",
    clockTolerance: "60s",
  });
  if (!payload.sub) throw new Error("missing sub");
  return { sub: String(payload.sub), aud: "cli", raw: payload };
}

export async function verifyWebToken(token: string): Promise<AuthUser> {
  const { payload } = await jwtVerify(token, WEB_SECRET, {
    issuer: ISSUER,
    audience: "web",
    clockTolerance: "60s",
  });
  if (!payload.sub) throw new Error("missing sub");
  return { sub: String(payload.sub), aud: "web", raw: payload };
}

/**
 * Try header (CLI) first, then cookie (web).
 * Returns null on any verification failure.
 */
export async function getAuth(req: NextApiRequest): Promise<AuthUser | null> {
  // 1) Authorization: Bearer (CLI)
  const auth = req.headers.authorization;
  if (auth?.startsWith("Bearer ")) {
    const token = auth.slice("Bearer ".length).trim();
    try {
      return await verifyCliToken(token);
    } catch {
      return null; // invalid CLI token
    }
  }

  // 2) Cookie (Web)
  const cookieJwt = parseCookie(req.headers.cookie, WEB_COOKIE_NAME);
  if (cookieJwt) {
    try {
      return await verifyWebToken(cookieJwt);
    } catch {
      return null; // invalid web token
    }
  }

  return null;
}

// src/server/auth.ts
import type { NextApiRequest } from "next";
import { jwtVerify, JWTPayload } from "jose";

const enc = (s: string) => new TextEncoder().encode(s);

const CLI_SECRET = enc(process.env.CLI_JWT_SECRET!);

export const ISSUER = "your-app";

export type AuthUser = {
  sub: string;
  provider?: string; // e.g. "exchange"
  product?: string;  // e.g. "outlook"
  raw?: JWTPayload;
};

export async function verifyCliToken(token: string): Promise<AuthUser> {
  const { payload } = await jwtVerify(token, CLI_SECRET, {
    issuer: ISSUER,
    audience: "cli",
    clockTolerance: "60s",
  });
  if (!payload.sub) throw new Error("missing sub");
  return {
    sub: String(payload.sub),
    provider: typeof payload.provider === "string" ? payload.provider : undefined,
    product: typeof payload.product === "string" ? payload.product : undefined,
    raw: payload,
  };
}

/**
 * Verifies the Authorization: Bearer token from the CLI.
 * Returns null on any verification failure.
 */
export async function getAuth(req: NextApiRequest): Promise<AuthUser | null> {
  const auth = req.headers.authorization;
  if (!auth?.startsWith("Bearer ")) return null;
  const token = auth.slice("Bearer ".length).trim();
  try {
    return await verifyCliToken(token);
  } catch {
    return null;
  }
}

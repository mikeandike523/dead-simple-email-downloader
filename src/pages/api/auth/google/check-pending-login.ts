import { dbQuery } from "@/server/db";
import isJsonLikeContentType from "@/utils/isJsonLikeContentType";
import { NextApiRequest, NextApiResponse } from "next";
import { sign as signJwtHS } from "@/utils/jwt-sign";
import { ISSUER } from "@/server/auth";
import { v4 as uuidv4 } from "uuid";

export default async function checkPendingLogin(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  if (!isJsonLikeContentType(req.headers?.["content-type"])) {
    return res.status(400).json({ error: "Invalid content type" });
  }

  if (typeof req.body !== "string") {
    return res.status(400).json({ error: "Invalid request body" });
  }

  const pollToken = req.body;

  const rows = await dbQuery(
    "SELECT ok, openid_sub, provider, product FROM pending_logins WHERE poll_token = ?",
    [pollToken]
  );
  if (rows.length === 0) {
    return res.status(404).json({ error: "Poll token not found" });
  }

  const { ok, openid_sub, provider, product } = rows[0] as {
    ok: number | boolean;
    openid_sub: string | null;
    provider: string;
    product: string;
  };

  if (!ok) {
    return res.status(403).end();
  }

  if (!openid_sub) {
    return res.status(500).json({ error: "Login completed but subject missing" });
  }

  await dbQuery(
    "UPDATE pending_logins SET touched_at = CURRENT_TIMESTAMP WHERE poll_token = ?",
    [pollToken]
  );

  const ttl = 12 * 60 * 60;

  const jwt = await signJwtHS(
    { sub: openid_sub, aud: "cli", iss: ISSUER, jti: uuidv4(), provider, product },
    ttl
  );

  res.setHeader("Access-Control-Allow-Origin", "*");
  return res.status(200).json({
    jwt,
    token_type: "Bearer",
    expires_in: ttl,
    provider,
    product,
  });
}

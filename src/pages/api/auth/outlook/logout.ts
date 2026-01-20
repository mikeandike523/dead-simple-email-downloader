import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { dbExec } from "@/server/db";

export default async function logout(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader(
      "Access-Control-Allow-Headers",
      "Content-Type, Authorization"
    );
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) {
    return res.status(401).json({ error: "unauthorized" });
  }

  const openidSub = user.sub;

  const accessTokens = await dbExec(
    "DELETE FROM access_tokens WHERE openid_sub = ?",
    [openidSub]
  );
  const oauthTokens = await dbExec(
    "DELETE FROM oauth_tokens WHERE openid_sub = ?",
    [openidSub]
  );

  return res.status(200).json({
    ok: true,
    cleared: {
      accessTokens: accessTokens.affectedRows ?? 0,
      oauthTokens: oauthTokens.affectedRows ?? 0,
    },
  });
}

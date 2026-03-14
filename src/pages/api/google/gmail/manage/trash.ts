import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";

const GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  const { messageId } = req.body ?? {};
  if (!messageId) return res.status(400).json({ error: "messageId is required" });

  const callOpts = {
    openidSub: user.sub,
    provider: user.provider ?? "google",
    product: user.product ?? "gmail",
  };

  const result = await callGoogleJSON({
    ...callOpts,
    url: `${GMAIL_BASE}/messages/${messageId}/trash`,
    method: "POST",
  });

  if (!result.ok) {
    return res.status(result.status).json({ error: result.text });
  }

  return res.status(200).json({ ok: true });
}

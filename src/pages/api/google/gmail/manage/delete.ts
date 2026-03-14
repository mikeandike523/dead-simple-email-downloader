import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";

const GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "DELETE") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  // messageId passed as query param since DELETE bodies are non-standard
  const messageId = req.query.messageId as string | undefined;
  if (!messageId) return res.status(400).json({ error: "messageId query param is required" });

  const callOpts = {
    openidSub: user.sub,
    provider: user.provider ?? "google",
    product: user.product ?? "gmail",
  };

  const result = await callGoogleJSON({
    ...callOpts,
    url: `${GMAIL_BASE}/messages/${messageId}`,
    method: "DELETE",
  });

  if (!result.ok) {
    return res.status(result.status).json({ error: result.text });
  }

  return res.status(200).json({ ok: true });
}

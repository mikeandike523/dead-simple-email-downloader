import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";

const GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

type Part = {
  mimeType: string;
  body: { data?: string; size?: number };
  parts?: Part[];
};

type FullMessage = {
  id: string;
  payload: Part;
};

/** Recursively search for the first part matching mimeType, return decoded text. */
function findPart(part: Part, mimeType: string): string | null {
  if (part.mimeType === mimeType && part.body?.data) {
    return Buffer.from(part.body.data, "base64url").toString("utf-8");
  }
  if (part.parts) {
    for (const child of part.parts) {
      const found = findPart(child, mimeType);
      if (found) return found;
    }
  }
  return null;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  const messageId = req.query.messageId as string;
  if (!messageId) return res.status(400).json({ error: "messageId required" });

  const callOpts = {
    openidSub: user.sub,
    provider: user.provider ?? "google",
    product: user.product ?? "gmail",
  };

  const result = await callGoogleJSON<FullMessage>({
    ...callOpts,
    url: `${GMAIL_BASE}/messages/${messageId}`,
    urlParams: { format: "full" },
  });

  if (!result.ok) {
    return res.status(result.status).json({ error: result.text });
  }

  const payload = result.data?.payload;
  if (!payload) {
    return res.status(404).json({ error: "No payload found" });
  }

  const html = findPart(payload, "text/html");
  if (html) {
    return res.status(200).json({ html });
  }

  const text = findPart(payload, "text/plain");
  return res.status(200).json({ text: text ?? "(no body)" });
}

import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { dbExec } from "@/server/db";

const SUBJECT_MAX = 256;
const PREVIEW_MAX = 512;

/** Truncate by Unicode code point (not UTF-16 code unit) to avoid splitting surrogates. */
function truncate(value: unknown, max: number): string | null {
  if (value === undefined || value === null) return null;
  const s = String(value);
  const chars = [...s]; // spread iterates code points
  return chars.length <= max ? s : chars.slice(0, max).join("");
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  const { messageId, categoryId, subject, bodyPreview } = req.body ?? {};
  if (!messageId || categoryId === undefined || categoryId === null) {
    return res.status(400).json({ error: "messageId and categoryId are required" });
  }

  const subjectTrunc  = truncate(subject, SUBJECT_MAX);
  const previewTrunc  = truncate(bodyPreview, PREVIEW_MAX);

  await dbExec(
    `INSERT INTO email_category_assignments
       (provider, product, message_id, category_id, openid_sub, subject, body_preview)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON DUPLICATE KEY UPDATE
       assigned_at  = NOW(),
       subject      = VALUES(subject),
       body_preview = VALUES(body_preview)`,
    [
      user.provider ?? "google",
      user.product ?? "gmail",
      messageId,
      categoryId,
      user.sub,
      subjectTrunc,
      previewTrunc,
    ]
  );

  return res.status(200).json({ ok: true });
}

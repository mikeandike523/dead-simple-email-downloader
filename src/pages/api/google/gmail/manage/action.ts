import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { dbExec } from "@/server/db";

const SUBJECT_MAX    = 256;
const PREVIEW_MAX    = 512;
const FROM_MAX       = 512;
const LABEL_NAME_MAX = 255;

const VALID_ACTIONS = new Set(["hard_delete", "soft_delete", "move", "inbox"]);

/** Truncate by Unicode code point (not UTF-16 code unit) to avoid splitting surrogates. */
function truncate(value: unknown, max: number): string | null {
  if (value === undefined || value === null) return null;
  const s = String(value);
  const chars = [...s];
  return chars.length <= max ? s : chars.slice(0, max).join("");
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  const { messageId, action, labelId, labelName, subject, bodyPreview, fromAddress } =
    req.body ?? {};

  if (!messageId) {
    return res.status(400).json({ error: "messageId is required" });
  }
  if (!action || !VALID_ACTIONS.has(action)) {
    return res.status(400).json({ error: `action must be one of: ${[...VALID_ACTIONS].join(", ")}` });
  }
  if (action === "move" && !labelId) {
    return res.status(400).json({ error: "labelId is required for move action" });
  }

  const provider = user.provider ?? "google";
  const product  = user.product  ?? "gmail";

  const subjectTrunc   = truncate(subject,     SUBJECT_MAX);
  const previewTrunc   = truncate(bodyPreview, PREVIEW_MAX);
  const fromTrunc      = truncate(fromAddress, FROM_MAX);
  const labelNameTrunc = truncate(labelName,   LABEL_NAME_MAX);

  // Upsert email_content, reusing the existing row if this message was seen before.
  const contentResult = await dbExec(
    `INSERT INTO email_content
       (provider, product, message_id, openid_sub, subject, body_preview, from_address)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON DUPLICATE KEY UPDATE
       subject      = VALUES(subject),
       body_preview = VALUES(body_preview),
       from_address = VALUES(from_address),
       id           = LAST_INSERT_ID(id)`,
    [provider, product, messageId, user.sub, subjectTrunc, previewTrunc, fromTrunc]
  );

  const emailContentId = contentResult.insertId;

  await dbExec(
    `INSERT INTO email_actions (email_content_id, action, label_id, label_name)
     VALUES (?, ?, ?, ?)`,
    [emailContentId, action, labelId ?? null, labelNameTrunc ?? null]
  );

  return res.status(200).json({ ok: true });
}

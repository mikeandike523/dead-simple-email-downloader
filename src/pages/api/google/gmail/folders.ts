import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";

const GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

type LabelSummary = {
  id: string;
  name: string;
  type: "system" | "user";
  total: number;
  unread: number;
  read: number;
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) {
    return res.status(401).json({ error: "unauthorized" });
  }

  const callOpts = {
    openidSub: user.sub,
    provider: user.provider ?? "google",
    product: user.product ?? "gmail",
  };

  // 1. List all label IDs (counts not included at this level)
  const listResult = await callGoogleJSON<{ labels: { id: string; name: string }[] }>({
    ...callOpts,
    url: `${GMAIL_BASE}/labels`,
  });

  if (!listResult.ok) {
    return res.status(listResult.status).json({ error: listResult.text });
  }

  const labels = (listResult.data as any)?.labels ?? [];

  // 2. Fetch full details (including counts) for all labels concurrently
  const detailResults = await Promise.all(
    labels.map((label: { id: string }) =>
      callGoogleJSON({
        ...callOpts,
        url: `${GMAIL_BASE}/labels/${label.id}`,
        silent: true,
      })
    )
  );

  const folders: LabelSummary[] = detailResults
    .filter((d) => d.ok && d.data)
    .map((d) => {
      const l = d.data as any;
      const total: number = l.messagesTotal ?? 0;
      const unread: number = l.messagesUnread ?? 0;
      return {
        id: l.id,
        name: l.name,
        type: l.type === "system" ? "system" : "user",
        total,
        unread,
        read: total - unread,
      };
    });

  return res.status(200).json({ folders });
}

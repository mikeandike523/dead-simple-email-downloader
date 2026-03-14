import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";

const GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

type MessageHeader = { name: string; value: string };
type MessageDetail = {
  id: string;
  threadId: string;
  snippet: string;
  labelIds: string[];
  payload: { headers: MessageHeader[] };
};
type ListResponse = {
  messages?: { id: string; threadId: string }[];
  nextPageToken?: string;
  resultSizeEstimate?: number;
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  const callOpts = {
    openidSub: user.sub,
    provider: user.provider ?? "google",
    product: user.product ?? "gmail",
  };

  const pageToken = req.query.pageToken as string | undefined;

  const urlParams: Record<string, string | number> = { labelIds: "INBOX", maxResults: 10 };
  if (pageToken) urlParams.pageToken = pageToken;

  const listResult = await callGoogleJSON<ListResponse>({
    ...callOpts,
    url: `${GMAIL_BASE}/messages`,
    urlParams,
  });

  if (!listResult.ok) {
    return res.status(listResult.status).json({ error: listResult.text });
  }

  const messages = listResult.data?.messages ?? [];
  const nextPageToken = listResult.data?.nextPageToken ?? null;
  const total = listResult.data?.resultSizeEstimate ?? 0;

  const details = await Promise.all(
    messages.map((msg) =>
      callGoogleJSON<MessageDetail>({
        ...callOpts,
        url: `${GMAIL_BASE}/messages/${msg.id}`,
        urlParams: {
          format: "metadata",
          metadataHeaders: ["Subject", "From", "Date"],
        },
        silent: true,
      })
    )
  );

  const getHeader = (headers: MessageHeader[], name: string) =>
    headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? "";

  const emails = details
    .filter((d) => d.ok && d.data)
    .map((d) => {
      const msg = d.data as MessageDetail;
      const headers = msg.payload?.headers ?? [];
      return {
        id: msg.id,
        threadId: msg.threadId,
        subject: getHeader(headers, "Subject") || "(no subject)",
        from: getHeader(headers, "From") || "(unknown sender)",
        date: getHeader(headers, "Date") || "",
        snippet: msg.snippet ?? "",
      };
    });

  return res.status(200).json({ emails, nextPageToken, total });
}

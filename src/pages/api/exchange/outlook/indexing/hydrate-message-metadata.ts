import { NextApiResponse } from "next";
import { AuthedNextApiRequest, withAuth } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

const MAX_BATCH_SIZE = 20; // Graph $batch max requests. :contentReference[oaicite:4]{index=4}
const TIMEOUT_MILLIS = 2000;

type HydrateBody = {
  ids: string[];
  includeHeaders?: boolean;
  includeEpoch?: boolean;
};

type MessageMeta = {
  id: string;
  conversationId?: string;
  conversationIndex?: string;
  internetMessageId?: string;
  subject?: string;
  from?: { emailAddress: { address: string; name?: string } };
  toRecipients?: Array<{ emailAddress: { address: string; name?: string } }>;
  ccRecipients?: Array<{ emailAddress: { address: string; name?: string } }>;
  receivedDateTime?: string;
  sentDateTime?: string;
  internetMessageHeaders?: Array<{ name: string; value: string }>;
  receivedEpoch?: number;
  sentEpoch?: number;
};

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    if(typeof req.body!== "object" ||!req.body) {
        return res.status(400).json({ error: "Invalid request body" });
    }

    const { ids, includeHeaders = false, includeEpoch = true } = req.body as HydrateBody
    const openidSub = req.user.sub;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ error: "Provide a non-empty 'ids' array" });
    }

    // Build $select list
    const baseSelect = [
      "id",
      "conversationId",
      "conversationIndex",
      "internetMessageId",
      "subject",
      "from",
      "toRecipients",
      "ccRecipients",
      "receivedDateTime",
      "sentDateTime",
    ];
    if (includeHeaders) baseSelect.push("internetMessageHeaders"); // :contentReference[oaicite:5]{index=5}
    const selectParam = `$select=${encodeURIComponent(baseSelect.join(","))}`;

    // Helper to chunk ids -> batches of <= 20
    const chunks: string[][] = [];
    for (let i = 0; i < ids.length; i += MAX_BATCH_SIZE) {
      chunks.push(ids.slice(i, i + MAX_BATCH_SIZE));
    }

    const all: MessageMeta[] = [];

    // Fire batches sequentially (simpler; you can parallelize with throttling/backoff)
    for (const chunk of chunks) {
      const requests = chunk.map((id, i) => ({
        id: String(i + 1),
        method: "GET",
        url: `/me/messages/${encodeURIComponent(id)}?${selectParam}`,
      }));

      const batchResp = await callGraphJSON<{
        responses: Array<{
          id: string;
          status: number;
          headers?: Record<string, string>;
          body?: any;
        }>;
      }>({
        route: "/$batch",
        method: "POST",
        openidSub,
        body: { requests },
        timeoutMs: TIMEOUT_MILLIS,
      });

      if (!batchResp.ok || !batchResp.data) {
        return res.status(502).json({
          error: "Graph $batch failed",
          detail: batchResp.text,
        });
      }

      for (const r of batchResp.data.responses) {
        if (r.status === 200 && r.body) {
          const m = r.body as MessageMeta; // shape per GET /me/messages :contentReference[oaicite:6]{index=6}

          // Ensure ISO strings are left in UTC (Graph already returns Z). Also add epoch if requested.
          if (includeEpoch) {
            if (m.receivedDateTime) m.receivedEpoch = Date.parse(m.receivedDateTime);
            if (m.sentDateTime) m.sentEpoch = Date.parse(m.sentDateTime);
          }

          all.push(m);
        } else if (r.status === 404) {
          // Message might have been deleted or moved in a way that hides it — just skip
          continue;
        } else {
          // Collect partial errors but don’t fail whole request
          // You could push a placeholder with the id and an error field if you prefer.
          continue;
        }
      }
    }

    return res.status(200).json({ messages: all });
  } catch (err: any) {
    // If you want to expose throttling, you could check for 429 in callGraphJSON and include retry-after
    return res.status(502).json({
      error: "Failed to hydrate message metadata.",
      detail: String(err?.message || err),
    });
  }
};

export default withAuth(handler);

import { NextApiResponse } from "next";

import { AuthedNextApiRequest, withAuth } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

type RouteBody = {
  messageIds: string[];
  soft?: boolean;
};

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    if (typeof req.body !== "object" || !req.body) {
      return res.status(400).json({ error: "Invalid request body" });
    }

    const { messageIds, soft = false } = req.body as RouteBody;

    if (!Array.isArray(messageIds) || messageIds.length === 0) {
      return res.status(400).json({
        error: "messageIds must be a non-empty array of strings",
      });
    }

    const deletedIds: string[] = [];
    const failed: Array<{ id: string; status?: number; error?: string }> = [];

    for (const id of messageIds) {
      if (typeof id !== "string" || id.length === 0) {
        failed.push({ id: String(id), error: "Invalid message id" });
        continue;
      }

      const graphResult = soft
        ? await callGraphJSON({
            route: `/me/messages/${id}/move`,
            method: "POST",
            body: { destinationId: "deleteditems" },
            openidSub,
          })
        : await callGraphJSON({
            route: `/me/messages/${id}`,
            method: "DELETE",
            openidSub,
          });

      if (!graphResult.ok) {
        failed.push({
          id,
          status: graphResult.status,
          error: graphResult.text,
        });
        continue;
      }

      deletedIds.push(id);
    }

    return res.status(200).json({
      requested: messageIds.length,
      deletedIds,
      failed,
    });
  } catch (err: any) {
    return res.status(502).json({
      error: "Failed to delete messages.",
      detail: String(err?.message || err),
    });
  }
};

export default withAuth(handler);

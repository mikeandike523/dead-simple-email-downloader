import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;
    const messageIdRaw = req.query.messageId;
    const attachmentIdRaw = req.query.attachmentId;
    const messageId = Array.isArray(messageIdRaw)
      ? messageIdRaw[0]
      : messageIdRaw;
    const attachmentId = Array.isArray(attachmentIdRaw)
      ? attachmentIdRaw[0]
      : attachmentIdRaw;

    if (!messageId || !attachmentId) {
      return res
        .status(400)
        .json({ error: "Missing messageId or attachmentId" });
    }

    const graphResult = await callGraphJSON({
      openidSub,
      route: `/me/messages/${encodeURIComponent(
        messageId
      )}/attachments/${encodeURIComponent(attachmentId)}`,
      urlParams: {
        $expand: "microsoft.graph.itemAttachment/item",
      },
    });

    if (!graphResult.ok) {
      return res.status(502).json({
        error: "Failed to fetch attachment",
        text: graphResult.text,
      });
    }

    return res.status(200).json(graphResult.data);
  } catch (err: any) {
    return res
      .status(500)
      .json({ error: "Server error", detail: String(err?.message || err) });
  }
};

export default withAuth(handler);

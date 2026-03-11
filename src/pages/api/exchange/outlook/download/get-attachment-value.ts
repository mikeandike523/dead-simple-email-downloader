import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphBinary } from "@/server/msgraph";

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

    const graphRes = await callGraphBinary({
      openidSub,
      route: `/me/messages/${encodeURIComponent(
        messageId
      )}/attachments/${encodeURIComponent(attachmentId)}/$value`,
    });

    if (!graphRes.ok) {
      const text = await graphRes.text();
      return res.status(graphRes.status).json({
        error: "Failed to fetch attachment value",
        text,
      });
    }

    const buf = Buffer.from(await graphRes.arrayBuffer());
    const contentType =
      graphRes.headers.get("Content-Type") || "application/octet-stream";
    res.setHeader("Content-Type", contentType);
    return res.status(200).send(buf);
  } catch (err: any) {
    return res
      .status(500)
      .json({ error: "Server error", detail: String(err?.message || err) });
  }
};

export default withAuth(handler);

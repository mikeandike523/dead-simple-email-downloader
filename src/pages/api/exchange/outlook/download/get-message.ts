import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

const MESSAGE_SELECT_FIELDS = [
  "id",
  "conversationId",
  "subject",
  "from",
  "toRecipients",
  "ccRecipients",
  "bccRecipients",
  "sentDateTime",
  "receivedDateTime",
  "internetMessageId",
  "hasAttachments",
  "body",
  "uniqueBody",
];

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;
    const messageIdRaw = req.query.messageId;
    const messageId = Array.isArray(messageIdRaw)
      ? messageIdRaw[0]
      : messageIdRaw;

    if (!messageId) {
      return res.status(400).json({ error: "Missing messageId" });
    }

    const graphResult = await callGraphJSON({
      openidSub,
      route: `/me/messages/${encodeURIComponent(messageId)}`,
      urlParams: {
        $select: MESSAGE_SELECT_FIELDS,
      },
    });

    if (!graphResult.ok) {
      return res
        .status(502)
        .json({ error: "Failed to fetch message", text: graphResult.text });
    }

    return res.status(200).json(graphResult.data);
  } catch (err: any) {
    return res
      .status(500)
      .json({ error: "Server error", detail: String(err?.message || err) });
  }
};

export default withAuth(handler);

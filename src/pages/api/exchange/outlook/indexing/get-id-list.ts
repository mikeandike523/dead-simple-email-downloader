import { NextApiResponse } from "next";

import { AuthedNextApiRequest, withAuth } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

type RouteBody = {
  folderId: string;
  nextLink?: string | null;
};

const PAGE_SIZE=100;

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;

    if (typeof req.body !== "object" || !req.body) {
      return res.status(400).json({ error: "Invalid request body" });
    }

    const { folderId, nextLink: previousNextLink } = req.body as RouteBody;

    const route = previousNextLink
      ? previousNextLink
      : `/me/mailFolders/${folderId}/messages/delta`;

    const graphResult = await callGraphJSON<{
      value: Array<{ id: string }>;
      "@odata.deltaLink"?: string | null;
      "@odata.nextLink"?: string | null;
    }>({
      route,
      urlParams: previousNextLink?undefined:{
        "$select":"id",
      },
      additionalHeaders:{
        "Prefer":`odata.maxpagesize=${PAGE_SIZE}`
      },
      method: "GET",
      openidSub,
    });

    if (!graphResult.ok) {
      return res
        .status(400)
        .json({ error: "Failed to fetch messages", text: graphResult.text });
    }

    if (typeof graphResult.data !== "object" || !graphResult.data) {
      return res.status(400).json({
        error: "Invalid response from Microsoft Graph API",
        text: graphResult.text,
      });
    }

    const messageIds = graphResult.data.value.map((message) => message.id);
    const nextLink = graphResult.data["@odata.nextLink"] || null;
    const deltaLink = graphResult.data["@odata.deltaLink"] || null;

    return res.status(200).json({
      messageIds,
      nextLink,
      deltaLink,
    });
  } catch (err: any) {
    return res.status(502).json({
      error: "Failed to get message id list.",
      detail: String(err?.message || err),
    });
  }
};

export default withAuth(handler);

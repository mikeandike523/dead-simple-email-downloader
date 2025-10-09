// pages/api/get-folder-metadata.ts

import { NextApiResponse } from "next";

import { AuthedNextApiRequest, withAuth } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

type RouteBody = {
  folderId: string;
};

type MailFolderMeta = {
  id: string;
  displayName?: string;
  totalItemCount?: number;
  unreadItemCount?: number;
  childFolderCount?: number;
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

    const { folderId } = req.body as RouteBody;

    if (!folderId || typeof folderId !== "string") {
      return res.status(400).json({ error: "Missing or invalid folderId" });
    }

    const route = `/me/mailFolders/${encodeURIComponent(
      folderId
    )}?$select=id,displayName,totalItemCount,unreadItemCount,childFolderCount`;

    const graphResult = await callGraphJSON<MailFolderMeta>({
      route,
      method: "GET",
      openidSub,
    });

    if (!graphResult.ok) {
      return res.status(400).json({
        error: "Failed to fetch folder metadata",
        text: graphResult.text,
      });
    }

    const data = graphResult.data;
    if (typeof data !== "object" || !data || !data.id) {
      return res.status(400).json({
        error: "Invalid response from Microsoft Graph API",
        text: graphResult.text,
      });
    }

    const {
      id,
      displayName = null,
      totalItemCount = null,
      unreadItemCount = null,
      childFolderCount = null,
    } = data;

    // Return minimal, comparison-friendly payload
    return res.status(200).json({
      folderId: id,
      displayName,
      counts: {
        totalItemCount,
        unreadItemCount,
        childFolderCount,
      },
    });
  } catch (err: any) {
    return res.status(502).json({
      error: "Failed to retrieve folder metadata",
      detail: String(err?.message || err),
    });
  }
};

export default withAuth(handler);

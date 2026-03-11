import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

type GraphListResponse<T> = {
  value?: T[];
  "@odata.nextLink"?: string;
};

function normalizeRouteFromNextLink(nextLink: string): string {
  const u = nextLink.startsWith("http")
    ? new URL(nextLink)
    : new URL(nextLink, "https://graph.microsoft.com/v1.0/");
  return u.pathname.replace(/^\/+/, "") + (u.search || "");
}

async function graphGetAll<T>(
  openidSub: string,
  route: string
): Promise<T[]> {
  const all: T[] = [];
  let next: string | null = route;

  while (next) {
    const res = await callGraphJSON({ openidSub, route: next });
    if (!res.ok) throw new Error(`Graph GET failed for ${next}`);
    const data = (res.data || {}) as GraphListResponse<T>;
    if (Array.isArray(data.value)) all.push(...data.value);
    next = data["@odata.nextLink"]
      ? normalizeRouteFromNextLink(data["@odata.nextLink"])
      : null;
  }
  return all;
}

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

    const attachments = await graphGetAll(
      openidSub,
      `/me/messages/${encodeURIComponent(messageId)}/attachments`
    );

    return res.status(200).json({ attachments });
  } catch (err: any) {
    return res
      .status(502)
      .json({ error: "Failed to fetch attachments", detail: String(err?.message || err) });
  }
};

export default withAuth(handler);

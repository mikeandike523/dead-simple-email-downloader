import { NextApiResponse } from "next";

import { AuthedNextApiRequest, withAuth } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";
import { ResponseSummary } from "@/utils/summarizeResponse";

type RouteBody = {
  exactSender: string;
  exactSubject: string;
  caseSensitive?: boolean;
  subjectIsRegex?: boolean;
};

type GraphMessage = {
  id?: string;
  subject?: string | null;
  bodyPreview?: string | null;
  receivedDateTime?: string | null;
  from?: {
    emailAddress?: {
      address?: string | null;
      name?: string | null;
    } | null;
  } | null;
};

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

function escapeSearchTerm(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function buildSearchQuery(sender: string, subject: string): string {
  const safeSender = escapeSearchTerm(sender);
  const safeSubject = escapeSearchTerm(subject);
  return `"from:${safeSender} subject:\\"${safeSubject}\\""`;
}

function getSenderAddress(msg: GraphMessage): string {
  return msg.from?.emailAddress?.address?.toString() ?? "";
}

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    if (typeof req.body !== "object" || !req.body) {
      return res.status(400).json({ error: "Invalid request body" });
    }

    const {
      exactSender,
      exactSubject,
      caseSensitive = false,
      subjectIsRegex = false,
    } = req.body as RouteBody;

    if (!exactSender || !exactSubject) {
      return res.status(400).json({
        error: "exactSender and exactSubject are required",
      });
    }

    let subjectRegex: RegExp | null = null;
    if (subjectIsRegex) {
      try {
        subjectRegex = new RegExp(exactSubject, caseSensitive ? "" : "i");
      } catch (err: any) {
        return res.status(400).json({
          error: "Invalid subject regex",
          detail: String(err?.message || err),
        });
      }
    }

    const senderCompare = caseSensitive
      ? exactSender
      : exactSender.toLowerCase();
    const subjectCompare = caseSensitive
      ? exactSubject
      : exactSubject.toLowerCase();

    const search = subjectIsRegex
      ? `"from:${escapeSearchTerm(exactSender)}"`
      : buildSearchQuery(exactSender, exactSubject);

    const matches: Array<{
      id: string;
      subject: string | null;
      bodyPreview: string | null;
      receivedDateTime: string | null;
      from: {
        emailAddress: {
          address: string | null;
          name: string | null;
        } | null;
      } | null;
    }> = [];

    let next: string | null = "/me/messages";
    const urlParams = {
      $select: "id,subject,bodyPreview,receivedDateTime,from",
      $top: 100,
      $search: search,
      $count: true,
    };
    const additionalHeaders = {
      ConsistencyLevel: "eventual",
    };

    while (next) {
      const graphResult: ResponseSummary<GraphListResponse<GraphMessage>> =
        await callGraphJSON<GraphListResponse<GraphMessage>>({
          route: next,
          urlParams: next === "/me/messages" ? urlParams : undefined,
          method: "GET",
          openidSub,
          additionalHeaders,
        });

      if (!graphResult.ok) {
        return res.status(400).json({
          error: "Failed to fetch messages",
          text: graphResult.text,
        });
      }

      if (typeof graphResult.data !== "object" || !graphResult.data) {
        return res.status(400).json({
          error: "Invalid response from Microsoft Graph API",
          text: graphResult.text,
        });
      }

      const batch = Array.isArray(graphResult.data.value)
        ? graphResult.data.value
        : [];

      for (const msg of batch) {
        const senderAddress = getSenderAddress(msg);
        const subject = msg.subject ?? "";
        const senderMatch = caseSensitive
          ? senderAddress === senderCompare
          : senderAddress.toLowerCase() === senderCompare;
        const subjectMatch = subjectRegex
          ? subjectRegex.test(subject)
          : caseSensitive
            ? subject === subjectCompare
            : subject.toLowerCase() === subjectCompare;

        if (!senderMatch || !subjectMatch) continue;
        if (!msg.id) continue;

        matches.push({
          id: msg.id,
          subject: msg.subject ?? null,
          bodyPreview: msg.bodyPreview ?? null,
          receivedDateTime: msg.receivedDateTime ?? null,
          from: msg.from
            ? {
                emailAddress: msg.from.emailAddress
                  ? {
                      address: msg.from.emailAddress.address ?? null,
                      name: msg.from.emailAddress.name ?? null,
                    }
                  : null,
              }
            : null,
        });
      }

      const nextLink = graphResult.data["@odata.nextLink"];
      next = nextLink ? normalizeRouteFromNextLink(nextLink) : null;
    }

    return res.status(200).json({
      matches,
      count: matches.length,
    });
  } catch (err: any) {
    return res.status(502).json({
      error: "Failed to find matching messages.",
      detail: String(err?.message || err),
    });
  }
};

export default withAuth(handler);

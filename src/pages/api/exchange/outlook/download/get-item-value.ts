import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphBinary } from "@/server/msgraph";

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;
    const itemTypeRaw = req.query.itemType;
    const itemIdRaw = req.query.itemId;
    const itemType = Array.isArray(itemTypeRaw) ? itemTypeRaw[0] : itemTypeRaw;
    const itemId = Array.isArray(itemIdRaw) ? itemIdRaw[0] : itemIdRaw;

    if (!itemType || !itemId) {
      return res.status(400).json({ error: "Missing itemType or itemId" });
    }

    let route: string | null = null;
    if (itemType === "event") {
      route = `/me/events/${encodeURIComponent(itemId)}/$value`;
    } else if (itemType === "contact") {
      route = `/me/contacts/${encodeURIComponent(itemId)}/$value`;
    }

    if (!route) {
      return res.status(400).json({ error: "Unsupported itemType" });
    }

    const graphRes = await callGraphBinary({ openidSub, route });
    if (!graphRes.ok) {
      const text = await graphRes.text();
      return res.status(graphRes.status).json({
        error: "Failed to fetch item value",
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

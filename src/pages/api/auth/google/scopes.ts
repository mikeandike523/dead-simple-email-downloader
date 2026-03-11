import type { NextApiRequest, NextApiResponse } from "next";
import { describeScopeRequest, type Product } from "@/server/scopes";

const PROVIDER = "google";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const productRaw = typeof req.query.product === "string" ? req.query.product : "gmail";
  const commandsRaw = typeof req.query.commands === "string" ? req.query.commands : "";
  const commands = commandsRaw ? commandsRaw.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const description = describeScopeRequest(PROVIDER, productRaw as Product, commands);

  return res.status(200).json({
    provider: PROVIDER,
    product: productRaw,
    commands,
    ...description,
  });
}

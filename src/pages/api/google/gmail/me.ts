import type { NextApiRequest, NextApiResponse } from "next";
import { getAuth } from "@/server/auth";
import { callGoogleJSON } from "@/server/google";
import { getErrorMessage } from "@/utils/errors";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const user = await getAuth(req);
  if (!user) {
    return res.status(401).json({ error: "unauthorized" });
  }

  try {
    const result = await callGoogleJSON({
      openidSub: user.sub,
      provider: user.provider ?? "google",
      product: user.product ?? "gmail",
      url: "https://www.googleapis.com/oauth2/v2/userinfo",
    });

    return res.status(result.status).json(result.data ?? { error: result.text });
  } catch (e: unknown) {
    return res.status(500).json({ error: getErrorMessage(e) || "internal_error" });
  }
}

import { dbQuery } from "@/utils/db";
import isJsonLikeContentType from "@/utils/isJsonLikeContentType";
import { NextApiRequest, NextApiResponse } from "next";

export default async function checkPendingLogin(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === "OPTIONS") {
    // respond to preflight with the CORS headers
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader(
      "Access-Control-Allow-Headers",
      "Content-Type, Authorization"
    );
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  // Ensure content type is a variant of application/json, and if charset is present, it is utf-8
  if (!isJsonLikeContentType(req.headers?.["content-type"])) {
    return res.status(400).json({ error: "Invalid content type" });
  }

  console.log(req.body)

  if (typeof req.body !== "string") {
    return res.status(400).json({ error: "Invalid request body" });
  }

  // Auto-parsed
  const pollToken = req.body;

  const results = await dbQuery(
    "SELECT ok from pending_logins WHERE poll_token = ?",
    [pollToken]
  );
  if (results.length === 0) {
    return res.status(404).json({ error: "Poll token not found" });
  }
  const [result] = results;
  const { ok } = result;
  return res.status(ok ? 204 : 403).end();
}

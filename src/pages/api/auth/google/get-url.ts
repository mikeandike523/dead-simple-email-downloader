import type { NextApiRequest, NextApiResponse } from "next";
import { randomString, signState } from "@/server/oidc-state";
import { v4 as uuidv4 } from "uuid";
import { dbExec } from "@/server/db";
import { PRODUCT_SCOPES, type Product } from "@/server/scopes";

const PROVIDER = "google";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const productRaw = typeof req.query.product === "string" ? req.query.product : "gmail";
    const scopes = PRODUCT_SCOPES[PROVIDER]?.[productRaw as Product];
    if (!scopes) {
      return res.status(400).json({ error: `Unknown product: ${productRaw}` });
    }

    const clientId = process.env.GCLOUD_CLIENT_ID!;
    const authUri = process.env.GCLOUD_AUTH_URI!;
    const redirectUri = process.env.GCLOUD_REDIRECT_URI!;
    const nonce = randomString(16);
    const pollToken = uuidv4();

    const state = signState({
      n: nonce,
      ts: Math.floor(Date.now() / 1000),
      pt: pollToken,
      pr: PROVIDER,
      pd: productRaw,
    });

    const url = new URL(authUri);
    url.searchParams.set("client_id", clientId);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("redirect_uri", redirectUri);
    url.searchParams.set("scope", scopes.join(" "));
    url.searchParams.set("state", state);
    url.searchParams.set("nonce", nonce);
    url.searchParams.set("access_type", "offline");
    url.searchParams.set("prompt", "consent");

    await dbExec(
      `INSERT INTO pending_logins (poll_token, provider, product) VALUES (?, ?, ?)`,
      [pollToken, PROVIDER, productRaw]
    );

    res.status(200).json({ pollToken, url: url.toString() });
  } catch (e: any) {
    res.status(500).json({ error: e?.message ?? "internal_error" });
  }
}

import type { NextApiRequest, NextApiResponse } from "next";
import { randomString, signState } from "@/server/oidc-state";
import { v4 as uuidv4 } from "uuid";
import { dbExec } from "@/server/db";
import { resolveScopes, type Product } from "@/server/scopes";
import { getErrorMessage } from "@/utils/errors";

const PROVIDER = "exchange";
const tenant = process.env.AZURE_TENANT || "common";
const authBase = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/authorize`;

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const productRaw = typeof req.query.product === "string" ? req.query.product : "outlook";
    const commandsRaw = typeof req.query.commands === "string" ? req.query.commands : "";
    const commands = commandsRaw ? commandsRaw.split(",").map((s) => s.trim()).filter(Boolean) : [];

    const scopes = resolveScopes(PROVIDER, productRaw as Product, commands);
    if (scopes.length === 0) {
      return res.status(400).json({ error: `Unknown product: ${productRaw}` });
    }

    const clientId = process.env.AZURE_CLIENT_ID!;
    const redirectUri = process.env.AZURE_OAUTH_REDIRECT_URL!;
    const nonce = randomString(16);
    const pollToken = uuidv4();

    const state = signState({
      n: nonce,
      ts: Math.floor(Date.now() / 1000),
      pt: pollToken,
      pr: PROVIDER,
      pd: productRaw,
    });

    const url = new URL(authBase);
    url.searchParams.set("client_id", clientId);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("redirect_uri", redirectUri);
    url.searchParams.set("response_mode", "query");
    url.searchParams.set("scope", scopes.join(" "));
    url.searchParams.set("state", state);
    url.searchParams.set("nonce", nonce);
    url.searchParams.set("prompt", "select_account");

    await dbExec(
      `INSERT INTO pending_logins (poll_token, provider, product) VALUES (?, ?, ?)`,
      [pollToken, PROVIDER, productRaw]
    );

    res.status(200).json({ pollToken, url: url.toString() });
  } catch (e: unknown) {
    res.status(500).json({ error: getErrorMessage(e) || "internal_error" });
  }
}

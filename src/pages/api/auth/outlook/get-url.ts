import type { NextApiRequest, NextApiResponse } from "next";
import { randomString, signState } from "@/server/oidc-state";
import { v4 as uuidv4 } from "uuid";
import { dbExec } from "@/server/db";

const tenant = process.env.AZURE_TENANT || "common";
const authBase = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/authorize`;

const SCOPES = [
  "openid",
  "offline_access",
  "User.Read",
  "Mail.Read",
  "Mail.ReadWrite",
  "Mail.Read.Shared",
  "Mail.ReadWrite.Shared",
];

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const clientId = process.env.AZURE_CLIENT_ID!;
    const redirectUri = process.env.OAUTH_REDIRECT_URL!;
    const nonce = randomString(16);
    const pollToken = uuidv4();


    // state carries nonce + timestamp, HMAC-signed (no server storage needed)
    const state = signState({   
      n: nonce,
      ts: Math.floor(Date.now() / 1000),
      pt: pollToken,
    });

    const url = new URL(authBase);
    url.searchParams.set("client_id", clientId);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("redirect_uri", redirectUri);
    url.searchParams.set("response_mode", "query");
    url.searchParams.set("scope", SCOPES.join(" "));
    url.searchParams.set("state", state);
    url.searchParams.set("nonce", nonce);
    // optional: prompt=select_account for easier account switching
    url.searchParams.set("prompt", "select_account");


    const dbResponse = await dbExec(
      `
INSERT INTO pending_logins (poll_token) VALUES (?)     
      `,
      [pollToken]
    );

    const affectedRows = dbResponse.affectedRows;

    if (affectedRows !== 1) {
      res.status(500).json({
        error: "Failed to insert poll token into database",
        ...(dbResponse.warningStatus
          ? { warningStatus: dbResponse.warningStatus }
          : {}),
      });
    }

    // Return JSON so your CLI can parse/print it easily
    res.status(200).json({
      pollToken,
      url: url.toString(),
    });
  } catch (e: any) {
    res.status(500).json({ error: e?.message ?? "internal_error" });
  }
}

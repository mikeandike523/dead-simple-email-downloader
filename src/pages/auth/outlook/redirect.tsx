import { GetServerSideProps } from "next";
import React, { useEffect } from "react";
import { dbExec } from "@/server/db";
import { decodeJwt } from "jose"; // lightweight decode; see note below re: full verification
import { sign as signJwtHS } from "@/utils/jwt-sign"; // small helper you have/ create (HS256)
import { verifyState } from "@/server/oidc-state"; // pair to signState
// If you don't have verifyState, implement it to HMAC-verify and JSON-parse the payload you produced in signState.

const tenant = process.env.AZURE_TENANT || "common";
const tokenEndpoint = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/token`;

type Props = {
  ok: boolean;
  msg: string;
};

export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const { query, res } = ctx;
  try {
    // 1) Handle provider error short-circuit
    if (typeof query.error === "string") {
      return { props: { ok: false, msg: `${query.error}: ${query.error_description ?? ""}` } };
    }

    // 2) Extract code + state
    const code = typeof query.code === "string" ? query.code : "";
    const stateRaw = typeof query.state === "string" ? query.state : "";
    if (!code || !stateRaw) {
      return { props: { ok: false, msg: "Missing code or state" } };
    }

    // 3) Verify and parse state (must include nonce + ts + pt [poll token])
    const state = verifyState(stateRaw); // throws if bad signature / malformed / expired (implement window check inside if you want)
    const { n: nonce, pt: pollToken } = state ?? {};
    if (!nonce || !pollToken) {
      return { props: { ok: false, msg: "Invalid state payload" } };
    }

    // 4) Exchange code for tokens
    const clientId = process.env.AZURE_CLIENT_ID!;
    const clientSecret = process.env.AZURE_CLIENT_SECRET!;
    const redirectUri = process.env.OAUTH_REDIRECT_URL!;

    const form = new URLSearchParams();
    form.set("client_id", clientId);
    form.set("client_secret", clientSecret);
    form.set("grant_type", "authorization_code");
    form.set("code", code);
    form.set("redirect_uri", redirectUri);

    const tokenResp = await fetch(tokenEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });

    if (!tokenResp.ok) {
      const t = await tokenResp.text();
      return { props: { ok: false, msg: `Token exchange failed: ${t}` } };
    }

    const tokens = await tokenResp.json() as {
      token_type: string;
      scope: string;
      expires_in: number;
      ext_expires_in?: number;
      access_token: string;
      refresh_token: string;
      id_token: string;
    };

    const { refresh_token, id_token } = tokens;
    if (!refresh_token || !id_token) {
      return { props: { ok: false, msg: "Provider did not return refresh_token or id_token" } };
    }

    // 5) Decode id_token to get sub and nonce, do light checks (optional: perform full JWKS signature verification)
    const idt = decodeJwt(id_token);
    const idNonce = idt.nonce as string | undefined;
    if (!idNonce || idNonce !== nonce) {
      return { props: { ok: false, msg: "Nonce mismatch" } };
    }

    const sub = idt.sub as string | undefined;
    if (!sub) {
      return { props: { ok: false, msg: "Missing sub in id_token" } };
    }

    // (Optional but recommended) Check iss and aud match what you expect:
    // const issOk = typeof idt.iss === "string" && idt.iss.includes("https://login.microsoftonline.com/");
    // const audOk = idt.aud === clientId;
    // if (!issOk || !audOk) { ... }

    // 6) Upsert refresh token by openid_sub
    await dbExec(
      `
INSERT INTO oauth_tokens (openid_sub, refresh_token)
VALUES (?, ?)
ON DUPLICATE KEY UPDATE
  refresh_token = VALUES(refresh_token),
  updated_at = CURRENT_TIMESTAMP
      `,
      [sub, refresh_token]
    );

    // 7) Mark pending_login as ok + stash the sub on the row + touch timestamp
    const upd = await dbExec(
      `
UPDATE pending_logins
   SET ok = TRUE,
       openid_sub = ?,
       touched_at = CURRENT_TIMESTAMP
 WHERE poll_token = ?
      `,
      [sub, pollToken]
    );
    if (upd.affectedRows !== 1) {
      return { props: { ok: false, msg: "Failed to update pending login" } };
    }

    // (Optional) If you want to show the user a copyable code/JWT here too, you could sign one:
    // const cliJwt = await signJwtHS({ sub, aud: "cli", iss: "your-app" }, "12h");

    // 8) Cache-control: keep this page out of caches
    res.setHeader("Cache-Control", "no-store");

    return { props: { ok: true, msg: "Login complete. You may close this window and return to your CLI." } };
  } catch (e: any) {
    return { props: { ok: false, msg: e?.message ?? "Unexpected error" } };
  }
};

export default function OutlookRedirectPage({ ok, msg }: Props) {
  useEffect(() => {
    if (ok) {
      const id = setTimeout(() => window.close?.(), 1000);
      return () => clearTimeout(id);
    }
  }, [ok]);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>{ok ? "✅ Connected to Microsoft" : "❌ Sign-in failed"}</h1>
      <p>{msg}</p>
    </main>
  );
}
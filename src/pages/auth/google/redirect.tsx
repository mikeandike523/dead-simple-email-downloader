import { GetServerSideProps } from "next";
import React, { useEffect } from "react";
import { dbExec, dbQuery } from "@/server/db";
import { decodeJwt } from "jose";
import { verifyState } from "@/server/oidc-state";

const tokenEndpoint = "https://oauth2.googleapis.com/token";

type Props = {
  ok: boolean;
  msg: string;
};

export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const { query, res } = ctx;
  try {
    if (typeof query.error === "string") {
      return { props: { ok: false, msg: `${query.error}: ${query.error_description ?? ""}` } };
    }

    const code = typeof query.code === "string" ? query.code : "";
    const stateRaw = typeof query.state === "string" ? query.state : "";
    if (!code || !stateRaw) {
      return { props: { ok: false, msg: "Missing code or state" } };
    }

    const state = verifyState(stateRaw);
    const {
      n: nonce,
      pt: pollToken,
      pr: provider = "google",
      pd: product = "gmail",
    } = state ?? {};
    if (!nonce || !pollToken) {
      return { props: { ok: false, msg: "Invalid state payload" } };
    }

    const loginRows = await dbQuery(
      "SELECT ok, openid_sub FROM pending_logins WHERE poll_token = ?",
      [pollToken]
    );
    if (loginRows.length === 0) {
      return { props: { ok: false, msg: "Unknown login request" } };
    }
    const loginRow = loginRows[0] as { ok: number | boolean; openid_sub: string | null };
    if (loginRow.ok && loginRow.openid_sub) {
      res.setHeader("Cache-Control", "no-store");
      return {
        props: {
          ok: true,
          msg: "Login already completed. You may close this window and return to your CLI.",
        },
      };
    }

    const clientId = process.env.GOOGLE_CLIENT_ID!;
    const clientSecret = process.env.GOOGLE_CLIENT_SECRET!;
    const redirectUri = process.env.GOOGLE_OAUTH_REDIRECT_URL!;

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

    const tokens = (await tokenResp.json()) as {
      token_type: string;
      scope: string;
      expires_in: number;
      access_token: string;
      refresh_token: string;
      id_token: string;
    };

    const { refresh_token, id_token } = tokens;
    if (!refresh_token || !id_token) {
      return { props: { ok: false, msg: "Provider did not return refresh_token or id_token" } };
    }

    const idt = decodeJwt(id_token);
    const idNonce = idt.nonce as string | undefined;
    if (!idNonce || idNonce !== nonce) {
      return { props: { ok: false, msg: "Nonce mismatch" } };
    }

    const sub = idt.sub as string | undefined;
    if (!sub) {
      return { props: { ok: false, msg: "Missing sub in id_token" } };
    }

    await dbExec(
      `
INSERT INTO oauth_tokens (openid_sub, provider, refresh_token)
VALUES (?, ?, ?)
ON DUPLICATE KEY UPDATE
  refresh_token = VALUES(refresh_token),
  updated_at = CURRENT_TIMESTAMP
      `,
      [sub, provider, refresh_token]
    );

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

    res.setHeader("Cache-Control", "no-store");
    return {
      props: {
        ok: true,
        msg: `Login complete (${provider}/${product}). You may close this window and return to your CLI.`,
      },
    };
  } catch (e: any) {
    return { props: { ok: false, msg: e?.message ?? "Unexpected error" } };
  }
};

export default function GoogleRedirectPage({ ok, msg }: Props) {
  useEffect(() => {
    if (ok) {
      const id = setTimeout(() => window.close?.(), 1000);
      return () => clearTimeout(id);
    }
  }, [ok]);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>{ok ? "✅ Connected to Google" : "❌ Sign-in failed"}</h1>
      <p>{msg}</p>
    </main>
  );
}

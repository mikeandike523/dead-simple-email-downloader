import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON, getCurrentAccessToken } from "@/server/msgraph";
import lodash from "lodash";
import { decodeJwt } from "jose";
import { z } from "zod";

/** ──────────────────────────────────────────────────────────────
 * Zod schemas (parse + validate raw Graph responses)
 * ──────────────────────────────────────────────────────────────*/

const GraphUserSchema = z.object({
  userPrincipalName: z.string(),
  displayName: z.string(),
  givenName: z.string().optional(),
  surname: z.string().optional(),
  preferredLanguage: z.string().optional(),
  mail: z.string().nullable().optional(),
  mobilePhone: z.string().nullable().optional(),
  jobTitle: z.string().nullable().optional(),
  officeLocation: z.string().nullable().optional(),
  businessPhones: z.array(z.string()).default([]),
  proxyAddresses: z.array(z.string()).default([]),
  otherMails: z.array(z.string()).default([]),
  mailNickname: z.string().nullable().optional(),
});

const MailboxSettingsSchema = z.object({
  timeZone: z.string().optional(),
  language: z.object({
    locale: z.string().optional(),
    displayName: z.string().optional(),
  }).optional(),
  workingHours: z.unknown().optional(),
  automaticRepliesSetting: z.unknown().optional(),
  userPurpose: z.string().optional(),
});

const AccessTokenClaimsSchema = z.object({
  scp: z.string().optional(),
  roles: z.array(z.unknown()).optional(),
  aud: z.string().optional(),
  appid: z.string().optional(),
  tid: z.string().optional(),
  oid: z.string().optional(),
  iss: z.string().optional(),
  ver: z.string().optional(),
  exp: z.number().optional(),
});

/** ──────────────────────────────────────────────────────────────
 * Output types (inferred from schemas where possible)
 * ──────────────────────────────────────────────────────────────*/

export type GraphUserInfo = z.infer<typeof GraphUserSchema>;
export type MailboxSettings = z.infer<typeof MailboxSettingsSchema>;

export interface MailIdentity {
  upn: string;
  primarySmtp: string | null;
  mail: string | null;
  aliases: string[];
  otherMails: string[];
  mailNickname: string | null;
}

export interface GraphUserInfoExtended extends GraphUserInfo {
  mailIdentity: MailIdentity;
  mailboxSettings?: MailboxSettings;
  graphAccessToken?: {
    scopes: string[];
    roles: string[];
    aud?: string;
    appid?: string;
    tid?: string;
    oid?: string;
    iss?: string;
    version?: string;
    expiresAtUtc?: string;
  };
}

/** ──────────────────────────────────────────────────────────────
 * Helpers
 * ──────────────────────────────────────────────────────────────*/

function parseProxyAddresses(proxyAddresses: string[]): {
  primarySmtp: string | null;
  aliases: string[];
} {
  let primarySmtp: string | null = null;
  const aliases: string[] = [];
  for (const addr of proxyAddresses) {
    if (addr.startsWith("SMTP:")) primarySmtp = addr.slice(5);
    else if (addr.startsWith("smtp:")) aliases.push(addr.slice(5));
  }
  return { primarySmtp, aliases };
}

function buildMailIdentity(user: z.infer<typeof GraphUserSchema>): MailIdentity {
  const { primarySmtp, aliases } = parseProxyAddresses(user.proxyAddresses);
  return {
    upn: user.userPrincipalName,
    primarySmtp,
    mail: user.mail ?? null,
    aliases,
    otherMails: user.otherMails,
    mailNickname: user.mailNickname ?? null,
  };
}

const EMPTY_MAIL_IDENTITY: MailIdentity = {
  upn: "",
  primarySmtp: null,
  mail: null,
  aliases: [],
  otherMails: [],
  mailNickname: null,
};

/** ──────────────────────────────────────────────────────────────
 * Handler
 * ──────────────────────────────────────────────────────────────*/

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  const openidSub = req.user.sub;

  const meSelect =
    "userPrincipalName,displayName,givenName,surname,preferredLanguage,mail," +
    "mobilePhone,jobTitle,officeLocation,businessPhones," +
    "proxyAddresses,otherMails,mailNickname";

  const [meResult, mbsResult] = await Promise.all([
    callGraphJSON({ openidSub, route: `me?$select=${encodeURIComponent(meSelect)}` }),
    callGraphJSON({ openidSub, route: "me/mailboxSettings" }),
  ]);

  const result: Partial<GraphUserInfoExtended> & { sub: string } = {
    ...lodash.pick(req.user, ["sub"]),
  };

  // Parse /me response with Zod
  const userParsed = GraphUserSchema.safeParse(meResult.data);
  if (userParsed.success) {
    Object.assign(result, userParsed.data);
    result.mailIdentity = buildMailIdentity(userParsed.data);
  } else {
    result.mailIdentity = EMPTY_MAIL_IDENTITY;
  }

  // Parse mailboxSettings with Zod
  const mbsParsed = MailboxSettingsSchema.safeParse(mbsResult.data);
  if (mbsParsed.success) {
    result.mailboxSettings = mbsParsed.data;
  }

  // Parse access token claims with Zod
  const accessToken = await getCurrentAccessToken(openidSub);
  if (accessToken) {
    try {
      const claimsParsed = AccessTokenClaimsSchema.safeParse(decodeJwt(accessToken));
      if (claimsParsed.success) {
        const c = claimsParsed.data;
        result.graphAccessToken = {
          scopes: c.scp ? c.scp.split(" ").filter(Boolean) : [],
          roles: (c.roles ?? []).map(String),
          aud: c.aud,
          appid: c.appid,
          tid: c.tid,
          oid: c.oid,
          iss: c.iss,
          version: c.ver,
          expiresAtUtc: c.exp !== undefined ? new Date(c.exp * 1000).toISOString() : undefined,
        };
      }
    } catch {
      // malformed token — skip access token info
    }
  }

  return res.status(200).json(result);
};

export default withAuth(handler);

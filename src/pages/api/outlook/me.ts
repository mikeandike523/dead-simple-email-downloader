import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";
import { AuthUser } from "@/server/auth";
import lodash from "lodash";

/** ──────────────────────────────────────────────────────────────
 * Types
 * ──────────────────────────────────────────────────────────────*/

export interface GraphUserInfo {
  userPrincipalName: string;
  displayName: string;
  givenName?: string;
  surname?: string;
  preferredLanguage?: string;
  mail?: string;
  mobilePhone?: string | null;
  jobTitle?: string | null;
  officeLocation?: string | null;
  businessPhones: string[];
}

export interface MailboxSettings {
  timeZone?: string;
  language?: { locale?: string; displayName?: string };
  workingHours?: unknown; // shape varies; keep as unknown unless you need full typing
  automaticRepliesSetting?: unknown; // same here
  userPurpose?: string; // e.g. "user", "shared", "room", etc.
}

export interface MailIdentity {
  /** Sign-in identity and addresses */
  upn: string; // userPrincipalName
  primarySmtp?: string | null; // derived from proxyAddresses ("SMTP:")
  mail?: string | null; // Graph "mail" (primary SMTP as reported)
  aliases: string[]; // secondary smtp: addresses (lowercase)
  otherMails: string[]; // non-alias or extra emails
  mailNickname?: string | null;
}

export interface GraphUserInfoExtended extends GraphUserInfo {
  mailIdentity: MailIdentity;
  mailboxSettings?: MailboxSettings;
}

/** Raw Graph response type (very loose) */
type RawGraphUser = Record<string, any>;
type RawMailboxSettings = Record<string, any>;

/** ──────────────────────────────────────────────────────────────
 * Mappers
 * ──────────────────────────────────────────────────────────────*/

function parseProxyAddresses(raw: any): {
  primarySmtp: string | null;
  aliases: string[];
} {
  const list = Array.isArray(raw) ? raw : [];
  let primary: string | null = null;
  const aliases: string[] = [];

  for (const addr of list) {
    if (typeof addr !== "string") continue;
    // Graph returns "SMTP:primary@contoso.com" | "smtp:alias@contoso.com"
    if (addr.startsWith("SMTP:")) {
      primary = addr.slice(5);
    } else if (addr.startsWith("smtp:")) {
      aliases.push(addr.slice(5));
    }
  }
  return { primarySmtp: primary, aliases };
}

/** Keep your original mapper for general profile fields */
export function mapGraphUserInfo(raw: RawGraphUser): GraphUserInfo {
  return {
    userPrincipalName: raw.userPrincipalName,
    displayName: raw.displayName,
    givenName: raw.givenName,
    surname: raw.surname,
    preferredLanguage: raw.preferredLanguage,
    mail: raw.mail,
    mobilePhone: raw.mobilePhone ?? null,
    jobTitle: raw.jobTitle ?? null,
    officeLocation: raw.officeLocation ?? null,
    businessPhones: Array.isArray(raw.businessPhones) ? raw.businessPhones : [],
  };
}

/** New: build the mailIdentity block */
function mapMailIdentity(raw: RawGraphUser): MailIdentity {
  const { primarySmtp, aliases } = parseProxyAddresses(raw.proxyAddresses);
  return {
    upn: raw.userPrincipalName,
    primarySmtp,
    mail: raw.mail ?? null,
    aliases,
    otherMails: Array.isArray(raw.otherMails) ? raw.otherMails : [],
    mailNickname: raw.mailNickname ?? null,
  };
}

function mapMailboxSettings(raw: RawMailboxSettings): MailboxSettings {
  if (!raw || typeof raw !== "object") return {};
  const {
    timeZone,
    language,
    workingHours,
    automaticRepliesSetting,
    userPurpose,
  } = raw;
  return {
    timeZone,
    language,
    workingHours,
    automaticRepliesSetting,
    userPurpose,
  };
}

/** ──────────────────────────────────────────────────────────────
 * Handler
 * ──────────────────────────────────────────────────────────────*/

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  const openidSub = req.user.sub;

  // 1) Pull user with all the mail-identity fields we care about.
  //    No extra scope needed beyond User.Read.
  const meSelect =
    "userPrincipalName,displayName,givenName,surname,preferredLanguage,mail," +
    "mobilePhone,jobTitle,officeLocation,businessPhones," +
    // mail identity fields:
    "proxyAddresses,otherMails,mailNickname";

  const meResult = await callGraphJSON({
    openidSub,
    route: `me?$select=${encodeURIComponent(meSelect)}`,
  });

  // 2) Optionally pull mailboxSettings (requires MailboxSettings.Read).
  const mbsResult = await callGraphJSON({
    openidSub,
    route: "me/mailboxSettings",
  });

  // Start with auth claims you already expose
  const result: Partial<AuthUser & GraphUserInfoExtended> = {
    ...lodash.pick(req.user, ["sub"]),
  };

  if (meResult.ok && meResult.data && typeof meResult.data === "object") {
    const user = meResult.data as RawGraphUser;
    Object.assign(result, mapGraphUserInfo(user));
    (result as GraphUserInfoExtended).mailIdentity = mapMailIdentity(user);
  } else {
    // Ensure the shape exists even if /me fails for some reason
    (result as any).mailIdentity = {
      upn: "",
      primarySmtp: null,
      mail: null,
      aliases: [],
      otherMails: [],
      mailNickname: null,
    } as MailIdentity;
  }

  if (mbsResult.ok && mbsResult.data && typeof mbsResult.data === "object") {
    (result as GraphUserInfoExtended).mailboxSettings = mapMailboxSettings(
      mbsResult.data as RawMailboxSettings
    );
  }

  return res.status(200).json(result);
};

export default withAuth(handler);

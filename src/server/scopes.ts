export type Provider = "exchange" | "google";
export type Product = "outlook" | "teams" | "gmail" | "drive";

export const PRODUCT_SCOPES: Record<Provider, Partial<Record<Product, string[]>>> = {
  exchange: {
    outlook: [
      "openid",
      "offline_access",
      "User.Read",
      "Mail.Read",
      "Mail.ReadWrite",
      "Mail.Read.Shared",
      "Mail.ReadWrite.Shared",
    ],
    teams: [
      "openid",
      "offline_access",
      "User.Read",
      "Chat.Read",
    ],
  },
  google: {
    gmail: [
      "openid",
      "email",
      "profile",
      "https://www.googleapis.com/auth/gmail.readonly",
      "https://www.googleapis.com/auth/gmail.modify",
    ],
    drive: [
      "openid",
      "email",
      "profile",
      "https://www.googleapis.com/auth/drive.readonly",
    ],
  },
};

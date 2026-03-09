export type Provider = "exchange";
export type Product = "outlook" | "teams";

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
};

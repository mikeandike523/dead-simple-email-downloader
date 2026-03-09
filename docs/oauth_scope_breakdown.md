# OAuth Scope Breakdown by Provider and Product

## Overview

The authentication system uses **incremental consent**: each product requests only
the scopes it needs. A single refresh token per `(openid_sub, provider)` accumulates
all scopes granted across logins. Access tokens are scoped per `(openid_sub, provider, product)`.

---

## Provider: `exchange` (Microsoft 365 / Azure AD)

**Refresh token key:** `(openid_sub, "exchange")`
**Access token key:** `(openid_sub, "exchange", <product>)`

One Azure AD app registration serves all Exchange products. Incremental consent
means the user sees only the scopes for the product they are logging into.

### Product: `outlook`

Requested at: `dsed exchange outlook login`

| Scope | Purpose |
|---|---|
| `openid` | Required for OpenID Connect `id_token` |
| `offline_access` | Required for refresh tokens (persistent auth) |
| `User.Read` | Read profile info (`/me` endpoint) |
| `Mail.Read` | Read messages in user's mailbox |
| `Mail.ReadWrite` | Move messages to trash, update read flags |
| `Mail.Read.Shared` | Access shared / delegated mailboxes (read) |
| `Mail.ReadWrite.Shared` | Access shared / delegated mailboxes (write) |

**Admin consent required:** No — all scopes are user-consented delegated permissions.

---

### Product: `teams`

Requested at: `dsed exchange teams login`
_(Not yet implemented — stub for future work)_

| Scope | Purpose |
|---|---|
| `openid` | Required for OpenID Connect `id_token` |
| `offline_access` | Required for refresh tokens |
| `User.Read` | Read profile info |
| `Chat.Read` | Read Teams 1:1 and group chat messages |

**Admin consent required:** No — `Chat.Read` is a user-consented delegated permission.

**Note:** `ChannelMessage.Read.All` (to read channel/team messages) _does_ require
admin consent in most organizational tenants and is therefore excluded from the
default scope set. It can be added to `src/server/scopes.ts` once admin consent
is confirmed for a target tenant.

---

## Incremental consent behaviour

When a user runs `dsed exchange outlook login` followed later by
`dsed exchange teams login`:

1. **First login** — Azure AD issues a refresh token covering Outlook scopes.
   Stored in `oauth_tokens` as `(sub, "exchange")`.
2. **Second login** — Azure AD updates the same logical grant; the new refresh
   token covers both Outlook and Teams scopes. The `oauth_tokens` row is upserted
   in-place (same `(sub, "exchange")` key).
3. Access tokens are obtained separately per product by passing the relevant scope
   string when calling `ensureAccessToken`.

---

## Future providers

| Provider key | Service | Notes |
|---|---|---|
| `google-workspace` | Google Gmail, Chat | Requires separate OAuth app (Google Identity) |

When a Google provider is added:
- New rows in `oauth_tokens` with `provider = "google-workspace"`
- New rows in `access_tokens` with `provider = "google-workspace"`, `product = "gmail"` etc.
- New auth routes at `src/pages/api/auth/google-workspace/get-url.ts` etc.
- New redirect page at `src/pages/auth/google-workspace/redirect.tsx`

# Database Migration: Provider/Product Schema

This migration adds `provider` and `product` columns to support incremental OAuth
and multiple future providers (e.g. Google Workspace).

**Run these statements in order.** The `DEFAULT` values ensure existing rows
continue working without any code change during the transition.

---

## Step 1 — Add columns with safe defaults

```sql
-- oauth_tokens: add provider (one refresh token per user per OAuth provider)
ALTER TABLE oauth_tokens
  ADD COLUMN provider VARCHAR(64) NOT NULL DEFAULT 'exchange' AFTER openid_sub;

-- access_tokens: add provider + product (one access token per user/provider/product combo)
ALTER TABLE access_tokens
  ADD COLUMN provider VARCHAR(64) NOT NULL DEFAULT 'exchange' AFTER openid_sub,
  ADD COLUMN product  VARCHAR(64) NOT NULL DEFAULT 'outlook'  AFTER provider;

-- pending_logins: track which provider/product a pending login is for
ALTER TABLE pending_logins
  ADD COLUMN provider VARCHAR(64) NOT NULL DEFAULT 'exchange' AFTER poll_token,
  ADD COLUMN product  VARCHAR(64) NOT NULL DEFAULT 'outlook'  AFTER provider;
```

## Step 2 — Update primary keys to composite keys

```sql
-- oauth_tokens: was PK(openid_sub), now PK(openid_sub, provider)
ALTER TABLE oauth_tokens
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (openid_sub, provider);

-- access_tokens: was PK(openid_sub), now PK(openid_sub, provider, product)
ALTER TABLE access_tokens
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (openid_sub, provider, product);
```

## Step 3 — Verify

```sql
DESCRIBE oauth_tokens;
-- Expected columns: openid_sub | provider | refresh_token | updated_at
-- PK: (openid_sub, provider)

DESCRIBE access_tokens;
-- Expected columns: openid_sub | provider | product | access_token | expires_at
-- PK: (openid_sub, provider, product)

DESCRIBE pending_logins;
-- Expected columns: poll_token | provider | product | ok | openid_sub | touched_at
```

---

## Azure App Registration change

Update the OAuth redirect URI in the Azure portal:

1. Go to **App registrations → your app → Authentication**
2. Under the **Web** platform, find the current redirect URI
3. Set the redirect URI to `…/auth/exchange/redirect`
4. **Save**
5. Update your `.env` file:
   ```
   AZURE_OAUTH_REDIRECT_URL=http://localhost:3000/auth/exchange/redirect
   ```
   (adjust to your actual host/port for production)

> **Tip:** During the transition, add the new URI as a second entry rather than
> replacing the old one. Once all sessions have re-logged in via the new path,
> remove the old entry.

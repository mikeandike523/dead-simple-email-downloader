CREATE DATABASE IF NOT EXISTS appdb;
USE appdb;


CREATE TABLE oauth_tokens (
    openid_sub VARCHAR(255) NOT NULL,
    provider   VARCHAR(64)  NOT NULL DEFAULT 'exchange',
    refresh_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (openid_sub, provider)
);

CREATE TABLE access_tokens (
    openid_sub    VARCHAR(255) NOT NULL,
    provider      VARCHAR(64)  NOT NULL DEFAULT 'exchange',
    product       VARCHAR(64)  NOT NULL DEFAULT 'outlook',
    access_token  TEXT NOT NULL,
    expires_at    TIMESTAMP NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (openid_sub, provider, product)
);

-- Allows CLIs to poll the login state
-- Each new login request creates a unique poll_token (akin to CSRF token)
-- A cron job will be made later to clean up completed or stranded poll_tokens
CREATE TABLE email_categories (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,   -- stored lowercase
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE email_category_assignments (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    provider     VARCHAR(50)   NOT NULL,
    product      VARCHAR(50)   NOT NULL,
    message_id   VARCHAR(255)  NOT NULL,
    category_id  INT           NOT NULL,
    openid_sub   VARCHAR(255)  NOT NULL,
    -- Stored at categorization time from provider preview APIs (never full body).
    -- Application always truncates before writing; VARCHAR limit is a schema contract.
    subject      VARCHAR(256)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    body_preview VARCHAR(512)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    assigned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_msg_cat (provider, product, message_id, category_id),
    FOREIGN KEY (category_id) REFERENCES email_categories(id)
);

CREATE TABLE pending_logins (
    poll_token CHAR(36)     NOT NULL,
    provider   VARCHAR(64)  NOT NULL DEFAULT 'exchange',
    product    VARCHAR(64)  NOT NULL DEFAULT 'outlook',

    -- Flag set true once the redirect lands and tokens were saved
    ok BOOLEAN NOT NULL DEFAULT FALSE,

    -- The openid_sub of the user who completed the login so we can return a signed JWT
    openid_sub VARCHAR(255) NULL,

    -- When created + when touched
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    touched_at TIMESTAMP NULL,

    PRIMARY KEY (poll_token)
);

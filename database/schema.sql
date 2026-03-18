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

CREATE TABLE email_categories (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,   -- stored lowercase
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Primary entity: identity + content snapshot of an email we have processed.
-- Reused across sessions via the unique key — content does not change between triage runs.
-- Application always truncates text fields before writing; VARCHAR limits are schema contracts.
CREATE TABLE email_content (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    provider     VARCHAR(50)   NOT NULL,
    product      VARCHAR(50)   NOT NULL,
    message_id   VARCHAR(255)  NOT NULL,
    openid_sub   VARCHAR(255)  NOT NULL,
    subject      VARCHAR(256)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    body_preview VARCHAR(512)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    from_address VARCHAR(512)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    seen_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_email_content (provider, product, message_id, openid_sub)
);

-- Category assigned to an email. Peer of email_actions — neither is primary.
CREATE TABLE email_category_assignments (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    email_content_id INT NOT NULL,
    category_id      INT NOT NULL,
    assigned_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_assignment (email_content_id, category_id),
    FOREIGN KEY (email_content_id) REFERENCES email_content(id),
    FOREIGN KEY (category_id)      REFERENCES email_categories(id)
);

-- Disposition taken on an email (hard delete, soft delete, move, kept in inbox).
-- Peer of email_category_assignments — both reference email_content.
CREATE TABLE email_actions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    email_content_id INT          NOT NULL,
    action           ENUM('hard_delete', 'soft_delete', 'move', 'inbox') NOT NULL,
    label_id         VARCHAR(255) NULL,
    label_name       VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    acted_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_content_id) REFERENCES email_content(id)
);

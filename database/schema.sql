CREATE DATABASE IF NOT EXISTS appdb;
USE appdb;

CREATE TABLE oauth_tokens (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    openid_sub VARCHAR(255) NOT NULL UNIQUE,
    refresh_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Allows CLIs to poll the logins state
-- Each new login request creates a unique poll_token (akin to CSRF token)
-- A cron job will be made later to clean up completed or stranded poll_tokens
CREATE TABLE pending_logins (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- Opaque secret the CLI uses for polling (e.g., UUIDv4)
    poll_token CHAR(36) NOT NULL UNIQUE,

    -- Flag set true once the redirect lands and tokens were saved
    ok BOOLEAN NOT NULL DEFAULT FALSE,

    -- The openid_sub of the user who completed the login so we can return a signed JWT
    openid_sub VARCHAR(255) NULL,

    -- When created + when touched
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    touched_at TIMESTAMP NULL
);
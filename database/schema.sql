CREATE DATABASE IF NOT EXISTS appdb;
USE appdb;

CREATE TABLE oauth_tokens (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    openid_sub VARCHAR(255) NOT NULL UNIQUE,
    refresh_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE pending_logins (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- Opaque secret the CLI uses for polling (e.g., UUIDv4)
    poll_token CHAR(36) NOT NULL UNIQUE,

    -- Flag set true once the redirect lands and tokens were saved
    ok BOOLEAN NOT NULL DEFAULT FALSE,

    -- When created + when touched
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    touched_at TIMESTAMP NULL
);
CREATE TABLE canvas_api_connections_platform (
    user_id UUID PRIMARY KEY REFERENCES users_platform(id) ON DELETE CASCADE,
    canvas_origin TEXT NOT NULL,
    token_nonce BYTEA NOT NULL,
    token_ciphertext BYTEA NOT NULL,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

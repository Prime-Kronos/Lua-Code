CREATE TABLE IF NOT EXISTS topdim_submissions (
  id UUID PRIMARY KEY,
  title VARCHAR(60) NOT NULL,
  category VARCHAR(30) NOT NULL,
  kind VARCHAR(12) NOT NULL CHECK (kind IN ('Потеряно','Найдено')),
  area VARCHAR(80) NOT NULL,
  item_date DATE NOT NULL,
  description VARCHAR(240) NOT NULL,
  photo_data BYTEA NOT NULL,
  photo_mime VARCHAR(40) NOT NULL DEFAULT 'image/webp',
  status VARCHAR(12) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS topdim_submissions_public_idx
  ON topdim_submissions (created_at DESC) WHERE status = 'approved';
CREATE INDEX IF NOT EXISTS topdim_submissions_review_idx
  ON topdim_submissions (created_at ASC) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS topdim_rate_limits (
  bucket_key CHAR(64) NOT NULL,
  action VARCHAR(32) NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  hits INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (bucket_key, action, window_start)
);
CREATE INDEX IF NOT EXISTS topdim_rate_limits_cleanup_idx
  ON topdim_rate_limits (window_start);
CREATE TABLE IF NOT EXISTS topdim_audit_log (
  id BIGSERIAL PRIMARY KEY,
  event VARCHAR(40) NOT NULL,
  submission_id UUID,
  actor VARCHAR(40) NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS topdim_audit_created_idx
  ON topdim_audit_log (created_at DESC);

CREATE TABLE IF NOT EXISTS topdim_admins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash CHAR(128) NOT NULL,
  password_salt CHAR(32) NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('owner','moderator')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS topdim_admin_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_id UUID NOT NULL REFERENCES topdim_admins(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  csrf_token VARCHAR(64) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS topdim_admin_sessions_expiry_idx ON topdim_admin_sessions(expires_at);

-- migrate: apply
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS session_type TEXT NOT NULL DEFAULT 'general';

-- migrate: rollback
ALTER TABLE sessions DROP COLUMN IF EXISTS session_type;

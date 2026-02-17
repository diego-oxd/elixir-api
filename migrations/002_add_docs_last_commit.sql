-- migrate: apply
ALTER TABLE projects ADD COLUMN IF NOT EXISTS docs_last_commit VARCHAR(40);

-- migrate: rollback
ALTER TABLE projects DROP COLUMN IF EXISTS docs_last_commit;

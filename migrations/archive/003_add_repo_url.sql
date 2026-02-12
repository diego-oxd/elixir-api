-- Migration: Add repo_url column to projects table
-- This stores the original GitHub URL for repositories added via add-repo endpoint

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS repo_url VARCHAR(500) NULL;

-- Add index for efficient lookups by URL
CREATE INDEX IF NOT EXISTS idx_projects_repo_url ON projects(repo_url);

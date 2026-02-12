-- Add markdown_content column to pages table for storing raw markdown
-- This allows overview and frontend pages to store markdown directly
-- instead of wrapping it in JSONB, avoiding encoding/escaping issues

ALTER TABLE pages ADD COLUMN markdown_content TEXT;

-- Add comment to clarify usage
COMMENT ON COLUMN pages.markdown_content IS 'Raw markdown content for overview and frontend pages. Mutually exclusive with structured content field.';

# Archived Migrations

This directory contains migration files that have been incorporated into the baseline schema (`001_initial_schema.sql`).

## Archived Files

### 003_add_repo_url.sql
- **Date Applied**: Before schema consolidation
- **Purpose**: Added `repo_url` column to `projects` table
- **Status**: Incorporated into `001_initial_schema.sql`

### 004_add_markdown_content_column.sql
- **Date Applied**: Before schema consolidation
- **Purpose**: Added `markdown_content` column to `pages` table
- **Status**: Incorporated into `001_initial_schema.sql`

## Why These Are Archived

When we implemented the yoyo-migrations system, we consolidated all existing schema changes into a single baseline migration file (`001_initial_schema.sql`). This file includes all changes from these archived migrations.

These files are kept for historical reference only and should not be applied to any database.

## For New Developers

If you're setting up the database for the first time:
1. Run `docker-compose up -d` to initialize the database with the current schema
2. The `init_db.sql` script will create all tables with the latest structure
3. No need to run these archived migrations

## For Existing Installations

Existing databases should already have these changes applied. The yoyo-migrations system tracks which migrations have been run, so you don't need to worry about duplicate applications.

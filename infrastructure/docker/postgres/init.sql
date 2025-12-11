-- =============================================================================
-- PostgreSQL Initialization Script
-- =============================================================================
-- This script runs when the PostgreSQL container is first created.
-- It sets up any required extensions.
-- =============================================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Grant permissions (if needed for specific schemas)
-- GRANT ALL PRIVILEGES ON DATABASE contribution_matcher TO postgres;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL initialized for Contribution Matcher';
END $$;

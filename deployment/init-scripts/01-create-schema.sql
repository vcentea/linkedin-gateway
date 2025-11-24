-- ============================================================================
-- LinkedIn Gateway Complete Database Schema
-- ============================================================================
-- This script creates all tables, indexes, and constraints needed for the application
-- Replaces Alembic migrations for deployment simplicity
-- ============================================================================

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search performance

-- Set timezone
SET timezone = 'UTC';

-- ============================================================================
-- BILLING TABLES
-- ============================================================================

-- Billing Tiers (Subscription levels)
CREATE TABLE IF NOT EXISTS billing_tiers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    monthly_price NUMERIC(10, 2),
    api_calls_limit VARCHAR(255),
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    tier_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_billing_tiers_monthly_price ON billing_tiers(monthly_price);
CREATE INDEX IF NOT EXISTS ix_billing_tiers_is_active ON billing_tiers(is_active);

-- ============================================================================
-- USER TABLES
-- ============================================================================

-- Users (Main user table)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Authentication fields
    linkedin_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    profile_picture_url TEXT,
    password_hash VARCHAR(255),  -- For local auth (NULL for OAuth users)
    -- OAuth tokens
    access_token VARCHAR(512),
    refresh_token VARCHAR(512),
    token_expires_at TIMESTAMP WITH TIME ZONE,
    -- Subscription info
    subscription_type VARCHAR(100),
    subscription_start TIMESTAMP WITH TIME ZONE,
    subscription_end TIMESTAMP WITH TIME ZONE,
    billing_tier_id UUID REFERENCES billing_tiers(id),
    -- Usage tracking
    last_activity TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    api_calls_today INTEGER DEFAULT 0,
    api_calls_monthly INTEGER DEFAULT 0,
    last_api_reset TIMESTAMP WITH TIME ZONE,
    -- Status info
    is_active BOOLEAN DEFAULT TRUE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    role VARCHAR(50),
    -- Additional data
    user_metadata JSONB DEFAULT '{}',
    my_linkedin_profile_id VARCHAR(255),  -- Cached own profile ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_linkedin_id ON users(linkedin_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_billing_tier_id ON users(billing_tier_id);
CREATE INDEX IF NOT EXISTS ix_users_last_activity ON users(last_activity);
CREATE INDEX IF NOT EXISTS ix_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS ix_users_my_linkedin_profile_id ON users(my_linkedin_profile_id);

-- User Sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE,
    device_info JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS ix_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS ix_user_sessions_last_activity ON user_sessions(last_activity);

-- User Subscriptions
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    billing_tier_id UUID NOT NULL REFERENCES billing_tiers(id),
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) NOT NULL,
    payment_method_id VARCHAR(255),
    auto_renew BOOLEAN DEFAULT TRUE,
    subscription_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_subscriptions_billing_tier_id ON user_subscriptions(billing_tier_id);
CREATE INDEX IF NOT EXISTS ix_user_subscriptions_start_date ON user_subscriptions(start_date);
CREATE INDEX IF NOT EXISTS ix_user_subscriptions_end_date ON user_subscriptions(end_date);
CREATE INDEX IF NOT EXISTS ix_user_subscriptions_status ON user_subscriptions(status);

-- Billing History
CREATE TABLE IF NOT EXISTS billing_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES user_subscriptions(id) ON DELETE CASCADE,
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(50) NOT NULL,
    payment_method VARCHAR(50),
    transaction_id VARCHAR(255),
    billing_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_billing_history_user_id ON billing_history(user_id);
CREATE INDEX IF NOT EXISTS ix_billing_history_subscription_id ON billing_history(subscription_id);
CREATE INDEX IF NOT EXISTS ix_billing_history_status ON billing_history(status);
CREATE INDEX IF NOT EXISTS ix_billing_history_transaction_id ON billing_history(transaction_id);

-- ============================================================================
-- API KEY TABLES
-- ============================================================================

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prefix VARCHAR(16) NOT NULL UNIQUE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    description TEXT,
    csrf_token VARCHAR(255),
    linkedin_cookies JSONB DEFAULT '{}',
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_config JSONB DEFAULT '{}',
    permissions JSONB DEFAULT '{}',
    api_metadata JSONB DEFAULT '{}',
    -- Webhook configuration (v1.1.0)
    webhook_url VARCHAR(1024),
    webhook_headers JSONB DEFAULT '{}' NOT NULL,
    -- Multi-key support (v1.1.0)
    instance_id VARCHAR(255),
    instance_name VARCHAR(255),
    browser_info JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_prefix ON api_keys(prefix);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS ix_api_keys_is_active ON api_keys(is_active);
-- Multi-key support indexes (v1.1.0)
CREATE INDEX IF NOT EXISTS ix_api_keys_instance ON api_keys(user_id, instance_id, is_active);
CREATE INDEX IF NOT EXISTS ix_api_keys_user_active ON api_keys(user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_api_keys_last_used ON api_keys(last_used_at DESC NULLS LAST);

-- Add comments for multi-key columns
COMMENT ON COLUMN api_keys.instance_id IS 'Unique identifier for extension instance (e.g., chrome_1699123456789_a9b8c7d6)';
COMMENT ON COLUMN api_keys.instance_name IS 'User-friendly name for the extension instance (e.g., "Chrome - Windows")';
COMMENT ON COLUMN api_keys.browser_info IS 'JSON metadata about browser: {browser, version, os, platform}';

-- Rate Limits
CREATE TABLE IF NOT EXISTS rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    max_requests VARCHAR(255) NOT NULL,
    time_window VARCHAR(255) NOT NULL,
    current_requests VARCHAR(255) DEFAULT '0',
    last_reset TIMESTAMP WITH TIME ZONE,
    rate_limit_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rate_limits_api_key_id ON rate_limits(api_key_id);
CREATE INDEX IF NOT EXISTS ix_rate_limits_endpoint ON rate_limits(endpoint);
CREATE INDEX IF NOT EXISTS ix_rate_limits_last_reset ON rate_limits(last_reset);

-- API Usage Logs
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code VARCHAR(255),
    response_time VARCHAR(255),
    request_metadata JSONB DEFAULT '{}',
    response_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_api_usage_logs_api_key_id ON api_usage_logs(api_key_id);
CREATE INDEX IF NOT EXISTS ix_api_usage_logs_user_id ON api_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_api_usage_logs_endpoint ON api_usage_logs(endpoint);
CREATE INDEX IF NOT EXISTS ix_api_usage_logs_status_code ON api_usage_logs(status_code);

-- ============================================================================
-- LINKEDIN DATA TABLES
-- ============================================================================

-- Profiles (LinkedIn profiles)
CREATE TABLE IF NOT EXISTS profiles (
    id SERIAL PRIMARY KEY,
    linkedin_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    jobtitle VARCHAR(255),
    about TEXT,
    industry VARCHAR(255),
    company VARCHAR(255),
    location VARCHAR(255),
    skills TEXT,
    courses TEXT[],
    certifications TEXT[],
    department VARCHAR(255),
    level VARCHAR(255),
    vanity_name VARCHAR(255),
    areasofinterest TEXT,
    positions JSONB,
    education JSONB,
    languages JSONB,
    profile_url TEXT,
    profile_score FLOAT,
    full_info_scraped BOOLEAN DEFAULT FALSE,
    writing_style TEXT,
    personality TEXT,
    strengths TEXT,
    keywords TEXT[],
    added_by_userid UUID REFERENCES users(id),
    recommendations TEXT[],
    last_20_posts TEXT[],
    last_20_comments TEXT[],
    highlighted_posts JSONB[],
    commentators_list TEXT[],
    reactors_list TEXT[],
    profile_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_profiles_linkedin_id ON profiles(linkedin_id);
CREATE INDEX IF NOT EXISTS ix_profiles_industry ON profiles(industry);
CREATE INDEX IF NOT EXISTS ix_profiles_company ON profiles(company);
CREATE INDEX IF NOT EXISTS ix_profiles_location ON profiles(location);
CREATE INDEX IF NOT EXISTS ix_profiles_vanity_name ON profiles(vanity_name);
CREATE INDEX IF NOT EXISTS ix_profiles_added_by_userid ON profiles(added_by_userid);

-- Posts (LinkedIn posts)
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    postid VARCHAR(255) UNIQUE,
    ugcpostid VARCHAR(255),
    url TEXT,
    snippet TEXT,
    author_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    reactions INTEGER,
    comments INTEGER,
    reposts INTEGER,
    engagement INTEGER,
    postcontent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    shareurn VARCHAR(255),
    post_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_posts_postid ON posts(postid);
CREATE INDEX IF NOT EXISTS ix_posts_author_id ON posts(author_id);
CREATE INDEX IF NOT EXISTS ix_posts_reactions ON posts(reactions);
CREATE INDEX IF NOT EXISTS ix_posts_comments ON posts(comments);
CREATE INDEX IF NOT EXISTS ix_posts_engagement ON posts(engagement);
CREATE INDEX IF NOT EXISTS ix_posts_timestamp ON posts(timestamp);

-- User-Post mapping (many-to-many)
CREATE TABLE IF NOT EXISTS user_post_mapping (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE,
    relevance_score INTEGER,
    relevance_data JSONB,
    PRIMARY KEY (user_id, post_id)
);

-- Message Histories
CREATE TABLE IF NOT EXISTS message_histories (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT,
    message_type VARCHAR(50),
    timestamp TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL,
    message_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_message_histories_profile_id ON message_histories(profile_id);
CREATE INDEX IF NOT EXISTS ix_message_histories_user_id ON message_histories(user_id);
CREATE INDEX IF NOT EXISTS ix_message_histories_message_type ON message_histories(message_type);
CREATE INDEX IF NOT EXISTS ix_message_histories_timestamp ON message_histories(timestamp);
CREATE INDEX IF NOT EXISTS ix_message_histories_status ON message_histories(status);

-- Connection Requests
CREATE TABLE IF NOT EXISTS connection_requests (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    connection_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL,
    connection_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_connection_requests_user_id ON connection_requests(user_id);
CREATE INDEX IF NOT EXISTS ix_connection_requests_profile_id ON connection_requests(profile_id);
CREATE INDEX IF NOT EXISTS ix_connection_requests_timestamp ON connection_requests(timestamp);
CREATE INDEX IF NOT EXISTS ix_connection_requests_status ON connection_requests(status);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to all tables
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        AND table_name != 'user_post_mapping'  -- Skip junction table
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS update_%I_updated_at ON %I', t, t);
        EXECUTE format('CREATE TRIGGER update_%I_updated_at 
                       BEFORE UPDATE ON %I 
                       FOR EACH ROW 
                       EXECUTE FUNCTION update_updated_at_column()', t, t);
    END LOOP;
END;
$$ language 'plpgsql';

-- ============================================================================
-- INITIAL DATA (Optional - for testing)
-- ============================================================================

-- Insert a default billing tier for testing
INSERT INTO billing_tiers (name, description, monthly_price, api_calls_limit, is_active)
VALUES ('Free', 'Free tier with basic features', 0.00, '1000', TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- GRANTS (Set appropriate permissions)
-- ============================================================================

-- NOTE: Permissions are automatically handled by PostgreSQL Docker image!
-- 
-- How it works:
-- 1. Docker creates user from POSTGRES_USER env var (e.g., linkedin_gateway_user)
-- 2. Docker creates database from POSTGRES_DB env var (e.g., LinkedinGateway)
-- 3. The POSTGRES_USER becomes the database owner with full privileges
-- 4. This init script runs AS that user, so all created objects belong to them
-- 5. No additional grants needed - the user owns everything!
--
-- The application connects with the same DB_USER credentials and has full access.

-- Verification: Show current user and database
SELECT 
    current_user AS "Script running as",
    current_database() AS "In database";

-- Verification: Show user privileges
SELECT 
    grantee, 
    privilege_type 
FROM information_schema.table_privileges 
WHERE grantee = current_user 
LIMIT 5;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Show all tables created
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Show all indexes created
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;


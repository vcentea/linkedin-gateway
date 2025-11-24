-- Grant all privileges on database
ALTER DATABASE "LinkedinGateway" OWNER TO linkedin_gateway_user;

-- Grant all privileges on schema
GRANT ALL ON SCHEMA public TO linkedin_gateway_user;

-- Grant all privileges on all tables in schema public
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO linkedin_gateway_user;

-- Grant all privileges on all sequences in schema public
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO linkedin_gateway_user;

-- Grant all privileges on all functions in schema public
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO linkedin_gateway_user;

-- Make sure the user can create new tables
GRANT CREATE ON SCHEMA public TO linkedin_gateway_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO linkedin_gateway_user;

-- Set default privileges for future sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO linkedin_gateway_user;

-- Set default privileges for future functions
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON FUNCTIONS TO linkedin_gateway_user; 
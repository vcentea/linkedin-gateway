#!/usr/bin/env pwsh
<#
    Update LinkedIn Gateway from v1.0.x to v1.1.0 (PowerShell version)
    Mirrors deployment/scripts/update-to-v1.1.sh for Windows environments.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptRoot '..\..')).Path

if (-not (Test-Path (Join-Path $projectRoot 'backend\main.py'))) {
    Write-Host 'ERROR: This script must be run from the deployment\scripts directory'
    Write-Host "Current directory: $PWD"
    exit 1
}

Write-Host '============================================'
Write-Host 'LinkedIn Gateway - Update to v1.1.0'
Write-Host '============================================'
Write-Host ''
Write-Host 'This will update your existing installation to v1.1.0'
Write-Host 'New features:'
Write-Host '  - Multi-key support (multiple API keys per user)'
Write-Host '  - Instance tracking (track different browser instances)'
Write-Host '  - Backend version compatibility checking'
Write-Host ''
Write-Host 'Database changes:'
Write-Host '  - Add instance_id, instance_name, browser_info columns to api_keys'
Write-Host '  - Add webhook_url and webhook_headers columns for per-key webhooks'
Write-Host '  - Add indexes for multi-key performance'
Write-Host '  - Backward compatible (existing keys continue working)'
Write-Host ''

Write-Host 'Step 1: Checking PostgreSQL connection...'
Write-Host ''

$envFilePath = $null
$backendEnv = Join-Path $projectRoot 'backend\.env'
$deploymentEnv = Join-Path $scriptRoot '..\.env'

Write-Host 'Searching for .env file...'
if (Test-Path $backendEnv) {
    $envFilePath = $backendEnv
    Write-Host '✓ Found: backend\.env'
} elseif (Test-Path $deploymentEnv) {
    $envFilePath = (Resolve-Path $deploymentEnv)
    Write-Host '✓ Found: deployment\.env'
} else {
    Write-Host '✗ No .env file found in backend\ or deployment\'
    Write-Host 'Using defaults: localhost:5432/linkedin_gateway'
    $env:DB_USER = 'postgres'
    $env:DB_PASSWORD = 'postgres'
    $env:DB_NAME = 'linkedin_gateway'
    $env:DB_HOST = 'localhost'
    $env:DB_PORT = '5432'
}

if ($envFilePath) {
    Get-Content -Path $envFilePath | ForEach-Object {
        if ($_ -match '^\s*#') { return }
        if ($_ -match '^\s*(DB_[A-Z0-9_]+)\s*=\s*(.*)\s*$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim('"').Trim("'")
            switch ($key) {
                'DB_USER'       { $env:DB_USER = $value }
                'DB_PASSWORD'   { $env:DB_PASSWORD = $value }
                'DB_NAME'       { $env:DB_NAME = $value }
                'DB_HOST'       { $env:DB_HOST = $value }
                'DB_PORT'       { $env:DB_PORT = $value }
                'DB_SUPERUSER'  { $env:DB_SUPERUSER = $value }
                'DB_SUPERUSER_PASSWORD' { $env:DB_SUPERUSER_PASSWORD = $value }
                'DB_SCHEMA'     { $env:DB_SCHEMA = $value }
            }
        }
    }
}

$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { 'postgres' }
$DB_PASSWORD = if ($env:DB_PASSWORD) { $env:DB_PASSWORD } else { 'postgres' }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { 'linkedin_gateway' }
$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { 'localhost' }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { '5432' }
$DB_SCHEMA = if ($env:DB_SCHEMA) { $env:DB_SCHEMA } else { 'public' }

$DB_SUPERUSER = if ($env:DB_SUPERUSER) { $env:DB_SUPERUSER } else { $DB_USER }
$DB_SUPERUSER_PASSWORD = if ($env:DB_SUPERUSER_PASSWORD) { $env:DB_SUPERUSER_PASSWORD }
if (-not $DB_SUPERUSER_PASSWORD -and $DB_SUPERUSER -eq $DB_USER) {
    $DB_SUPERUSER_PASSWORD = $DB_PASSWORD
}

Write-Host ''
Write-Host 'Using PostgreSQL configuration:'
Write-Host "  Host: $DB_HOST"
Write-Host "  Port: $DB_PORT"
Write-Host "  Database: $DB_NAME"
Write-Host "  User: $DB_USER"
Write-Host "  Schema: $DB_SCHEMA"
if ($DB_SUPERUSER -ne $DB_USER) {
    Write-Host "  Superuser for ownership fixes: $DB_SUPERUSER"
}
Write-Host ''

$previousPassword = $env:PGPASSWORD
$env:PGPASSWORD = $DB_PASSWORD
& psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -c 'SELECT version();' > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: Cannot connect to PostgreSQL database'
    Write-Host 'Please ensure PostgreSQL is running and credentials in .env are correct'
    $env:PGPASSWORD = $previousPassword
    exit 1
}
$env:PGPASSWORD = $previousPassword

Write-Host '✓ Database connection successful'
Write-Host ''

Write-Host 'Step 2: Backing up database...'
Write-Host ''

$backupDir = Join-Path $projectRoot 'backups'
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupFile = Join-Path $backupDir "linkedin_gateway_pre_v1.1_${timestamp}.sql"

Write-Host "Creating backup: $backupFile"
$previousPassword = $env:PGPASSWORD
$env:PGPASSWORD = $DB_PASSWORD
& pg_dump -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -f $backupFile
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: Failed to create backup'
    $env:PGPASSWORD = $previousPassword
    exit 1
}
$env:PGPASSWORD = $previousPassword

Write-Host '✓ Backup created successfully'
Write-Host ''

function Invoke-OwnershipFix {
    param(
        [Parameter(Mandatory = $true)] [string] $User,
        [Parameter(Mandatory = $true)] [string] $Password
    )

    $tempFile = New-TemporaryFile
    try {
        $sql = @'
\set ON_ERROR_STOP on

DO $OWNERSHIP$
DECLARE
    target_owner name := :'target_owner';
    schema_name name := :'schema_name';
    rec RECORD;
    changed_count INTEGER;
    skipped_count INTEGER;
BEGIN
    BEGIN
        EXECUTE format('ALTER SCHEMA %I OWNER TO %I', schema_name, target_owner);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Skipping schema owner change for % due to insufficient privileges', schema_name;
        WHEN others THEN
            RAISE NOTICE 'Could not change schema owner for %: %', schema_name, SQLERRM;
    END;

    changed_count := 0;
    skipped_count := 0;
    FOR rec IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = schema_name
          AND c.relkind IN ('r','p','f')
          AND pg_get_userbyid(c.relowner) <> target_owner
          AND NOT EXISTS (
              SELECT 1
              FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass
                AND d.objid = c.oid
                AND d.deptype = 'e'
          )
    LOOP
        BEGIN
            EXECUTE format('ALTER TABLE %I.%I OWNER TO %I', schema_name, rec.relname, target_owner);
            changed_count := changed_count + 1;
        EXCEPTION
            WHEN insufficient_privilege THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Skipping table % due to insufficient privileges', rec.relname;
            WHEN others THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Could not change owner for table %: %', rec.relname, SQLERRM;
        END;
    END LOOP;
    RAISE NOTICE 'Tables/partitions updated: %', changed_count;
    IF skipped_count > 0 THEN
        RAISE NOTICE 'Tables skipped due to permission issues: %', skipped_count;
    END IF;

    changed_count := 0;
    skipped_count := 0;
    FOR rec IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = schema_name
          AND c.relkind = 'S'
          AND pg_get_userbyid(c.relowner) <> target_owner
          AND NOT EXISTS (
              SELECT 1
              FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass
                AND d.objid = c.oid
                AND d.deptype = 'e'
          )
    LOOP
        BEGIN
            EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO %I', schema_name, rec.relname, target_owner);
            changed_count := changed_count + 1;
        EXCEPTION
            WHEN insufficient_privilege THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Skipping sequence % due to insufficient privileges', rec.relname;
            WHEN others THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Could not change owner for sequence %: %', rec.relname, SQLERRM;
        END;
    END LOOP;
    RAISE NOTICE 'Sequences updated: %', changed_count;
    IF skipped_count > 0 THEN
        RAISE NOTICE 'Sequences skipped due to permission issues: %', skipped_count;
    END IF;

    changed_count := 0;
    skipped_count := 0;
    FOR rec IN
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = schema_name
          AND c.relkind IN ('v','m')
          AND pg_get_userbyid(c.relowner) <> target_owner
    LOOP
        BEGIN
            IF rec.relkind = 'v' THEN
                EXECUTE format('ALTER VIEW %I.%I OWNER TO %I', schema_name, rec.relname, target_owner);
            ELSE
                EXECUTE format('ALTER MATERIALIZED VIEW %I.%I OWNER TO %I', schema_name, rec.relname, target_owner);
            END IF;
            changed_count := changed_count + 1;
        EXCEPTION
            WHEN insufficient_privilege THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Skipping view % due to insufficient privileges', rec.relname;
            WHEN others THEN
                skipped_count := skipped_count + 1;
                RAISE NOTICE 'Could not change owner for view %: %', rec.relname, SQLERRM;
        END;
    END LOOP;
    RAISE NOTICE 'Views updated: %', changed_count;
    IF skipped_count > 0 THEN
        RAISE NOTICE 'Views skipped due to permission issues: %', skipped_count;
    END IF;

    BEGIN
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I TO %I', schema_name, target_owner);
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I TO %I', schema_name, target_owner);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Skipping privilege grants due to insufficient privileges';
        WHEN others THEN
            RAISE NOTICE 'Could not grant privileges: %', SQLERRM;
    END;
END
$OWNERSHIP$;
'@
        Set-Content -Path $tempFile.FullName -Value $sql -Encoding ASCII

        $previousPassword = $env:PGPASSWORD
        $env:PGPASSWORD = $Password
        & psql -X -q -U $User -h $DB_HOST -p $DB_PORT -d $DB_NAME `
            -v "target_owner=$DB_USER" -v "schema_name=$DB_SCHEMA" `
            -f $tempFile.FullName
        $env:PGPASSWORD = $previousPassword

        return ($LASTEXITCODE -eq 0)
    } finally {
        if (Test-Path $tempFile.FullName) {
            Remove-Item $tempFile.FullName -ErrorAction SilentlyContinue
        }
    }
}

function Get-UnownedObjectCount {
    $query = @'
WITH relevant_objects AS (
    SELECT pg_get_userbyid(c.relowner) AS owner
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :'schema_name'
      AND c.relkind IN ('r','p','f','S','v','m')
      AND NOT EXISTS (
          SELECT 1
          FROM pg_depend d
          WHERE d.classid = 'pg_class'::regclass
            AND d.objid = c.oid
            AND d.deptype = 'e'
      )
)
SELECT COUNT(*) FROM relevant_objects WHERE owner <> :'target_owner';
'@

    $previousPassword = $env:PGPASSWORD
    $env:PGPASSWORD = $DB_PASSWORD
    $output = & psql -X -A -t -q -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME `
        -v "target_owner=$DB_USER" -v "schema_name=$DB_SCHEMA" `
        -c $query 2>$null
    $lastExit = $LASTEXITCODE
    $env:PGPASSWORD = $previousPassword

    if ($lastExit -ne 0) {
        return -1
    }
    return [int]($output.Trim())
}

function Show-UnownedObjects {
    $query = @'
WITH objects AS (
    SELECT 'TABLE' AS object_type, c.relname AS object_name, pg_get_userbyid(c.relowner) AS owner
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :'schema_name'
      AND c.relkind IN ('r','p','f')
      AND NOT EXISTS (
          SELECT 1
          FROM pg_depend d
          WHERE d.classid = 'pg_class'::regclass
            AND d.objid = c.oid
            AND d.deptype = 'e'
      )
    UNION ALL
    SELECT 'SEQUENCE', c.relname, pg_get_userbyid(c.relowner)
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :'schema_name'
      AND c.relkind = 'S'
      AND NOT EXISTS (
          SELECT 1
          FROM pg_depend d
          WHERE d.classid = 'pg_class'::regclass
            AND d.objid = c.oid
            AND d.deptype = 'e'
      )
    UNION ALL
    SELECT 'VIEW', c.relname, pg_get_userbyid(c.relowner)
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :'schema_name'
      AND c.relkind IN ('v','m')
)
SELECT object_type, object_name, owner
FROM objects
WHERE owner <> :'target_owner'
ORDER BY object_type, object_name;
'@

    $previousPassword = $env:PGPASSWORD
    $env:PGPASSWORD = $DB_PASSWORD
    & psql -X -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME `
        -v "target_owner=$DB_USER" -v "schema_name=$DB_SCHEMA" `
        -c $query
    $env:PGPASSWORD = $previousPassword
}

Write-Host 'Step 3: Checking and fixing database ownership...'
Write-Host ''

$initialUnowned = Get-UnownedObjectCount
if ($initialUnowned -eq -1) {
    Write-Host '✗ Failed to inspect current ownership state'
    exit 1
}

if ($initialUnowned -eq 0) {
    Write-Host "✓ All relevant database objects already owned by $DB_USER"
} else {
    Write-Host "⚠ Found $initialUnowned database objects not owned by $DB_USER in schema $DB_SCHEMA"
    Write-Host "→ Attempting ownership transfer using credentials for $DB_USER..."

    $success = Invoke-OwnershipFix -User $DB_USER -Password $DB_PASSWORD
    if ($success) {
        Write-Host "✓ Ownership synchronization attempt completed as $DB_USER"
    } else {
        Write-Host "⚠ Ownership transfer encountered errors when running as $DB_USER (likely insufficient privileges)"
        if ($DB_SUPERUSER -and $DB_SUPERUSER_PASSWORD -and ($DB_SUPERUSER -ne $DB_USER -or $DB_SUPERUSER_PASSWORD -ne $DB_PASSWORD)) {
            Write-Host "→ Retrying ownership transfer with elevated role $DB_SUPERUSER..."
            $success = Invoke-OwnershipFix -User $DB_SUPERUSER -Password $DB_SUPERUSER_PASSWORD
            if ($success) {
                Write-Host "✓ Ownership synchronization attempt completed as $DB_SUPERUSER"
            } else {
                Write-Host "⚠ Ownership transfer still encountered errors with $DB_SUPERUSER"
            }
        }
    }

    $finalUnowned = Get-UnownedObjectCount
    if ($finalUnowned -eq -1) {
        Write-Host '✗ Failed to verify ownership after attempting to fix it'
        exit 1
    }

    if ($finalUnowned -gt 0) {
        Write-Host "⚠ Ownership fix incomplete. Remaining objects not owned by $DB_USER: $finalUnowned"
        Write-Host ''
        Show-UnownedObjects
        Write-Host ''
        Write-Host 'Note: PostgreSQL only allows the current owner or a superuser to transfer ownership.'
        Write-Host '      If migrations fail later, rerun this script with elevated credentials or'
        Write-Host '      use deployment/scripts/fix-db-ownership.* from a privileged role.'
    } else {
        Write-Host "✓ Ownership transferred successfully to $DB_USER"
    }
}

Write-Host ''

Write-Host 'Step 4: Applying database migrations...'
Write-Host ''

$migrationFile = New-TemporaryFile
try {
    $migrationSql = @'
-- Multi-key support migration for v1.1.0

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS instance_id VARCHAR(255);
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS instance_name VARCHAR(255);
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS browser_info JSONB DEFAULT '{}';
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS webhook_url VARCHAR(1024);
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS webhook_headers JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS ix_api_keys_instance ON api_keys(user_id, instance_id, is_active);
CREATE INDEX IF NOT EXISTS ix_api_keys_user_active ON api_keys(user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_api_keys_last_used ON api_keys(last_used_at DESC NULLS LAST);

COMMENT ON COLUMN api_keys.instance_id IS 'Unique identifier for extension instance (e.g., chrome_1699123456789_a9b8c7d6)';
COMMENT ON COLUMN api_keys.instance_name IS 'User-friendly name for the extension instance (e.g., "Chrome - Windows")';
COMMENT ON COLUMN api_keys.browser_info IS 'JSON metadata about browser: {browser, version, os, platform}';
COMMENT ON COLUMN api_keys.webhook_url IS 'Optional webhook endpoint invoked for this API key';
COMMENT ON COLUMN api_keys.webhook_headers IS 'Optional headers sent with webhook invocations';

UPDATE api_keys
SET webhook_headers = '{}'::jsonb
WHERE webhook_headers IS NULL;
'@
    Set-Content -Path $migrationFile.FullName -Value $migrationSql -Encoding ASCII

    $previousPassword = $env:PGPASSWORD
    $env:PGPASSWORD = $DB_PASSWORD
    & psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -f $migrationFile.FullName
    $status = $LASTEXITCODE
    $env:PGPASSWORD = $previousPassword

    if ($status -ne 0) {
        Write-Host '✗ Failed to apply database migrations'
        Write-Host ''
        Write-Host "Backup available at: $backupFile"
        Write-Host ''
        Write-Host 'To restore:'
        Write-Host "  psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -f `"$backupFile`""
        exit 1
    }
} finally {
    if (Test-Path $migrationFile.FullName) {
        Remove-Item $migrationFile.FullName -ErrorAction SilentlyContinue
    }
}

Write-Host '✓ Database migrations applied successfully'
Write-Host ''

Write-Host 'Step 5: Updating version...'
Write-Host ''
Write-Host '✓ Version files already updated to v1.1.0'
Write-Host ''

Write-Host '============================================'
Write-Host 'Update Complete!'
Write-Host '============================================'
Write-Host ''
Write-Host 'Your LinkedIn Gateway has been updated to v1.1.0'
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  1. Restart your backend server'
Write-Host '  2. Rebuild and reload the Chrome extension:'
Write-Host '     cd chrome-extension'
Write-Host '     npm run build:prod'
Write-Host '  3. Reload extension in Chrome (chrome://extensions/)'
Write-Host ''
Write-Host 'Existing API keys will continue to work'
Write-Host 'New keys will include instance tracking'
Write-Host ''
Write-Host "Backup location: $backupFile"
Write-Host ''

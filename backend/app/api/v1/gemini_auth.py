"""
Gemini OAuth Script Generation and Credential Storage.

Since the Cloud Code API only accepts tokens from the Gemini CLI OAuth client,
and that client only allows localhost redirects, we generate scripts that users
run locally to authenticate.

The scripts:
1. Start a local HTTP server
2. Open Google OAuth with Gemini CLI credentials
3. Exchange the code for tokens
4. Send tokens to our backend to store
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.db.models.user import User
from app.crud import api_key as api_key_crud
from app.gemini.config import (
    GEMINI_CLIENT_ID, 
    GEMINI_CLIENT_SECRET, 
    GEMINI_SCOPES,
    TOKEN_URI,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gemini/auth", tags=["Gemini Authentication"])

# In-memory store for pending script sessions
# Structure: {session_id: {"user_id": uuid, "created_at": datetime}}
pending_sessions: dict = {}

SESSION_EXPIRY_MINUTES = 30


class GeminiCredentialsSubmit(BaseModel):
    """Credentials submitted by the local script."""
    session_id: str
    access_token: str
    refresh_token: str
    expires_in: Optional[int] = 3600
    user_email: Optional[str] = None
    project_id: Optional[str] = None


def cleanup_expired_sessions():
    """Remove expired sessions."""
    now = datetime.utcnow()
    expired = [
        sid for sid, data in pending_sessions.items()
        if now - data["created_at"] > timedelta(minutes=SESSION_EXPIRY_MINUTES)
    ]
    for sid in expired:
        del pending_sessions[sid]


@router.get("/script/{platform}")
async def generate_auth_script(
    platform: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a platform-specific OAuth script for the user.
    
    Args:
        platform: 'windows' or 'mac'
    
    Returns:
        Script content as plain text
    """
    cleanup_expired_sessions()
    
    if platform not in ['windows', 'mac']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform must be 'windows' or 'mac'"
        )
    
    # Generate unique session ID
    session_id = secrets.token_urlsafe(32)
    
    # Determine server URL
    public_url = request.headers.get("X-Public-URL")
    if not public_url:
        # Build from request
        host = request.headers.get("host", "localhost")
        scheme = "https" if "ainnovate.tech" in host else "http"
        public_url = f"{scheme}://{host}"
    
    server_url = public_url.rstrip('/')
    
    # Store session
    pending_sessions[session_id] = {
        "user_id": current_user.id,
        "created_at": datetime.utcnow()
    }
    
    logger.info(f"[GEMINI AUTH] Generated script for user {current_user.id}, session: {session_id[:8]}...")
    
    if platform == 'windows':
        script = _generate_windows_batch_script(session_id, server_url)
        filename = "connect_gemini.bat"
    else:
        script = _generate_mac_script(session_id, server_url)
        filename = "connect_gemini.sh"
    
    return PlainTextResponse(
        content=script,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/submit-credentials")
async def submit_credentials(
    credentials: GeminiCredentialsSubmit,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive credentials from the local OAuth script.
    
    This endpoint does NOT require authentication - it uses the session_id
    to identify which user the credentials belong to.
    """
    cleanup_expired_sessions()
    
    session_id = credentials.session_id
    
    if session_id not in pending_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired session. Please generate a new script."
        )
    
    session = pending_sessions[session_id]
    user_id = session["user_id"]
    
    # Check expiry
    if datetime.utcnow() - session["created_at"] > timedelta(minutes=SESSION_EXPIRY_MINUTES):
        del pending_sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired. Please generate a new script."
        )
    
    logger.info(f"[GEMINI AUTH] Received credentials for user {user_id}")
    logger.info(f"[GEMINI AUTH] Email: {credentials.user_email}")
    logger.info(f"[GEMINI AUTH] Project ID: {credentials.project_id}")
    logger.info(f"[GEMINI AUTH] Has access_token: {bool(credentials.access_token)}")
    logger.info(f"[GEMINI AUTH] Has refresh_token: {bool(credentials.refresh_token)}")
    logger.info(f"[GEMINI AUTH] Expires in: {credentials.expires_in}")
    
    # Build credentials object with Gemini CLI client credentials
    creds = {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "token_type": "Bearer",
        "scope": " ".join(GEMINI_SCOPES),
        "client_id": GEMINI_CLIENT_ID,
        "client_secret": GEMINI_CLIENT_SECRET,
        "token_uri": TOKEN_URI
    }
    
    if credentials.expires_in:
        expiry_date = int((datetime.utcnow() + timedelta(seconds=credentials.expires_in)).timestamp() * 1000)
        creds["expiry_date"] = expiry_date
    
    if credentials.user_email:
        creds["user_email"] = credentials.user_email
    
    if credentials.project_id:
        creds["project_id"] = credentials.project_id
        logger.info(f"[GEMINI AUTH] Added project_id to credentials: {credentials.project_id}")
    
    # Store credentials
    try:
        updated_key = await api_key_crud.update_gemini_credentials(
            db=db,
            user_id=user_id,
            gemini_credentials=creds
        )
        
        if updated_key:
            logger.info(f"[GEMINI AUTH] Credentials stored for user {user_id}")
        else:
            logger.warning(f"[GEMINI AUTH] No API key found for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No API key found. Please create an API key first."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[GEMINI AUTH] Failed to store credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store credentials: {str(e)}"
        )
    
    # Clean up session
    del pending_sessions[session_id]
    
    return {
        "success": True,
        "message": "Gemini credentials stored successfully!",
        "user_email": credentials.user_email
    }


def _generate_windows_batch_script(session_id: str, server_url: str) -> str:
    """Generate Windows batch script using Base64-encoded PowerShell."""
    import base64
    
    # The PowerShell script content - clean, no escaping needed
    ps_script = f'''$ErrorActionPreference = "Stop"

$SESSION_ID = "{session_id}"
$SERVER_URL = "{server_url}"
$CLIENT_ID = "{GEMINI_CLIENT_ID}"
$CLIENT_SECRET = "{GEMINI_CLIENT_SECRET}"
$SCOPES = "{' '.join(GEMINI_SCOPES)}"
$TOKEN_URL = "{TOKEN_URI}"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LinkedIn Gateway - Connect Gemini AI" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will connect your Google account to enable Gemini AI features."
Write-Host ""

function Get-AvailablePort {{
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}}

$PORT = Get-AvailablePort
$REDIRECT_URI = "http://localhost:$PORT/"

Write-Host "[*] Starting local server on port $PORT..." -ForegroundColor Yellow

$authParams = @{{
    client_id = $CLIENT_ID
    redirect_uri = $REDIRECT_URI
    response_type = "code"
    scope = $SCOPES
    access_type = "offline"
    prompt = "consent"
}}
$queryString = ($authParams.GetEnumerator() | ForEach-Object {{ "$($_.Key)=$([System.Uri]::EscapeDataString($_.Value))" }}) -join "&"
$authUrl = "https://accounts.google.com/o/oauth2/v2/auth?$queryString"

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($REDIRECT_URI)
$listener.Start()

Write-Host "[*] Opening browser for Google sign-in..." -ForegroundColor Yellow
Start-Process $authUrl

Write-Host "[*] Waiting for authorization..." -ForegroundColor Yellow
Write-Host "    (Complete the sign-in in your browser)" -ForegroundColor Gray

$context = $listener.GetContext()
$request = $context.Request
$response = $context.Response

$code = $null
$errorMsg = $null
$query = $request.Url.Query.TrimStart("?")
foreach ($param in $query.Split("&")) {{
    $parts = $param.Split("=", 2)
    if ($parts.Length -eq 2) {{
        $key = [System.Uri]::UnescapeDataString($parts[0])
        $value = [System.Uri]::UnescapeDataString($parts[1])
        if ($key -eq "code") {{ $code = $value }}
        if ($key -eq "error") {{ $errorMsg = $value }}
    }}
}}

if ($code) {{
    $responseHtml = "<html><body style='font-family:Arial;text-align:center;padding:50px;'><h1 style='color:green;'>Success!</h1><p>You can close this window and return to the extension.</p></body></html>"
}} else {{
    $responseHtml = "<html><body style='font-family:Arial;text-align:center;padding:50px;'><h1 style='color:red;'>Error</h1><p>$errorMsg</p></body></html>"
}}
$buffer = [System.Text.Encoding]::UTF8.GetBytes($responseHtml)
$response.ContentLength64 = $buffer.Length
$response.OutputStream.Write($buffer, 0, $buffer.Length)
$response.Close()
$listener.Stop()

if (-not $code) {{
    Write-Host "[FAIL] Authorization failed: $errorMsg" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}}

Write-Host "[OK] Authorization code received!" -ForegroundColor Green
Write-Host "[*] Exchanging code for tokens..." -ForegroundColor Yellow

$tokenBody = @{{
    code = $code
    client_id = $CLIENT_ID
    client_secret = $CLIENT_SECRET
    redirect_uri = $REDIRECT_URI
    grant_type = "authorization_code"
}}

try {{
    $tokenResponse = Invoke-RestMethod -Uri $TOKEN_URL -Method Post -Body $tokenBody -ContentType "application/x-www-form-urlencoded"
}} catch {{
    Write-Host "[FAIL] Token exchange failed: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}}

Write-Host "[OK] Tokens received!" -ForegroundColor Green
Write-Host "[*] Getting user info..." -ForegroundColor Yellow

$userEmail = $null
$projectId = $null

try {{
    $userInfo = Invoke-RestMethod -Uri "https://www.googleapis.com/oauth2/v2/userinfo" -Headers @{{ Authorization = "Bearer $($tokenResponse.access_token)" }}
    $userEmail = $userInfo.email
    Write-Host "    Email: $userEmail" -ForegroundColor Gray
}} catch {{
    Write-Host "    Could not get user email" -ForegroundColor Gray
}}

Write-Host "[*] Getting Gemini project info..." -ForegroundColor Yellow

$headers = @{{ 
    Authorization = "Bearer $($tokenResponse.access_token)"
    "Content-Type" = "application/json"
}}
$lcaBody = '{{"metadata":{{"ideType":"GEMINI_CLI","platform":"WINDOWS_AMD64","pluginType":"GEMINI"}}}}'

try {{
    $lcaResponse = Invoke-RestMethod -Uri "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" -Method Post -Headers $headers -Body $lcaBody
    $projectId = $lcaResponse.cloudaicompanionProject
    $currentTier = $lcaResponse.currentTier
    
    Write-Host "    Project: $projectId" -ForegroundColor Gray
    Write-Host "    CurrentTier: $($currentTier.id)" -ForegroundColor Gray
    
    # Check if user needs onboarding (no currentTier means not onboarded)
    if (-not $currentTier) {{
        Write-Host "[*] User not onboarded - initiating onboarding..." -ForegroundColor Yellow
        
        # Find default tier from allowedTiers
        $allowedTiers = $lcaResponse.allowedTiers
        $tierId = "free-tier"
        
        if ($allowedTiers) {{
            $tierIds = $allowedTiers | ForEach-Object {{ $_.id }}
            Write-Host "    Available tiers: $($tierIds -join ', ')" -ForegroundColor Gray
            
            foreach ($tier in $allowedTiers) {{
                if ($tier.isDefault) {{
                    $tierId = $tier.id
                    break
                }}
            }}
            if (-not $tierId -and $allowedTiers.Count -gt 0) {{
                $tierId = $allowedTiers[0].id
            }}
        }}
        
        Write-Host "    Using tier: $tierId" -ForegroundColor Gray
        
        # Build onboard payload (matches official CLI)
        $onboardPayload = @{{
            tierId = $tierId
            metadata = @{{
                ideType = "GEMINI_CLI"
                platform = "WINDOWS_AMD64"
                pluginType = "GEMINI"
            }}
        }} | ConvertTo-Json -Depth 3
        
        Write-Host "    Sending onboardUser request..." -ForegroundColor Gray
        
        # Poll until onboarding is complete
        $maxAttempts = 12
        $attempt = 0
        $done = $false
        
        while (-not $done -and $attempt -lt $maxAttempts) {{
            try {{
                $onboardResponse = Invoke-RestMethod -Uri "https://cloudcode-pa.googleapis.com/v1internal:onboardUser" -Method Post -Headers $headers -Body $onboardPayload
                $done = $onboardResponse.done
                
                if (-not $done) {{
                    Write-Host "    Waiting for onboarding... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
                    Start-Sleep -Seconds 5
                }}
            }} catch {{
                Write-Host "    Onboarding attempt failed: $_" -ForegroundColor Yellow
            }}
            $attempt++
        }}
        
        if ($done) {{
            Write-Host "[OK] Onboarding completed!" -ForegroundColor Green
        }} else {{
            Write-Host "[!] Onboarding may still be in progress" -ForegroundColor Yellow
        }}
        
        # Fetch project ID again
        Write-Host "    Fetching project ID..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
        
        $lcaResponse = Invoke-RestMethod -Uri "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" -Method Post -Headers $headers -Body $lcaBody
        $projectId = $lcaResponse.cloudaicompanionProject
        $currentTier = $lcaResponse.currentTier
        
        Write-Host "    Project: $projectId" -ForegroundColor Green
        Write-Host "    Tier: $($currentTier.id)" -ForegroundColor Green
    }}
}} catch {{
    Write-Host "[!] Could not get project info: $_" -ForegroundColor Yellow
    Write-Host "    Credentials saved - onboarding may complete automatically" -ForegroundColor Gray
}}

Write-Host "[*] Sending credentials to server..." -ForegroundColor Yellow

$submitBody = @{{
    session_id = $SESSION_ID
    access_token = $tokenResponse.access_token
    refresh_token = $tokenResponse.refresh_token
    expires_in = $tokenResponse.expires_in
    user_email = $userEmail
    project_id = $projectId
}} | ConvertTo-Json

try {{
    $submitResponse = Invoke-RestMethod -Uri "$SERVER_URL/api/v1/gemini/auth/submit-credentials" -Method Post -Body $submitBody -ContentType "application/json"
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  SUCCESS! Gemini AI Connected!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your Google account is now connected." -ForegroundColor White
    Write-Host "You can close this window and return to the extension." -ForegroundColor White
    Write-Host ""
}} catch {{
    Write-Host "[FAIL] Failed to send credentials to server: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please try again or contact support." -ForegroundColor Yellow
}}

Read-Host "Press Enter to exit"
'''
    
    # Encode the PowerShell script as UTF-16LE Base64 (required by PowerShell -EncodedCommand)
    ps_bytes = ps_script.encode('utf-16-le')
    ps_base64 = base64.b64encode(ps_bytes).decode('ascii')
    
    # Create simple batch file that runs encoded command
    batch_script = f'''@echo off
title LinkedIn Gateway - Connect Gemini AI
powershell -ExecutionPolicy Bypass -EncodedCommand {ps_base64}
pause
'''
    return batch_script


def _generate_windows_script(session_id: str, server_url: str) -> str:
    """Generate PowerShell script for Windows (legacy, use batch instead)."""
    return f'''# LinkedIn Gateway - Gemini AI Connection Script
# Generated for your account. Run this script once to connect your Google account.
#
# Usage: Right-click this file and select "Run with PowerShell"
#        Or run in PowerShell: .\\connect_gemini.ps1

$ErrorActionPreference = "Stop"

# Configuration
$SESSION_ID = "{session_id}"
$SERVER_URL = "{server_url}"
$CLIENT_ID = "{GEMINI_CLIENT_ID}"
$CLIENT_SECRET = "{GEMINI_CLIENT_SECRET}"
$SCOPES = "{' '.join(GEMINI_SCOPES)}"
$TOKEN_URL = "{TOKEN_URI}"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LinkedIn Gateway - Connect Gemini AI" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will connect your Google account to enable Gemini AI features."
Write-Host ""

# Find available port
function Get-AvailablePort {{
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}}

$PORT = Get-AvailablePort
$REDIRECT_URI = "http://localhost:$PORT/"

Write-Host "[*] Starting local server on port $PORT..." -ForegroundColor Yellow

# Build OAuth URL
$authParams = @{{
    client_id = $CLIENT_ID
    redirect_uri = $REDIRECT_URI
    response_type = "code"
    scope = $SCOPES
    access_type = "offline"
    prompt = "consent"
}}
$queryString = ($authParams.GetEnumerator() | ForEach-Object {{ "$($_.Key)=$([System.Uri]::EscapeDataString($_.Value))" }}) -join "&"
$authUrl = "https://accounts.google.com/o/oauth2/v2/auth?$queryString"

# Create HTTP listener
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($REDIRECT_URI)
$listener.Start()

# Open browser
Write-Host "[*] Opening browser for Google sign-in..." -ForegroundColor Yellow
Start-Process $authUrl

Write-Host "[*] Waiting for authorization..." -ForegroundColor Yellow
Write-Host "    (Complete the sign-in in your browser)" -ForegroundColor Gray

# Wait for callback
$context = $listener.GetContext()
$request = $context.Request
$response = $context.Response

# Parse response
$code = $null
$error = $null
$queryParams = [System.Web.HttpUtility]::ParseQueryString($request.Url.Query)
$code = $queryParams["code"]
$error = $queryParams["error"]

# Send response to browser
$responseHtml = if ($code) {{
    '<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1 style="color:green;">Success!</h1><p>You can close this window and return to the extension.</p></body></html>'
}} else {{
    '<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1 style="color:red;">Error</h1><p>' + $error + '</p></body></html>'
}}
$buffer = [System.Text.Encoding]::UTF8.GetBytes($responseHtml)
$response.ContentLength64 = $buffer.Length
$response.OutputStream.Write($buffer, 0, $buffer.Length)
$response.Close()
$listener.Stop()

if (-not $code) {{
    Write-Host "[FAIL] Authorization failed: $error" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}}

Write-Host "[OK] Authorization code received!" -ForegroundColor Green

# Exchange code for tokens
Write-Host "[*] Exchanging code for tokens..." -ForegroundColor Yellow

$tokenBody = @{{
    code = $code
    client_id = $CLIENT_ID
    client_secret = $CLIENT_SECRET
    redirect_uri = $REDIRECT_URI
    grant_type = "authorization_code"
}}

try {{
    $tokenResponse = Invoke-RestMethod -Uri $TOKEN_URL -Method Post -Body $tokenBody -ContentType "application/x-www-form-urlencoded"
}} catch {{
    Write-Host "[FAIL] Token exchange failed: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}}

Write-Host "[OK] Tokens received!" -ForegroundColor Green

# Get user info
Write-Host "[*] Getting user info..." -ForegroundColor Yellow
$userEmail = $null
$projectId = $null

try {{
    $userInfo = Invoke-RestMethod -Uri "https://www.googleapis.com/oauth2/v2/userinfo" -Headers @{{ Authorization = "Bearer $($tokenResponse.access_token)" }}
    $userEmail = $userInfo.email
    Write-Host "    Email: $userEmail" -ForegroundColor Gray
}} catch {{
    Write-Host "    Could not get user email" -ForegroundColor Gray
}}

# Get project ID from loadCodeAssist
Write-Host "[*] Getting Gemini project..." -ForegroundColor Yellow
try {{
    $lcaBody = @{{
        metadata = @{{
            ideType = "GEMINI_CLI"
            platform = "WINDOWS_AMD64"
            pluginType = "GEMINI"
        }}
    }} | ConvertTo-Json

    $lcaResponse = Invoke-RestMethod -Uri "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" `
        -Method Post -Headers @{{ Authorization = "Bearer $($tokenResponse.access_token)"; "Content-Type" = "application/json" }} `
        -Body $lcaBody
    
    $projectId = $lcaResponse.cloudaicompanionProject
    if ($projectId) {{
        Write-Host "    Project: $projectId" -ForegroundColor Gray
    }}
}} catch {{
    Write-Host "    Could not get project ID (this is OK)" -ForegroundColor Gray
}}

# Send credentials to server
Write-Host "[*] Sending credentials to server..." -ForegroundColor Yellow

$submitBody = @{{
    session_id = $SESSION_ID
    access_token = $tokenResponse.access_token
    refresh_token = $tokenResponse.refresh_token
    expires_in = $tokenResponse.expires_in
    user_email = $userEmail
    project_id = $projectId
}} | ConvertTo-Json

try {{
    $submitResponse = Invoke-RestMethod -Uri "$SERVER_URL/api/v1/gemini/auth/submit-credentials" `
        -Method Post -Body $submitBody -ContentType "application/json"
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  SUCCESS! Gemini AI Connected!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your Google account ($userEmail) is now connected." -ForegroundColor White
    Write-Host "You can close this window and return to the extension." -ForegroundColor White
    Write-Host ""
}} catch {{
    Write-Host "[FAIL] Failed to send credentials to server: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please try again or contact support." -ForegroundColor Yellow
}}

Read-Host "Press Enter to exit"
'''


def _generate_mac_script(session_id: str, server_url: str) -> str:
    """Generate Bash script for macOS."""
    return f'''#!/bin/bash
# LinkedIn Gateway - Gemini AI Connection Script
# Generated for your account. Run this script once to connect your Google account.
#
# Usage: chmod +x connect_gemini.sh && ./connect_gemini.sh

set -e

# Configuration
SESSION_ID="{session_id}"
SERVER_URL="{server_url}"
CLIENT_ID="{GEMINI_CLIENT_ID}"
CLIENT_SECRET="{GEMINI_CLIENT_SECRET}"
SCOPES="{' '.join(GEMINI_SCOPES)}"
TOKEN_URL="{TOKEN_URI}"

echo ""
echo "============================================"
echo "  LinkedIn Gateway - Connect Gemini AI"
echo "============================================"
echo ""
echo "This script will connect your Google account to enable Gemini AI features."
echo ""

# Find available port
find_port() {{
    python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()"
}}

PORT=$(find_port)
REDIRECT_URI="http://localhost:$PORT/"

echo "[*] Starting local server on port $PORT..."

# URL encode function
urlencode() {{
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1', safe=''))"
}}

# Build OAuth URL
SCOPE_ENCODED=$(urlencode "$SCOPES")
AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth?client_id=$CLIENT_ID&redirect_uri=$REDIRECT_URI&response_type=code&scope=$SCOPE_ENCODED&access_type=offline&prompt=consent"

# Create a simple Python HTTP server to capture the callback
CAPTURE_SCRIPT=$(cat << 'PYTHON_EOF'
import http.server
import socketserver
import urllib.parse
import sys

PORT = int(sys.argv[1])

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        code = params.get('code', [None])[0]
        error = params.get('error', [None])[0]
        
        if code:
            html = '<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1 style="color:green;">Success!</h1><p>You can close this window.</p></body></html>'
            print(f"CODE:{{code}}")
        else:
            html = f'<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1 style="color:red;">Error</h1><p>{{error}}</p></body></html>'
            print(f"ERROR:{{error}}")
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
        
        # Shutdown after handling request
        def shutdown():
            self.server.shutdown()
        import threading
        threading.Thread(target=shutdown).start()
    
    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.handle_request()
PYTHON_EOF
)

# Open browser
echo "[*] Opening browser for Google sign-in..."
open "$AUTH_URL" 2>/dev/null || xdg-open "$AUTH_URL" 2>/dev/null || echo "Please open this URL: $AUTH_URL"

echo "[*] Waiting for authorization..."
echo "    (Complete the sign-in in your browser)"

# Run server and capture output
RESULT=$(python3 -c "$CAPTURE_SCRIPT" $PORT 2>&1)

# Parse result
if [[ $RESULT == CODE:* ]]; then
    CODE="${{RESULT#CODE:}}"
    echo "[OK] Authorization code received!"
elif [[ $RESULT == ERROR:* ]]; then
    ERROR="${{RESULT#ERROR:}}"
    echo "[FAIL] Authorization failed: $ERROR"
    exit 1
else
    echo "[FAIL] Unknown error"
    exit 1
fi

# Exchange code for tokens
echo "[*] Exchanging code for tokens..."

TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_URL" \\
    -d "code=$CODE" \\
    -d "client_id=$CLIENT_ID" \\
    -d "client_secret=$CLIENT_SECRET" \\
    -d "redirect_uri=$REDIRECT_URI" \\
    -d "grant_type=authorization_code")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))")
EXPIRES_IN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expires_in',3600))")

if [ -z "$ACCESS_TOKEN" ]; then
    echo "[FAIL] Token exchange failed"
    echo "$TOKEN_RESPONSE"
    exit 1
fi

echo "[OK] Tokens received!"

# Get user info
echo "[*] Getting user info..."
USER_EMAIL=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "https://www.googleapis.com/oauth2/v2/userinfo" | python3 -c "import sys,json; print(json.load(sys.stdin).get('email',''))" 2>/dev/null || echo "")
if [ -n "$USER_EMAIL" ]; then
    echo "    Email: $USER_EMAIL"
fi

# Get project ID
echo "[*] Getting Gemini project..."
PROJECT_ID=$(curl -s -X POST "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" \\
    -H "Authorization: Bearer $ACCESS_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{{"metadata":{{"ideType":"GEMINI_CLI","platform":"DARWIN_ARM64","pluginType":"GEMINI"}}}}' | \\
    python3 -c "import sys,json; print(json.load(sys.stdin).get('cloudaicompanionProject',''))" 2>/dev/null || echo "")
if [ -n "$PROJECT_ID" ]; then
    echo "    Project: $PROJECT_ID"
fi

# Send credentials to server
echo "[*] Sending credentials to server..."

SUBMIT_BODY=$(python3 -c "import json; print(json.dumps({{
    'session_id': '$SESSION_ID',
    'access_token': '$ACCESS_TOKEN',
    'refresh_token': '$REFRESH_TOKEN',
    'expires_in': $EXPIRES_IN,
    'user_email': '$USER_EMAIL',
    'project_id': '$PROJECT_ID'
}}))")

SUBMIT_RESPONSE=$(curl -s -X POST "$SERVER_URL/api/v1/gemini/auth/submit-credentials" \\
    -H "Content-Type: application/json" \\
    -d "$SUBMIT_BODY")

SUCCESS=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',False))" 2>/dev/null || echo "False")

if [ "$SUCCESS" = "True" ]; then
    echo ""
    echo "============================================"
    echo "  SUCCESS! Gemini AI Connected!"
    echo "============================================"
    echo ""
    echo "Your Google account ($USER_EMAIL) is now connected."
    echo "You can close this window and return to the extension."
    echo ""
else
    echo "[FAIL] Failed to send credentials to server"
    echo "$SUBMIT_RESPONSE"
fi
'''

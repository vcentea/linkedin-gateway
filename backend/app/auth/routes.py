# backend/app/auth/routes.py
import httpx # Add httpx import
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select # Import select
from sqlalchemy.ext.asyncio import AsyncSession # Ensure AsyncSession is used
from starlette.datastructures import URL
from datetime import datetime, timedelta, timezone # Add timezone and timedelta
import json # Add json import

from .oauth import oauth
from ..db.session import get_db
from ..db.models.user import User, UserSession
from ..core.config import settings
from ..core.security import create_session
# Remove security imports if no longer needed directly in this route
# from ..core.security import create_session, set_session_cookie

router = APIRouter()

@router.get("/login/linkedin", tags=["Authentication"])
async def login_linkedin(request: Request):
    """Redirect user to LinkedIn for authorization."""
    import os
    # Use PUBLIC_URL if set, otherwise use request URL with proper scheme detection
    public_url = os.getenv('PUBLIC_URL')
    
    if public_url and public_url.strip():
        # Use PUBLIC_URL to construct redirect URI (ensures https)
        redirect_uri = f"{public_url.rstrip('/')}/auth/user/callback"
    else:
        # Fall back to request.url_for but detect if behind HTTPS proxy
        redirect_uri = str(request.url_for('user_callback_linkedin'))
        # If behind proxy and X-Forwarded-Proto is https, fix the scheme
        if request.headers.get('x-forwarded-proto') == 'https' and redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://', 1)
    
    print(f"Generated redirect_uri for LinkedIn: {redirect_uri}")
    # Use request object for authorization redirect
    return await oauth.linkedin.authorize_redirect(request, redirect_uri)

@router.get("/user/callback", name="user_callback_linkedin", tags=["Authentication"])
async def callback_linkedin(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle the callback from LinkedIn after authorization."""
    code = request.query_params.get('code')
    state = request.query_params.get('state') # Authlib uses state, good practice to check it if needed

    if not code:
        print("[CALLBACK] Error: Missing code parameter in callback URL")
        raise HTTPException(status_code=400, detail="Missing code parameter in callback URL")
    
    # Construct the redirect_uri EXACTLY the same way as in login_linkedin
    # This MUST match the one sent in the login redirect and registered in LinkedIn app
    import os
    public_url = os.getenv('PUBLIC_URL')
    
    if public_url and public_url.strip():
        # Use PUBLIC_URL to construct redirect URI (same as login)
        redirect_uri = f"{public_url.rstrip('/')}/auth/user/callback"
    else:
        # Fall back to request.url_for with proxy detection (same as login)
        redirect_uri = str(request.url_for('user_callback_linkedin'))
        # If behind proxy and X-Forwarded-Proto is https, fix the scheme
        if request.headers.get('x-forwarded-proto') == 'https' and redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://', 1)
    
    print(f"[CALLBACK] Using redirect_uri for token exchange: {redirect_uri}")

    try:
        token = await manual_linkedin_token_exchange(code, redirect_uri)
    except HTTPException as e:
         raise e
    except Exception as e:
        print(f"Error during manual token exchange: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error during token exchange: {e}")

    if not token or 'access_token' not in token:
        raise HTTPException(status_code=400, detail="Failed to get valid access token from LinkedIn.")

    access_token_value = token['access_token']
    expires_in = token.get('expires_in', 63072000) # Default to 2 years (730 days)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    try:
        async with httpx.AsyncClient() as client:
            headers = {'Authorization': f'Bearer {access_token_value}'}
            userinfo_url = 'https://api.linkedin.com/v2/userinfo'
            print(f"[CALLBACK] Fetching user info from: {userinfo_url}")
            resp = await client.get(userinfo_url, headers=headers)
            resp.raise_for_status()
            profile = resp.json()
            
    except Exception as e:
        print(f"Error fetching user info from LinkedIn: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch user info: {e}")

    linkedin_id = profile.get('sub')
    email = profile.get('email')
    name = profile.get('name')
    picture = profile.get('picture')

    if not linkedin_id or not email:
        raise HTTPException(status_code=400, detail="Could not retrieve necessary profile information from LinkedIn.")

    try:
        # --- Find user by linkedin_id ---
        result_li = await db.execute(
            select(User).where(User.linkedin_id == linkedin_id)
        )
        user = result_li.scalar_one_or_none()
        
        existing_user = False
        if not user:
            # --- If not found by linkedin_id, find by email ---
            result_email = await db.execute(
                select(User).where(User.email == email)
            )
            user = result_email.scalar_one_or_none()
            
            if user:
                # User exists by email, update LinkedIn info
                user.linkedin_id = linkedin_id
                user.name = user.name or name # Update name/picture only if missing
                user.profile_picture_url = user.profile_picture_url or picture
                existing_user = True
                print(f"[CALLBACK] Existing user found by email: {email}. Updated LinkedIn ID.")
            else:
                # Create new user
                print(f"[CALLBACK] Creating new user with email: {email}")
                user = User(
                    linkedin_id=linkedin_id,
                    email=email,
                    name=name,
                    profile_picture_url=picture,
                    is_active=True
                    # Add default subscription/limits if needed here, like in old app
                )
                db.add(user)
                db.flush() # Assign ID before commit if needed (e.g., for default prompts)
                existing_user = False
                 # TODO: Add default prompts/settings for new user if necessary
                print(f"[CALLBACK] New user created with ID: {user.id}")
            await db.flush() # Ensure ID is available if needed before context exit
            if not existing_user:
                await db.refresh(user) # Refresh new user to get defaults

        elif not user.is_active:
             raise HTTPException(status_code=403, detail="User account is inactive.")
        else:
             existing_user = True
             print(f"[CALLBACK] Existing active user found by LinkedIn ID: {linkedin_id}")
             # Optionally update name/picture if changed on LinkedIn?
             # user.name = name
             # user.profile_picture_url = picture
             # db.commit()
             # db.refresh(user)

        # ---> Replace session/redirect logic with HTML response AND store token <---
        # Store the obtained LinkedIn token in our UserSession table
        stored_token = await create_session(
            user_id=user.id, 
            db=db, 
            linkedin_token=access_token_value, 
            linkedin_expires_at=expires_at
        )
        
        if not stored_token:
             # Session creation failed - this is critical!
             print(f"[CALLBACK] ERROR: Failed to store session token for user {user.id}")
             raise HTTPException(status_code=500, detail="Failed to create session")

        print(f"[CALLBACK] ========== TOKEN DEBUG ==========")
        print(f"[CALLBACK] LinkedIn access_token (first 30): {access_token_value[:30]}...")
        print(f"[CALLBACK] Our session token (first 30): {stored_token[:30]}...")
        print(f"[CALLBACK] Returning to frontend: {stored_token[:30]}...")
        print(f"[CALLBACK] ========== END DEBUG ==========")

        # ---> Construct data to send back to frontend <---
        # IMPORTANT: Return the stored_token (our session token), NOT access_token_value (LinkedIn's token)
        user_data_for_frontend = {
            'status': 'success',
            'accessToken': stored_token,  # ✅ Return our session token, not LinkedIn's token
            'id': str(user.id), # Ensure ID is string for JS
            'name': user.name,
            'email': user.email,
            'profile_picture_url': user.profile_picture_url,
            'existing_user': existing_user,
            'token_expires_at': expires_at.isoformat(),
            # Add other relevant user fields if needed by frontend (e.g., subscription)
            # 'subscription_type': user.subscription_type
        }
        
        print(f"[CALLBACK] Final user_data_for_frontend accessToken (first 30): {user_data_for_frontend['accessToken'][:30]}...")

        # Construct HTML response similar to the old app
        print("[CALLBACK] Preparing HTML response with postMessage...")
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Success</title>
            <script>
                window.onload = function() {{
                    try {{
                        // Use JSON.stringify to safely embed the data
                        const userData = {json.dumps(user_data_for_frontend)};
                        console.log('[CALLBACK HTML] Sending message to opener:', JSON.stringify(userData));
                        // ---> Use '*' as targetOrigin for broader compatibility
                        const targetOrigin = '*'; 
                        if (window.opener) {{
                            window.opener.postMessage(userData, targetOrigin);
                            console.log('[CALLBACK HTML] Message sent to:', targetOrigin);
                            // Optionally close window after a short delay
                             setTimeout(() => window.close(), 500);
                        }} else {{
                             console.error('[CALLBACK HTML] window.opener is not available.');
                             document.body.innerHTML = "Authentication successful, but could not communicate back to the application window. Please close this window manually.";
                        }}
                    }} catch (error) {{
                        console.error('[CALLBACK HTML] Error sending message to the opener:', error);
                        document.body.innerHTML = "An error occurred during authentication finalization. Please close this window and try again.";
                    }}
                }};
            </script>
        </head>
        <body>
            Processing authentication... You can close this window if it does not close automatically.
        </body>
        </html>
        '''
        print("[CALLBACK] Returning HTML response")
        return HTMLResponse(content=html_content)

    except Exception as e:
        # Use await for rollback
        await db.rollback()
        # Log the error without accessing potentially expired ORM objects
        error_message = f"Database or other error during LinkedIn callback: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        # Return an error HTML page as well
        error_html = f"<html><body>Authentication failed: {error_message}. Please close this window.</body></html>"
        return HTMLResponse(content=error_html, status_code=500)
    # finally: # Removed finally as Depends(get_db) handles session closing

@router.post("/logout", tags=["Authentication"])
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Log out the user by invalidating their session token.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"status": "success", "message": "No active session"}
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        # Find and delete the session with this token using delete() construct
        # Note: delete() is usually synchronous in older SQLAlchemy, but might need adjustment for async
        # For async, typically you'd select, then delete objects in the session
        result = await db.execute(
            select(UserSession).where(UserSession.session_token == token)
        )
        sessions_to_delete = result.scalars().all()
        deleted_count = len(sessions_to_delete)
        for session in sessions_to_delete:
            await db.delete(session)
        await db.flush() # Ensure deletion is flushed before commit
        
        # await db.commit() # Rely on get_db context manager
        
        return {
            "status": "success", 
            "message": "Logged out successfully", 
            "details": {"sessions_invalidated": deleted_count}
        }
    except Exception as e:
        # Use await for rollback
        await db.rollback()
        print(f"Error during logout: {e}")
        return {"status": "error", "message": "Error during logout process"}

# TODO: Add a /logout route that clears the session cookie and potentially invalidates the session server-side.
# TODO: Add a /me route to get current user details based on session cookie. 

async def manual_linkedin_token_exchange(code: str, redirect_uri: str) -> dict:
    """Manually exchange authorization code for access token."""
    url = 'https://www.linkedin.com/oauth/v2/accessToken'
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri, # Use the dynamically generated one
        'client_id': settings.LINKEDIN_CLIENT_ID,
        'client_secret': settings.LINKEDIN_CLIENT_SECRET
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"[DEBUG Manual Exchange] Sending POST to {url} with client_id: {data['client_id']}")
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            token_data = response.json()
            print(f"[DEBUG Manual Exchange] Received token data: {token_data}")
            return token_data
        except httpx.RequestError as exc:
            print(f"[DEBUG Manual Exchange] HTTP Request error: {exc}")
            raise HTTPException(status_code=400, detail=f"Error contacting LinkedIn token endpoint: {exc}")
        except httpx.HTTPStatusError as exc:
            print(f"[DEBUG Manual Exchange] HTTP Status error: {exc.response.status_code} - {exc.response.text}")
            # Try to parse error details from LinkedIn if available
            error_details = exc.response.text
            try: 
                error_json = exc.response.json()
                error_details = error_json.get('error_description', error_json.get('error', error_details))
            except Exception:
                pass # Keep original text if JSON parsing fails
            raise HTTPException(status_code=exc.response.status_code, detail=f"LinkedIn token exchange error: {error_details}") 
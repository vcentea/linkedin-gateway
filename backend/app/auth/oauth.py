from authlib.integrations.starlette_client import OAuth
from ..core.config import settings

# ---> Add print statement here
print(f"[DEBUG oauth.py] Loaded Client Secret: {settings.LINKEDIN_CLIENT_SECRET}")

# Initialize OAuth client
oauth = OAuth()

# Register LinkedIn client
oauth.register(
    name='linkedin',
    client_id=settings.LINKEDIN_CLIENT_ID,
    client_secret=settings.LINKEDIN_CLIENT_SECRET,
    authorize_url='https://www.linkedin.com/oauth/v2/authorization',
    authorize_params=None,
    access_token_url='https://www.linkedin.com/oauth/v2/accessToken',
    access_token_params=None,
    redirect_uri=settings.LINKEDIN_REDIRECT_URI, # Must match LinkedIn Dev Portal and route
    client_kwargs={'scope': 'openid profile email'}, # Standard OIDC scopes
    userinfo_endpoint='https://api.linkedin.com/v2/userinfo' # OIDC userinfo endpoint
) 
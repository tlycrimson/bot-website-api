# main.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import requests
import time
import logging
from typing import Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get all environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
HICOM_ROLE_ID = os.getenv("HICOM_ROLE_ID")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://bot-website-api.onrender.com/auth/callback")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ADMIN_DISCORD_ID = "353167234698444802"  # Your Discord ID

# Validate
required_vars = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_ANON_KEY": SUPABASE_KEY,
    "DISCORD_CLIENT_ID": DISCORD_CLIENT_ID,
    "DISCORD_CLIENT_SECRET": DISCORD_CLIENT_SECRET,
    "DISCORD_BOT_TOKEN": DISCORD_BOT_TOKEN,
    "DISCORD_GUILD_ID": DISCORD_GUILD_ID,
    "HICOM_ROLE_ID": HICOM_ROLE_ID,
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

logger.info("All environment variables loaded successfully!")

# Security
security = HTTPBearer()

# Headers for Supabase
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ============ HELPER FUNCTIONS ============

def supabase_request(method, table, data=None, params=None, record_id=None):
    """Your existing supabase_request function"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    if record_id is not None:
        url = f"{url}?user_id=eq.{record_id}"
    
    response = requests.request(
        method=method,
        url=url,
        headers=HEADERS,
        json=data,
        params=params
    )
    
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Supabase error: {response.text}"
        )
    
    if method == "DELETE":
        return {"success": True}
    
    return response.json()

def _filter_payload(data: dict, allowed_keys: set[str]) -> dict:
    """Your existing _filter_payload function"""
    return {k: v for k, v in data.items() if k in allowed_keys}

# ============ AUTHENTICATION HELPERS ============

# Try to import JWT, but provide a fallback if not installed
try:
    import jwt
    
    def create_jwt_token(user_data: dict) -> str:
        """Create a JWT token for authenticated user"""
        payload = {
            **user_data,
            "exp": time.time() + 3600,  # 1 hour expiration
            "iat": time.time()
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    def verify_jwt_token(token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return payload
        except:
            return None
            
except ImportError:
    logger.warning("PyJWT not installed. Using simple token system (NOT SECURE FOR PRODUCTION)")
    
    # Simple fallback for development
    import base64
    import json
    
    def create_jwt_token(user_data: dict) -> str:
        """Simple token creation (not secure)"""
        payload = {
            **user_data,
            "exp": time.time() + 3600,
            "iat": time.time()
        }
        json_str = json.dumps(payload)
        return base64.b64encode(json_str.encode()).decode()
    
    def verify_jwt_token(token: str) -> Optional[dict]:
        """Simple token verification (not secure)"""
        try:
            json_str = base64.b64decode(token.encode()).decode()
            payload = json.loads(json_str)
            if payload.get("exp", 0) > time.time():
                return payload
        except:
            pass
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current user from JWT token"""
    token = credentials.credentials
    user = verify_jwt_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

async def is_admin_or_hicom(user: dict = Depends(get_current_user)):
    """Check if user is admin or has HICOM role"""
    # Check if user is you (admin)
    if user.get("discord_id") == ADMIN_DISCORD_ID:
        return user
    
    # Check HICOM role via Discord API
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"  # Fixed: Use "Bot" prefix
    }
    
    # Get user's roles in the guild
    try:
        response = requests.get(
            f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{user.get('discord_id')}",
            headers=headers
        )
        
        if response.status_code == 200:
            member_data = response.json()
            roles = member_data.get("roles", [])
            
            # Check if user has HICOM role
            if HICOM_ROLE_ID and HICOM_ROLE_ID in roles:
                return user
    except Exception as e:
        logger.error(f"Failed to check Discord roles: {e}")
    
    raise HTTPException(status_code=403, detail="Access denied. Requires HICOM role or admin privileges.")

# ============ DISCORD OAUTH ENDPOINTS ============

@app.get("/auth/discord/login")
def discord_login():
    """Redirect to Discord OAuth2"""
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds.members.read"
    )
    return {"auth_url": discord_auth_url}

@app.get("/auth/callback")
def discord_callback(code: str):
    """Handle Discord OAuth2 callback"""
    # Exchange code for access token
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "scope": "identify+guilds.members.read"
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data=token_data,
        headers=headers
    )
    
    if response.status_code != 200:
        logger.error(f"Discord token exchange failed: {response.text}")
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    
    tokens = response.json()
    access_token = tokens.get("access_token")
    
    # Get user info from Discord
    user_response = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    if user_response.status_code != 200:
        logger.error(f"Discord user info failed: {user_response.text}")
        raise HTTPException(status_code=400, detail="Failed to get user info")
    
    user_data = user_response.json()
    
    # Create JWT token
    jwt_token = create_jwt_token({
        "discord_id": user_data["id"],
        "username": user_data["username"],
        "avatar": user_data.get("avatar"),
        "discriminator": user_data.get("discriminator"),
        "access_token": access_token
    })
    
    return {
        "token": jwt_token,
        "user": {
            "id": user_data["id"],
            "username": user_data["username"],
            "avatar": user_data.get("avatar"),
            "discriminator": user_data.get("discriminator")
        }
    }

@app.get("/auth/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "user": {
            "discord_id": user.get("discord_id"),
            "username": user.get("username"),
            "avatar": user.get("avatar"),
            "discriminator": user.get("discriminator")
        },
        "is_admin": user.get("discord_id") == ADMIN_DISCORD_ID
    }

@app.get("/auth/check-permissions")
async def check_permissions(user: dict = Depends(is_admin_or_hicom)):
    """Check if user has admin/HICOM permissions"""
    return {
        "authorized": True,
        "user": {
            "discord_id": user.get("discord_id"),
            "username": user.get("username")
        },
        "is_admin": user.get("discord_id") == ADMIN_DISCORD_ID
    }

# ============ PUBLIC LEADERBOARD ENDPOINTS ============

@app.get("/")
def root():
    return {"message": "Bot API is running"}

# PUBLIC endpoint - no authentication required
@app.get("/public/leaderboard")
async def public_leaderboard():
    """Public XP leaderboard - no authentication required"""
    params = {
        "select": "user_id,username,xp",
        "order": "xp.desc",
        "limit": "100"  # Limit results for performance
    }
    try:
        return supabase_request("GET", "users", params=params)
    except Exception as e:
        logger.error(f"Failed to fetch public leaderboard: {e}")
        return []

# PUBLIC endpoint - no authentication required
@app.get("/public/hr")
async def public_hr():
    """Public HR leaderboard - no authentication required"""
    params = {
        "select": "user_id,username,tryouts,events,phases,courses,inspections,joint_events,division,rank",
        "order": "user_id",
        "limit": "100"
    }
    try:
        return supabase_request("GET", "HRs", params=params)
    except Exception as e:
        logger.error(f"Failed to fetch public HR data: {e}")
        return []

# PUBLIC endpoint - no authentication required
@app.get("/public/lr")
async def public_lr():
    """Public LR leaderboard - no authentication required"""
    params = {
        "select": "user_id,username,activity,time_guarded,events_attended,division,rank",
        "order": "user_id",
        "limit": "100"
    }
    try:
        return supabase_request("GET", "LRs", params=params)
    except Exception as e:
        logger.error(f"Failed to fetch public LR data: {e}")
        return []

# ============ ADMIN ENDPOINTS (Protected) ============

# Keep existing protected endpoints for admin panel
@app.get("/leaderboard")
async def leaderboard(user: dict = Depends(is_admin_or_hicom)):
    """Get all users for admin panel (protected)"""
    params = {
        "select": "user_id,username,xp",
        "order": "xp.desc"
    }
    return supabase_request("GET", "users", params=params)

@app.get("/hr")
async def get_hr(user: dict = Depends(is_admin_or_hicom)):
    """Get all HR users (protected)"""
    params = {"order": "user_id"}
    return supabase_request("GET", "HRs", params=params)

@app.get("/lr")
async def get_lr(user: dict = Depends(is_admin_or_hicom)):
    """Get all LR users (protected)"""
    params = {"order": "user_id"}
    return supabase_request("GET", "LRs", params=params)

# ============ CREATE ENDPOINTS (Protected) ============

# Allowed columns per table
HR_COLUMNS = {
    "user_id",
    "username",
    "tryouts",
    "events",
    "phases",
    "courses",
    "inspections",
    "joint_events",
    "division",
    "rank",
}

LR_COLUMNS = {
    "user_id",
    "username",
    "activity",
    "time_guarded",
    "events_attended",
    "division",
    "rank",
}

USER_COLUMNS = {
    "user_id",
    "username",
    "xp",
}

@app.post("/hr")
async def create_hr(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create a new HR row."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, HR_COLUMNS)
    return supabase_request("POST", "HRs", data=payload)

@app.post("/lr")
async def create_lr(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create a new LR row."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, LR_COLUMNS)
    return supabase_request("POST", "LRs", data=payload)

@app.post("/users")
async def create_user(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create a new user (XP entry)."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, USER_COLUMNS)
    return supabase_request("POST", "users", data=payload)

# ============ UPDATE ENDPOINTS (Protected) ============

@app.patch("/hr/{user_id}")
async def update_hr(user_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update an HR row."""
    payload = _filter_payload(data, HR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for HR")
    return supabase_request("PATCH", "HRs", data=payload, record_id=user_id)

@app.patch("/lr/{user_id}")
async def update_lr(user_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update an LR row."""
    payload = _filter_payload(data, LR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for LR")
    return supabase_request("PATCH", "LRs", data=payload, record_id=user_id)

@app.patch("/users/{user_id}")
async def update_user(user_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update a user's XP or username."""
    payload = _filter_payload(data, USER_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for user")
    return supabase_request("PATCH", "users", data=payload, record_id=user_id)

# ============ DELETE ENDPOINTS (Protected) ============

@app.delete("/hr/{user_id}")
async def delete_hr(user_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete an HR row"""
    return supabase_request("DELETE", "HRs", record_id=user_id)

@app.delete("/lr/{user_id}")
async def delete_lr(user_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete an LR row"""
    return supabase_request("DELETE", "LRs", record_id=user_id)

@app.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete a user row"""
    return supabase_request("DELETE", "users", record_id=user_id)

# ============ HEALTH CHECK (Public) ============

@app.get("/health")
def health_check():
    """Public health check"""
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=HEADERS)
        if response.status_code == 200:
            return {"status": "healthy", "supabase": "connected"}
        else:
            return {"status": "unhealthy", "supabase": f"error: {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
# main.py - Add these imports
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import requests
import jwt
import time
from typing import Optional, List

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

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

# ============ AUTHENTICATION HELPERS ============

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
        "Authorization": f"Bearer {DISCORD_BOT_TOKEN}"
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
            # You'll need to replace "HICOM_ROLE_ID" with your actual HICOM role ID
            HICOM_ROLE_ID = os.getenv("HICOM_ROLE_ID")
            if HICOM_ROLE_ID and HICOM_ROLE_ID in roles:
                return user
    except:
        pass
    
    raise HTTPException(status_code=403, detail="Access denied. Requires HICOM role or admin privileges.")

# ============ DISCORD OAUTH ENDPOINTS ============

@app.get("/auth/discord/login")
def discord_login():
    """Redirect to Discord OAuth2"""
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5173/auth/callback')}"
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
        "redirect_uri": os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5173/auth/callback"),
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
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    
    tokens = response.json()
    access_token = tokens.get("access_token")
    
    # Get user info from Discord
    user_response = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    if user_response.status_code != 200:
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

# ============ PROTECTED ENDPOINTS ============

# Update ALL your existing endpoints to use the dependency
# Example for /hr endpoint:
@app.get("/hr")
def get_hr(user: dict = Depends(is_admin_or_hicom)):
    """Get all HR users (protected)"""
    params = {"order": "user_id"}
    return supabase_request("GET", "HRs", params=params)

# Do the same for ALL other endpoints:
# - /lr
# - /leaderboard
# - POST/PATCH/DELETE endpoints

# Keep the helper functions from before (supabase_request, etc.)

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
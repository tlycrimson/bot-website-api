# main.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from urllib.parse import urlparse  
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
    """Make a request to Supabase REST API"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    # For DELETE operations with record_id
    if record_id is not None:
        if method == "DELETE":
            url = f"{url}?id=eq.{record_id}"
        else:
            # For PATCH operations on hierarchy tables
            url = f"{url}?id=eq.{record_id}"
    
    logger.info(f"Supabase request: {method} {url}")
    if data:
        logger.info(f"Request data: {data}")
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=HEADERS,
            json=data,
            params=params
        )
        
        logger.info(f"Supabase response status: {response.status_code}")
        logger.info(f"Supabase response text: {response.text[:500]}")
        
        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Supabase error: {response.text}"
            )
        
        # Handle empty responses (204 No Content or empty body)
        if response.status_code == 204 or not response.text.strip():
            if method == "DELETE":
                return {"success": True, "message": "Record deleted successfully"}
            elif method == "POST":
                # For POST, we might want to return the inserted record
                # Try to fetch the latest record if possible
                try:
                    # Try to get the record we just created by fetching latest
                    fetch_params = {"order": "created_at.desc", "limit": 1}
                    fetch_response = requests.get(url, headers=HEADERS, params=fetch_params)
                    if fetch_response.status_code == 200 and fetch_response.text.strip():
                        result = fetch_response.json()
                        if result and len(result) > 0:
                            return result[0]
                except Exception as fetch_error:
                    logger.warning(f"Could not fetch created record: {fetch_error}")
                
                return {"success": True, "message": "Record created successfully"}
            elif method == "PATCH":
                return {"success": True, "message": "Record updated successfully"}
            else:
                return {"success": True}
        
        # Try to parse JSON response
        try:
            return response.json()
        except json.JSONDecodeError:
            # If it's not valid JSON but we have content, return as text
            if response.text:
                return {"message": response.text, "success": True}
            return {"success": True}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Supabase request failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database request failed: {str(e)}")

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
    """Handle Discord OAuth2 callback - redirect to frontend with token"""
    try:
        logger.info(f"Discord callback received. Code: {code[:20]}...")
        
        # Exchange code for access token
        token_data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://bot-website-api.onrender.com/auth/callback",  # MUST match
            "scope": "identify+guilds.members.read"
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # Get access token from Discord
        token_response = requests.post(
            "https://discord.com/api/v10/oauth2/token",
            data=token_data,
            headers=headers
        )
        
        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            # Redirect to frontend with error
            return RedirectResponse(url="http://localhost:5173/login?error=token_failed")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        # Get user info
        user_response = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if user_response.status_code != 200:
            logger.error(f"User info failed: {user_response.text}")
            return RedirectResponse(url="http://localhost:5173/login?error=user_info_failed")
        
        user_data = user_response.json()
        
        # Create JWT token
        jwt_token = create_jwt_token({
            "discord_id": user_data["id"],
            "username": user_data["username"],
            "avatar": user_data.get("avatar"),
            "discriminator": user_data.get("discriminator"),
            "access_token": access_token
        })
        
        logger.info(f"Created JWT token for user: {user_data['username']}")
        
        # For development:
        frontend_url = "http://localhost:5173"
        # For production, you might want to use an environment variable
        
        redirect_url = f"{frontend_url}/auth/redirect?token={jwt_token}"
        
        logger.info(f"Redirecting to frontend: {redirect_url}")
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Error in discord_callback: {str(e)}")
        return RedirectResponse(url="http://localhost:5173/login?error=server_error")

        
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

# ============ HIERARCHY ENDPOINTS ============

# Allowed columns for hierarchy tables
HIERARCHY_SECTION_COLUMNS = {
    "section_title",
    "section_type",
    "accent_color", 
    "display_order",
    "is_active"
}

HIERARCHY_ENTRY_COLUMNS = {
    "section_id",
    "rank",
    "username",
    "army_rank",
    "roblox_id",
    "requirements",
    "display_order"
}

HIERARCHY_HEADER_COLUMNS = {
    "section_id",
    "header_text",
    "display_order"
}

# Get all hierarchy data (public - no auth required)
@app.get("/hierarchy")
async def get_hierarchy():
    """Get all hierarchy data for display"""
    try:
        # Get all active sections
        sections_params = {
            "select": "id,section_title,section_type,accent_color,display_order",
            "order": "display_order",
            "is_active": "eq.true"
        }
        sections = supabase_request("GET", "hierarchy_sections", params=sections_params)
        
        result = []
        for section in sections:
            # Get headers for this section
            headers_params = {
                "select": "header_text,display_order",
                "order": "display_order",
                "section_id": f"eq.{section['id']}"
            }
            headers = supabase_request("GET", "hierarchy_headers", params=headers_params)
            
            # Get entries for this section
            entries_params = {
                "select": "rank,username,army_rank,roblox_id,requirements,display_order",
                "order": "display_order",
                "section_id": f"eq.{section['id']}"
            }
            entries = supabase_request("GET", "hierarchy_entries", params=entries_params)
            
            result.append({
                "section": section,
                "headers": headers,
                "entries": entries
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch hierarchy: {e}")
        return []

# Get hierarchy data for admin panel (with auth)
@app.get("/admin/hierarchy")
async def get_hierarchy_admin(user: dict = Depends(is_admin_or_hicom)):
    """Get all hierarchy data for admin editing"""
    try:
        # Get all sections (including inactive)
        sections = supabase_request("GET", "hierarchy_sections", params={"order": "display_order"})
        
        result = []
        for section in sections:
            # Get headers
            headers_params = {
                "select": "id,header_text,display_order",
                "order": "display_order",
                "section_id": f"eq.{section['id']}"
            }
            headers = supabase_request("GET", "hierarchy_headers", params=headers_params)
            
            # Get entries
            entries_params = {
                "select": "id,rank,username,army_rank,roblox_id,requirements,display_order",
                "order": "display_order", 
                "section_id": f"eq.{section['id']}"
            }
            entries = supabase_request("GET", "hierarchy_entries", params=entries_params)
            
            result.append({
                "section": section,
                "headers": headers,
                "entries": entries
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch admin hierarchy: {e}")
        raise HTTPException(status_code=500, detail="Failed to load hierarchy data")

# Create new hierarchy section
@app.post("/admin/hierarchy/sections")
async def create_hierarchy_section(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create a new hierarchy section"""
    payload = _filter_payload(data, HIERARCHY_SECTION_COLUMNS)
    if not payload.get("section_title") or not payload.get("section_type"):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    return supabase_request("POST", "hierarchy_sections", data=payload)

# Update hierarchy section
@app.patch("/admin/hierarchy/sections/{section_id}")
async def update_hierarchy_section(section_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update a hierarchy section"""
    payload = _filter_payload(data, HIERARCHY_SECTION_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    return supabase_request("PATCH", "hierarchy_sections", data=payload, record_id=section_id)

# Delete hierarchy section
@app.delete("/admin/hierarchy/sections/{section_id}")
async def delete_hierarchy_section(section_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete a hierarchy section and its related data"""
    return supabase_request("DELETE", "hierarchy_sections", record_id=section_id)

# Create hierarchy entry
@app.post("/admin/hierarchy/entries")
async def create_hierarchy_entry(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create a new hierarchy entry (person or quota)"""
    payload = _filter_payload(data, HIERARCHY_ENTRY_COLUMNS)
    if not payload.get("section_id") or not payload.get("rank"):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    return supabase_request("POST", "hierarchy_entries", data=payload)

# Update hierarchy entry
@app.patch("/admin/hierarchy/entries/{entry_id}")
async def update_hierarchy_entry(entry_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update a hierarchy entry"""
    payload = _filter_payload(data, HIERARCHY_ENTRY_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    return supabase_request("PATCH", "hierarchy_entries", data=payload, record_id=entry_id)

# Delete hierarchy entry
@app.delete("/admin/hierarchy/entries/{entry_id}")
async def delete_hierarchy_entry(entry_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete a hierarchy entry"""
    return supabase_request("DELETE", "hierarchy_entries", record_id=entry_id)

# Create hierarchy header
@app.post("/admin/hierarchy/headers")
async def create_hierarchy_header(data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Create headers for a hierarchy section"""
    payload = _filter_payload(data, HIERARCHY_HEADER_COLUMNS)
    if not payload.get("section_id") or not payload.get("header_text"):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    return supabase_request("POST", "hierarchy_headers", data=payload)

# Update hierarchy header
@app.patch("/admin/hierarchy/headers/{header_id}")
async def update_hierarchy_header(header_id: str, data: dict, user: dict = Depends(is_admin_or_hicom)):
    """Update a hierarchy header"""
    payload = _filter_payload(data, HIERARCHY_HEADER_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    return supabase_request("PATCH", "hierarchy_headers", data=payload, record_id=header_id)

# Delete hierarchy header
@app.delete("/admin/hierarchy/headers/{header_id}")
async def delete_hierarchy_header(header_id: str, user: dict = Depends(is_admin_or_hicom)):
    """Delete a hierarchy header"""
    return supabase_request("DELETE", "hierarchy_headers", record_id=header_id)
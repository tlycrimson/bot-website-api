# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
from typing import Optional, List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials")

# Headers for Supabase REST API
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"  # This ensures PATCH returns the updated record
}

# Helper function to make Supabase requests
def supabase_request(method, table, data=None, params=None, record_id=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    # record_id always refers to the user_id column in our tables
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
    
    # For PATCH/DELETE operations that might return empty response
    if response.status_code == 204 or response.text == "":
        if method == "DELETE":
            return {"success": True, "message": "Record deleted successfully"}
        elif method == "PATCH":
            return {"success": True, "message": "Record updated successfully"}
        else:
            return {"success": True}
    
    try:
        return response.json()
    except:
        # If we can't parse JSON, return success message
        if method == "DELETE":
            return {"success": True, "message": "Record deleted successfully"}
        elif method == "PATCH":
            return {"success": True, "message": "Record updated successfully"}
        else:
            return {"success": True, "message": "Operation completed"}

@app.get("/")
def root():
    return {"message": "Bot API is running"}

# ============ GET ENDPOINTS ============

@app.get("/leaderboard")
def leaderboard():
    """Get all XP users for admin panel"""
    params = {
        "select": "user_id,username,xp",
        "order": "xp.desc"
    }
    return supabase_request("GET", "users", params=params)

@app.get("/hr")
def get_hr():
    """Get all HR users"""
    params = {"order": "user_id"}
    return supabase_request("GET", "HRs", params=params)

@app.get("/lr")
def get_lr():
    """Get all LR users"""
    params = {"order": "user_id"}
    return supabase_request("GET", "LRs", params=params)

# ============ CREATE ENDPOINTS ============

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

def _filter_payload(data: dict, allowed_keys: set[str]) -> dict:
    """Return a copy of data containing only keys that exist in the table."""
    return {k: v for k, v in data.items() if k in allowed_keys}

@app.post("/hr")
def create_hr(data: dict):
    """Create a new HR row."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, HR_COLUMNS)
    return supabase_request("POST", "HRs", data=payload)

@app.post("/lr")
def create_lr(data: dict):
    """Create a new LR row."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, LR_COLUMNS)
    return supabase_request("POST", "LRs", data=payload)

@app.post("/users")
def create_user(data: dict):
    """Create a new user (XP entry)."""
    if "username" not in data or "user_id" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: user_id or username")

    payload = _filter_payload(data, USER_COLUMNS)
    return supabase_request("POST", "users", data=payload)

# ============ UPDATE ENDPOINTS ============

@app.patch("/hr/{user_id}")
def update_hr(user_id: str, data: dict):
    """Update an HR row."""
    payload = _filter_payload(data, HR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for HR")
    return supabase_request("PATCH", "HRs", data=payload, record_id=user_id)

@app.patch("/lr/{user_id}")
def update_lr(user_id: str, data: dict):
    """Update an LR row."""
    payload = _filter_payload(data, LR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for LR")
    return supabase_request("PATCH", "LRs", data=payload, record_id=user_id)

@app.patch("/users/{user_id}")
def update_user(user_id: str, data: dict):
    """Update a user's XP or username."""
    payload = _filter_payload(data, USER_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for user")
    return supabase_request("PATCH", "users", data=payload, record_id=user_id)

# ============ DELETE ENDPOINTS ============

@app.delete("/hr/{user_id}")
def delete_hr(user_id: str):
    """Delete an HR row"""
    return supabase_request("DELETE", "HRs", record_id=user_id)

@app.delete("/lr/{user_id}")
def delete_lr(user_id: str):
    """Delete an LR row"""
    return supabase_request("DELETE", "LRs", record_id=user_id)

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    """Delete a user row"""
    return supabase_request("DELETE", "users", record_id=user_id)

# ============ HEALTH CHECK ============

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test Supabase connection
        response = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=HEADERS)
        if response.status_code == 200:
            return {"status": "healthy", "supabase": "connected"}
        else:
            return {"status": "unhealthy", "supabase": f"error: {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
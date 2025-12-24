# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
from typing import Optional

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
    "Content-Type": "application/json"
}

# Helper function to make Supabase requests
def supabase_request(method, table, data=None, params=None, record_id=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    if record_id:
        url = f"{url}?id=eq.{record_id}"
    
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

@app.get("/")
def root():
    return {"message": "Bot API is running"}

# ============ GET ENDPOINTS (Existing - keep these) ============

@app.get("/leaderboard")
def leaderboard():
    params = {
        "select": "user_id,username,xp",
        "order": "xp.desc",
        "limit": "10"
    }
    return supabase_request("GET", "users", params=params)

@app.get("/hr")
def get_hr():
    params = {"order": "user_id"}
    return supabase_request("GET", "HRs", params=params)

@app.get("/lr")
def get_lr():
    params = {"order": "user_id"}
    return supabase_request("GET", "LRs", params=params)

# ============ CREATE ENDPOINTS (New) ============

# Allowed columns per table (to avoid sending invalid columns to Supabase)
HR_COLUMNS = {
    "user_id",
    "username",
    "tryouts",
    "events",
    "phases",
    "courses",
    "inspections",
    "joint_events",
}

LR_COLUMNS = {
    "user_id",
    "username",
    "activity",
    "time_guarded",
    "events_attended",
}

USER_COLUMNS = {
    "user_id",
    "username",
    "xp",
}


def _filter_payload(data: dict, allowed_keys: set[str]) -> dict:
    """Return a copy of data containing only keys that exist in the table.

    This prevents 400s from Supabase when the payload contains unknown columns.
    """
    return {k: v for k, v in data.items() if k in allowed_keys}


@app.post("/hr")
def create_hr(data: dict):
    """Create a new HR row.

    Only "username" is required; "user_id" and stat columns are optional
    and can be filled in later or defaulted in the database.
    """
    if "username" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: username")

    payload = _filter_payload(data, HR_COLUMNS)
    return supabase_request("POST", "HRs", data=payload)


@app.post("/lr")
def create_lr(data: dict):
    """Create a new LR row.

    Only "username" is required; "user_id" and stat columns are optional.
    """
    if "username" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: username")

    payload = _filter_payload(data, LR_COLUMNS)
    return supabase_request("POST", "LRs", data=payload)


@app.post("/users")
def create_user(data: dict):
    """Create a new user (XP entry).

    Only "username" is required; "user_id" and "xp" are optional.
    """
    if "username" not in data:
        raise HTTPException(status_code=400, detail="Missing required field: username")

    payload = _filter_payload(data, USER_COLUMNS)
    return supabase_request("POST", "users", data=payload)


# ============ UPDATE ENDPOINTS (New) ============

@app.put("/hr/{hr_id}")
def update_hr(hr_id: str, data: dict):
    """Update an HR row (any of the stat columns or username)."""
    payload = _filter_payload(data, HR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for HR")
    return supabase_request("PATCH", "HRs", data=payload, record_id=hr_id)


@app.put("/lr/{lr_id}")
def update_lr(lr_id: str, data: dict):
    """Update an LR row (any of the stat columns or username)."""
    payload = _filter_payload(data, LR_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for LR")
    return supabase_request("PATCH", "LRs", data=payload, record_id=lr_id)


@app.put("/users/{user_id}")
def update_user(user_id: str, data: dict):
    """Update a user's XP or username."""
    payload = _filter_payload(data, USER_COLUMNS)
    if not payload:
        raise HTTPException(status_code=400, detail="No valid fields to update for user")
    return supabase_request("PATCH", "users", data=payload, record_id=user_id)


# ============ DELETE ENDPOINTS (New) ============

@app.delete("/hr/{hr_id}")
def delete_hr(hr_id: str):
    """Delete an HR row"""
    return supabase_request("DELETE", "HRs", record_id=hr_id)


@app.delete("/lr/{lr_id}")
def delete_lr(lr_id: str):
    """Delete an LR row"""
    return supabase_request("DELETE", "LRs", record_id=lr_id)


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    """Delete a user row"""
    return supabase_request("DELETE", "users", record_id=user_id)

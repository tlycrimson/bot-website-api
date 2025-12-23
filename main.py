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

@app.post("/hr")
def create_hr(data: dict):
    """Create a new HR member"""
    required_fields = ["username", "discord_id", "division", "rank"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    return supabase_request("POST", "HRs", data=data)

@app.post("/lr")
def create_lr(data: dict):
    """Create a new LR member"""
    required_fields = ["username", "discord_id", "division", "rank"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    return supabase_request("POST", "LRs", data=data)

@app.post("/users")
def create_user(data: dict):
    """Create a new user"""
    required_fields = ["user_id", "username"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    return supabase_request("POST", "users", data=data)

# ============ UPDATE ENDPOINTS (New) ============

@app.put("/hr/{hr_id}")
def update_hr(hr_id: str, data: dict):
    """Update an HR member"""
    return supabase_request("PATCH", "HRs", data=data, record_id=hr_id)

@app.put("/lr/{lr_id}")
def update_lr(lr_id: str, data: dict):
    """Update an LR member"""
    return supabase_request("PATCH", "LRs", data=data, record_id=lr_id)

@app.put("/users/{user_id}")
def update_user(user_id: str, data: dict):
    """Update a user's XP/level"""
    return supabase_request("PATCH", "users", data=data, record_id=user_id)

# ============ DELETE ENDPOINTS (New) ============

@app.delete("/hr/{hr_id}")
def delete_hr(hr_id: str):
    """Delete an HR member"""
    return supabase_request("DELETE", "HRs", record_id=hr_id)

@app.delete("/lr/{lr_id}")
def delete_lr(lr_id: str):
    """Delete an LR member"""
    return supabase_request("DELETE", "LRs", record_id=lr_id)

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    """Delete a user"""
    return supabase_request("DELETE", "users", record_id=user_id)
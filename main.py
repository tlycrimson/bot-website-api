# main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from supabase import create_client, Client
import os

# Import authentication
from auth import get_api_key

# Initialize FastAPI
app = FastAPI(title="Bot Admin API", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client using Render environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase environment variables in Render")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Test connection
print(f"✅ Connected to Supabase at: {SUPABASE_URL}")

# Pydantic models
class HRCreate(BaseModel):
    username: str
    discord_id: str
    division: str
    rank: str
    join_date: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"

class HRUpdate(BaseModel):
    username: Optional[str] = None
    discord_id: Optional[str] = None
    division: Optional[str] = None
    rank: Optional[str] = None
    join_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class LRCreate(BaseModel):
    username: str
    discord_id: str
    division: str
    rank: str
    join_date: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"

class LRUpdate(BaseModel):
    username: Optional[str] = None
    discord_id: Optional[str] = None
    division: Optional[str] = None
    rank: Optional[str] = None
    join_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    xp: Optional[int] = None
    level: Optional[int] = None

class BulkUpdateRequest(BaseModel):
    ids: List[str]
    updates: dict

# ==================== PUBLIC ENDPOINTS (No auth needed) ====================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "message": "Bot Admin API is running",
        "status": "healthy",
        "supabase_connected": bool(SUPABASE_URL and SUPABASE_KEY),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/leaderboard")
def leaderboard():
    """Get XP leaderboard"""
    try:
        res = supabase.table("users") \
            .select("user_id, username, xp, level") \
            .order("xp", desc=True) \
            .limit(10) \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/hr")
def get_hr():
    """Get all HR members"""
    try:
        res = supabase.table("HRs") \
            .select("*") \
            .order("username") \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/lr")
def get_lr():
    """Get all LR members"""
    try:
        res = supabase.table("LRs") \
            .select("*") \
            .order("username") \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== PROTECTED ENDPOINTS (Require API key) ====================

@app.post("/hr")
def create_hr(hr_data: HRCreate, api_key: str = Depends(get_api_key)):
    """Create a new HR member"""
    try:
        # Check if HR member already exists
        existing = supabase.table("HRs") \
            .select("*") \
            .or_(f"username.eq.{hr_data.username},discord_id.eq.{hr_data.discord_id}") \
            .execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="HR member already exists")
        
        # Prepare data
        hr_dict = hr_data.dict()
        hr_dict["created_at"] = datetime.utcnow().isoformat()
        hr_dict["updated_at"] = datetime.utcnow().isoformat()
        
        if not hr_dict.get("join_date"):
            hr_dict["join_date"] = datetime.utcnow().date().isoformat()
        
        # Insert into database
        res = supabase.table("HRs") \
            .insert(hr_dict) \
            .execute()
        
        return {
            "success": True,
            "message": "HR member created successfully",
            "data": res.data[0] if res.data else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/hr/{hr_id}")
def update_hr(hr_id: str, hr_data: HRUpdate, api_key: str = Depends(get_api_key)):
    """Update an existing HR member"""
    try:
        # Check if HR member exists
        existing = supabase.table("HRs") \
            .select("*") \
            .eq("id", hr_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="HR member not found")
        
        # Prepare update data
        update_data = hr_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Check for duplicates if updating username or discord_id
        if update_data.get("username") or update_data.get("discord_id"):
            duplicate_check = supabase.table("HRs") \
                .select("*") \
                .neq("id", hr_id)
            
            conditions = []
            if update_data.get("username"):
                conditions.append(f"username.eq.{update_data['username']}")
            if update_data.get("discord_id"):
                conditions.append(f"discord_id.eq.{update_data['discord_id']}")
            
            if conditions:
                duplicate_check = duplicate_check.or_(",".join(conditions))
                duplicates = duplicate_check.execute()
                
                if duplicates.data:
                    raise HTTPException(status_code=400, detail="Another HR member already exists with this username or Discord ID")
        
        # Update the record
        res = supabase.table("HRs") \
            .update(update_data) \
            .eq("id", hr_id) \
            .execute()
        
        return {
            "success": True,
            "message": "HR member updated successfully",
            "data": res.data[0] if res.data else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/hr/{hr_id}")
def delete_hr(hr_id: str, api_key: str = Depends(get_api_key)):
    """Delete an HR member"""
    try:
        # Check if HR member exists
        existing = supabase.table("HRs") \
            .select("*") \
            .eq("id", hr_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="HR member not found")
        
        # Delete the record
        supabase.table("HRs") \
            .delete() \
            .eq("id", hr_id) \
            .execute()
        
        return {
            "success": True,
            "message": "HR member deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== LR ENDPOINTS (Same pattern as HR) ====================

@app.post("/lr")
def create_lr(lr_data: LRCreate, api_key: str = Depends(get_api_key)):
    """Create a new LR member"""
    try:
        # Check if LR member already exists
        existing = supabase.table("LRs") \
            .select("*") \
            .or_(f"username.eq.{lr_data.username},discord_id.eq.{lr_data.discord_id}") \
            .execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="LR member already exists")
        
        # Prepare data
        lr_dict = lr_data.dict()
        lr_dict["created_at"] = datetime.utcnow().isoformat()
        lr_dict["updated_at"] = datetime.utcnow().isoformat()
        
        if not lr_dict.get("join_date"):
            lr_dict["join_date"] = datetime.utcnow().date().isoformat()
        
        # Insert into database
        res = supabase.table("LRs") \
            .insert(lr_dict) \
            .execute()
        
        return {
            "success": True,
            "message": "LR member created successfully",
            "data": res.data[0] if res.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/lr/{lr_id}")
def update_lr(lr_id: str, lr_data: LRUpdate, api_key: str = Depends(get_api_key)):
    """Update an existing LR member"""
    try:
        # Check if LR member exists
        existing = supabase.table("LRs") \
            .select("*") \
            .eq("id", lr_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="LR member not found")
        
        # Prepare update data
        update_data = lr_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the record
        res = supabase.table("LRs") \
            .update(update_data) \
            .eq("id", lr_id) \
            .execute()
        
        return {
            "success": True,
            "message": "LR member updated successfully",
            "data": res.data[0] if res.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/lr/{lr_id}")
def delete_lr(lr_id: str, api_key: str = Depends(get_api_key)):
    """Delete an LR member"""
    try:
        # Check if LR member exists
        existing = supabase.table("LRs") \
            .select("*") \
            .eq("id", lr_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="LR member not found")
        
        # Delete the record
        supabase.table("LRs") \
            .delete() \
            .eq("id", lr_id) \
            .execute()
        
        return {
            "success": True,
            "message": "LR member deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== USER/XP ENDPOINTS ====================

@app.get("/users")
def get_all_users():
    """Get all users (for admin panel)"""
    try:
        res = supabase.table("users") \
            .select("*") \
            .order("xp", desc=True) \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/users/{user_id}")
def update_user(user_id: str, user_data: UserUpdate, api_key: str = Depends(get_api_key)):
    """Update user XP and level"""
    try:
        # Check if user exists
        existing = supabase.table("users") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prepare update data
        update_data = user_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the record
        res = supabase.table("users") \
            .update(update_data) \
            .eq("user_id", user_id) \
            .execute()
        
        return {
            "success": True,
            "message": "User updated successfully",
            "data": res.data[0] if res.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/users/{user_id}")
def delete_user(user_id: str, api_key: str = Depends(get_api_key)):
    """Delete a user"""
    try:
        # Check if user exists
        existing = supabase.table("users") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete the record
        supabase.table("users") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== STATS ENDPOINT ====================

@app.get("/stats")
def get_stats():
    """Get overall statistics"""
    try:
        # Get counts (simplified version)
        hr_data = supabase.table("HRs").select("*").execute()
        lr_data = supabase.table("LRs").select("*").execute()
        user_data = supabase.table("users").select("*").execute()
        
        return {
            "hr_count": len(hr_data.data) if hr_data.data else 0,
            "lr_count": len(lr_data.data) if lr_data.data else 0,
            "user_count": len(user_data.data) if user_data.data else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
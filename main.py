# main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import json

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

# Check for environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase environment variables in Render")

print(f"✅ Supabase URL: {SUPABASE_URL}")
print(f"✅ Supabase Key present: {'Yes' if SUPABASE_KEY else 'No'}")

# Import and initialize Supabase client
try:
    # Use supabase-py which is simpler and doesn't require Rust
    from supabase_py import create_client
    
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized successfully")
    
except ImportError:
    # Fallback to requests-based implementation
    print("⚠️  supabase-py not available, using fallback implementation")
    import requests
    
    class SupabaseFallback:
        def __init__(self, url, key):
            self.url = url
            self.headers = {
                'apikey': key,
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            }
        
        def table(self, table_name):
            return SupabaseTable(self.url, table_name, self.headers)
    
    class SupabaseTable:
        def __init__(self, base_url, table_name, headers):
            self.base_url = f"{base_url}/rest/v1"
            self.table_name = table_name
            self.headers = headers
        
        def select(self, columns="*"):
            self.columns = columns
            return self
        
        def eq(self, column, value):
            self.eq_filter = (column, value)
            return self
        
        def order(self, column, desc=False):
            self.order_by = f"{column}.{'desc' if desc else 'asc'}"
            return self
        
        def limit(self, count):
            self.limit_count = count
            return self
        
        def execute(self):
            url = f"{self.base_url}/{self.table_name}"
            params = {
                'select': self.columns if hasattr(self, 'columns') else '*'
            }
            
            if hasattr(self, 'eq_filter'):
                column, value = self.eq_filter
                params[f'{column}'] = f'eq.{value}'
            
            if hasattr(self, 'order_by'):
                params['order'] = self.order_by
            
            if hasattr(self, 'limit_count'):
                params['limit'] = self.limit_count
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            class Result:
                def __init__(self, data):
                    self.data = data
            
            return Result(response.json())
        
        def insert(self, data):
            url = f"{self.base_url}/{self.table_name}"
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            class Result:
                def __init__(self, data):
                    self.data = data
            
            return Result(response.json())
        
        def update(self, data):
            url = f"{self.base_url}/{self.table_name}"
            if hasattr(self, 'eq_filter'):
                column, value = self.eq_filter
                url += f"?{column}=eq.{value}"
            
            response = requests.patch(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            class Result:
                def __init__(self, data):
                    self.data = data
            
            return Result(response.json())
        
        def delete(self):
            url = f"{self.base_url}/{self.table_name}"
            if hasattr(self, 'eq_filter'):
                column, value = self.eq_filter
                url += f"?{column}=eq.{value}"
            
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            
            class Result:
                def __init__(self):
                    self.data = []
            
            return Result()
    
    supabase = SupabaseFallback(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Using fallback Supabase client")

# Pydantic models (same as before)
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

# ==================== HELPER FUNCTIONS ====================

def execute_safe(query):
    """Execute Supabase query with error handling"""
    try:
        return query.execute()
    except Exception as e:
        print(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ==================== PUBLIC ENDPOINTS ====================

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

# ==================== PROTECTED ENDPOINTS ====================

@app.post("/hr")
def create_hr(hr_data: HRCreate, api_key: str = Depends(get_api_key)):
    """Create a new HR member"""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/hr/{hr_id}")
def update_hr(hr_id: str, hr_data: HRUpdate, api_key: str = Depends(get_api_key)):
    """Update an existing HR member"""
    try:
        # Prepare update data
        update_data = hr_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the record
        res = supabase.table("HRs") \
            .update(update_data) \
            .eq("id", hr_id) \
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="HR member not found")
        
        return {
            "success": True,
            "message": "HR member updated successfully",
            "data": res.data[0] if res.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/hr/{hr_id}")
def delete_hr(hr_id: str, api_key: str = Depends(get_api_key)):
    """Delete an HR member"""
    try:
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

# ==================== LR ENDPOINTS ====================

@app.post("/lr")
def create_lr(lr_data: LRCreate, api_key: str = Depends(get_api_key)):
    """Create a new LR member"""
    try:
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
        # Prepare update data
        update_data = lr_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the record
        res = supabase.table("LRs") \
            .update(update_data) \
            .eq("id", lr_id) \
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="LR member not found")
        
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
        # Prepare update data
        update_data = user_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the record
        res = supabase.table("users") \
            .update(update_data) \
            .eq("user_id", user_id) \
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="User not found")
        
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
        # Get counts
        hr_res = supabase.table("HRs").select("*").execute()
        lr_res = supabase.table("LRs").select("*").execute()
        user_res = supabase.table("users").select("*").execute()
        
        return {
            "hr_count": len(hr_res.data) if hr_res.data else 0,
            "lr_count": len(lr_res.data) if lr_res.data else 0,
            "user_count": len(user_res.data) if user_res.data else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
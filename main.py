from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase_client import supabase

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Bot API is running"}

@app.get("/leaderboard")
def leaderboard():
    res = supabase.table("users") \
        .select("user_id, username, xp") \
        .order("xp", desc=True) \
        .limit(10) \
        .execute()
    return res.data

@app.get("/hr")
def get_hr():
    res = supabase.table("HRs") \
        .select("*") \
        .order("user_id") \
        .execute()
    return res.data

@app.get("/lr")
def get_lr():
    res = supabase.table("LRs") \
        .select("*") \
        .order("user_id") \
        .execute()
    return res.data


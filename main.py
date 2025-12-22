from fastapi import FastAPI
from supabase_client import supabase

app = FastAPI()

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

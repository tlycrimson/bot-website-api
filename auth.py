# auth.py
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
import os

# Get API key from Render environment
API_KEY = os.environ.get("API_KEY", "default-dev-key")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )
    
    if api_key != API_KEY and API_KEY != "default-dev-key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return api_key
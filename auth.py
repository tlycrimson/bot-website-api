# auth.py
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
import os

# Get API key from Render environment variables
API_KEY = os.environ.get("API_KEY", "default-dev-key-if-not-set")
API_KEY_NAME = "X-API-Key"

# Create API key header
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Validate API key from header.
    Returns the API key if valid, raises HTTPException if not.
    """
    # If no API key is set in environment, allow all requests (development only!)
    if API_KEY == "default-dev-key-if-not-set":
        print("⚠️  WARNING: Running without API key authentication (development mode)")
        return "development-key"
    
    # Check if API key is provided
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Check if API key is valid
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key_header

# Simple verification function for direct use
def verify_api_key(api_key: str) -> bool:
    """Simple verification without raising exceptions"""
    if not api_key:
        return False
    
    if API_KEY == "default-dev-key-if-not-set":
        return True
    
    return api_key == API_KEY
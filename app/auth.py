from fastapi import HTTPException, Depends, Header
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

GLOBAL_API_KEY = os.getenv("API_KEY")

if not GLOBAL_API_KEY:
    raise ValueError("API_KEY environment variable is required")


async def verify_global_api_key(x_api_key: str = Header(..., description="Global API key")):
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key is required. Provide X-API-Key header."
        )
    
    if x_api_key != GLOBAL_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return True


async def get_global_auth(auth = Depends(verify_global_api_key)):
    return auth


async def optional_global_auth(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key != GLOBAL_API_KEY:
        return False
    return True
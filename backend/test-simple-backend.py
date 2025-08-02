#!/usr/bin/env python3
"""Simple backend test with just auth endpoints"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Set up environment
os.environ["REDIS_URL"] = "redis://localhost:6379"

from core.auth import authenticate_user, create_user_session

app = FastAPI(title="AuraConnect Test")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AuraConnect Test API is running"}

@app.post("/auth/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
):
    """Test login endpoint"""
    try:
        print(f"Login attempt: {form_data.username}")
        
        # Authenticate user
        user = authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # Create session
        session_data = create_user_session(user, request)
        
        return {
            "access_token": session_data["access_token"],
            "refresh_token": session_data["refresh_token"],
            "token_type": session_data["token_type"]
        }
        
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

if __name__ == "__main__":
    print("Starting test backend on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
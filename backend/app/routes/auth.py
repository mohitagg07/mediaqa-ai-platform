"""
auth.py

FIX: Register endpoint was using UserCreate schema which required email.
     Frontend sends only {username, password} → caused 422 Unprocessable Entity.
     Now email is Optional with a default of "".
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.services import mongo_service
from app.utils.jwt_utils import hash_password, verify_password, create_access_token
from app.models.schemas import UserLogin, Token
import logging

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = ""   # optional — not required


@router.post("/register", status_code=201)
async def register(user: UserRegister):
    if len(user.username.strip()) < 2:
        raise HTTPException(400, "Username must be at least 2 characters")
    if len(user.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")

    saved = await mongo_service.save_user({
        "username":        user.username.strip(),
        "email":           user.email or "",
        "hashed_password": hash_password(user.password),
    })
    if not saved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    logger.info(f"Registered: {user.username}")
    return {"message": f"Account created for '{user.username}'"}


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    db_user = await mongo_service.get_user(credentials.username)
    if not db_user or not verify_password(credentials.password, db_user["hashed_password"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": credentials.username})
    logger.info(f"Login: {credentials.username}")
    return Token(access_token=token)

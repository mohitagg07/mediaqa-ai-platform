from fastapi import APIRouter, HTTPException, status
from app.models.schemas import UserCreate, UserLogin, Token
from app.services import mongo_service
from app.utils.jwt_utils import hash_password, verify_password, create_access_token
import logging

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """Register a new user account."""
    user_data = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hash_password(user.password),
    }
    saved = await mongo_service.save_user(user_data)
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    logger.info(f"Registered new user: {user.username}")
    return {"message": f"User '{user.username}' created successfully"}


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate and return a JWT token."""
    db_user = await mongo_service.get_user(credentials.username)
    if not db_user or not verify_password(credentials.password, db_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": credentials.username})
    logger.info(f"User logged in: {credentials.username}")
    return Token(access_token=token)

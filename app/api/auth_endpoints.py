# ============================================================
# auth_endpoints.py — User signup and login endpoints
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.auth import (
    hash_password, verify_password, create_access_token,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse, Token


router = APIRouter()


@router.post("/auth/signup", response_model=Token)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    Returns a JWT token immediately so the user is logged in.
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user with hashed password
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate token immediately so user is logged in
    access_token = create_access_token(
        data={"user_id": new_user.id, "email": new_user.email},
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=new_user
    )


@router.post("/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with username (or email) and password.
    Returns a JWT token.
    
    Note: form_data uses 'username' field but we accept email too.
    """
    # Try to find user by email or username
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Generate token
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(__import__('app.core.auth', fromlist=['get_current_user']).get_current_user)):
    """Get the current logged-in user's info."""
    return current_user
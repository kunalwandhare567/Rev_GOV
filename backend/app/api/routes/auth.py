"""
JWT Authentication Routes
Separate admin and officer logins, JWT token issuance.
No hardcoded credentials — all loaded from settings/DB.
"""
import logging
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

pwd_ctx = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ALGORITHM = "HS256"


# ── Schemas ──

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    expires_in: int


class UserInfo(BaseModel):
    username: str
    role: str


# ── Helpers ──

def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _create_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["exp"] = expire
    payload["iat"] = datetime.datetime.utcnow()
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: decode JWT and return the User ORM object."""
    payload = _decode_token(token)
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def require_officer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("ADMIN", "OFFICER"):
        raise HTTPException(status_code=403, detail="Officer role required")
    return current_user


# ── Endpoints ──

@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Issue JWT token for admin or officer login.
    Accepts username + password (form data).
    """
    user = db.query(User).filter(
        User.username == form_data.username,
        User.is_active == True,
    ).first()

    if not user or not _verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_token({"sub": user.username, "role": user.role})
    expire_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(f"Login: {user.username} ({user.role})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
        expires_in=expire_seconds,
    )


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)):
    """Return current user info from JWT."""
    return UserInfo(username=current_user.username, role=current_user.role)


@router.post("/logout")
def logout():
    """
    JWT is stateless — logout is handled client-side by deleting the token.
    This endpoint exists for audit trail purposes.
    """
    return {"message": "Logged out. Please delete your token client-side."}

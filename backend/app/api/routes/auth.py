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
from app.models.db_models import User, Citizen

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


class CitizenRegisterRequest(BaseModel):
    identifier: str              # Phone (+91XXXXXXXXXX) or Email (citizen@example.com)
    password: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CitizenLoginRequest(BaseModel):
    identifier: str              # Phone or Email
    password: str


class CitizenAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "CITIZEN"
    citizen_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    expires_in: int


class CitizenProfileResponse(BaseModel):
    citizen_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    preferred_language: str = "en"


class CitizenProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


# ── Helpers ──

def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


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


def get_current_citizen(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Security dependency: decode JWT token and return authenticated Citizen.
    Throws 401 Unauthorized if invalid or missing token.
    """
    from app.data_layer.repositories.citizen_repo import CitizenRepository
    payload = _decode_token(token)
    citizen_ref: Optional[str] = payload.get("citizen_ref")
    username: Optional[str] = payload.get("sub")

    citizen_repo = CitizenRepository(db)

    citizen = None
    if citizen_ref:
        citizen = citizen_repo.get_by_ref(citizen_ref)
    if not citizen and username:
        citizen = citizen_repo.get_by_identifier(username)

    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated citizen account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return citizen


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

    token = _create_token({"sub": user.username, "role": user.role, "citizen_ref": user.citizen_ref})
    expire_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(f"Login: {user.username} ({user.role})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
        expires_in=expire_seconds,
    )


# ── CITIZEN AUTHENTICATION ENDPOINTS ──

@router.post("/citizen/register", response_model=CitizenAuthResponse)
def register_citizen(
    body: CitizenRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new citizen account using Email or Phone.
    Allocates a unique permanent citizen_id (CIT-001).
    Links ChannelIdentity for omnichannel recognition across Web, WhatsApp, IVR.
    """
    from app.data_layer.repositories.citizen_repo import CitizenRepository
    from app.data_layer.repositories.channel_identity_repo import ChannelIdentityRepository

    identifier = body.identifier.strip().lower()
    if not identifier:
        raise HTTPException(status_code=400, detail="Phone number or Email is required.")

    # Determine phone/email fields
    phone_val = body.phone or (identifier if "@" not in identifier else None)
    email_val = body.email or (identifier if "@" in identifier else None)

    # Check if user/citizen already exists across User and Citizen tables
    existing = db.query(User).filter(
        (User.username == identifier) |
        (User.username == (phone_val or "")) |
        (User.username == (email_val or ""))
    ).first()

    if not existing and phone_val:
        existing = db.query(Citizen).filter(Citizen.phone == phone_val).first()

    if not existing and email_val:
        existing = db.query(Citizen).filter(Citizen.email == email_val).first()

    if existing:
        raise HTTPException(status_code=400, detail="An account with this Email or Phone number already exists. Please sign in.")

    citizen_repo = CitizenRepository(db)
    channel_repo = ChannelIdentityRepository(db)

    # Create Citizen record with permanent citizen_id
    citizen = citizen_repo.create(
        name=body.name or "Citizen User",
        phone=phone_val,
        email=email_val,
        address=body.address,
    )

    # Create User authentication record
    hashed_pw = _hash_password(body.password)
    user = User(
        username=identifier,
        hashed_password=hashed_pw,
        role="CITIZEN",
        citizen_ref=citizen.citizen_ref,
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Link ChannelIdentities for Web, WhatsApp, IVR
    if phone_val:
        channel_repo.create(
            citizen_ref=citizen.citizen_ref,
            channel="WHATSAPP",
            identifier=phone_val,
            identifier_type="WHATSAPP_NUMBER",
            verified=True,
        )
        channel_repo.create(
            citizen_ref=citizen.citizen_ref,
            channel="IVR",
            identifier=phone_val,
            identifier_type="PHONE",
            verified=True,
        )
    if email_val:
        channel_repo.create(
            citizen_ref=citizen.citizen_ref,
            channel="EMAIL",
            identifier=email_val,
            identifier_type="EMAIL",
            verified=True,
        )

    token = _create_token({
        "sub": user.username,
        "role": "CITIZEN",
        "citizen_ref": citizen.citizen_ref,
    })

    logger.info(f"Citizen Registered: {citizen.citizen_ref} ({user.username})")

    return CitizenAuthResponse(
        access_token=token,
        token_type="bearer",
        role="CITIZEN",
        citizen_id=citizen.citizen_ref,
        name=citizen.name,
        email=citizen.email,
        phone=citizen.phone,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/citizen/login", response_model=CitizenAuthResponse)
def login_citizen(
    body: CitizenLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate citizen account via Email or Phone + password.
    Returns persistent citizen_id (CIT-001) and JWT bearer access token.
    """
    from app.data_layer.repositories.citizen_repo import CitizenRepository

    identifier = body.identifier.strip().lower()
    user = db.query(User).filter(User.username == identifier, User.is_active == True).first()

    if not user or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Email/Phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    citizen_repo = CitizenRepository(db)
    citizen = None
    if user.citizen_ref:
        citizen = citizen_repo.get_by_ref(user.citizen_ref)
    if not citizen:
        citizen = citizen_repo.resolve_or_create(identifier=identifier, name=user.username)
        user.citizen_ref = citizen.citizen_ref
        db.commit()

    token = _create_token({
        "sub": user.username,
        "role": "CITIZEN",
        "citizen_ref": citizen.citizen_ref,
    })

    logger.info(f"Citizen Login Successful: {citizen.citizen_ref} ({user.username})")

    return CitizenAuthResponse(
        access_token=token,
        token_type="bearer",
        role="CITIZEN",
        citizen_id=citizen.citizen_ref,
        name=citizen.name,
        email=citizen.email,
        phone=citizen.phone,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/citizen/profile", response_model=CitizenProfileResponse)
def get_citizen_profile(
    current_citizen = Depends(get_current_citizen),
):
    """Get authenticated citizen profile details."""
    return CitizenProfileResponse(
        citizen_id=current_citizen.citizen_ref,
        name=current_citizen.name or "Citizen User",
        phone=current_citizen.phone,
        email=current_citizen.email,
        address=current_citizen.address,
        preferred_language=current_citizen.preferred_language or "en",
    )


@router.patch("/citizen/profile", response_model=CitizenProfileResponse)
def update_citizen_profile(
    body: CitizenProfileUpdateRequest,
    current_citizen = Depends(get_current_citizen),
    db: Session = Depends(get_db),
):
    """Update authenticated citizen profile details."""
    from app.data_layer.repositories.citizen_repo import CitizenRepository
    repo = CitizenRepository(db)
    updated = repo.update_profile(
        citizen_ref=current_citizen.citizen_ref,
        name=body.name,
        phone=body.phone,
        email=body.email,
        address=body.address,
    )
    return CitizenProfileResponse(
        citizen_id=updated.citizen_ref,
        name=updated.name,
        phone=updated.phone,
        email=updated.email,
        address=updated.address,
        preferred_language=updated.preferred_language or "en",
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


from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut, UserUpdate
from app.core.money import to_decimal
from app.services import auth_service

router = APIRouter()


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(payload: UserCreate, db: Session = Depends(get_db)):
    return auth_service.register_user(
        db, name=payload.name, email=payload.email, password=payload.password, phone=payload.phone, monthly_income=payload.monthly_income
    )


@router.post("/auth/login", response_model=Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut, tags=["users"])
def read_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/me", response_model=UserOut, tags=["users"])
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        user.name = data["name"].strip()
    if "phone" in data:
        user.phone = data["phone"]
    if data.get("monthly_income") is not None:
        user.monthly_income = to_decimal(data["monthly_income"])
    db.commit()
    db.refresh(user)
    return user

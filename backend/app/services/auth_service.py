from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.core.money import to_decimal
from app.core.security import hash_password, verify_password
from app.models import User

logger = get_logger("auth_service")


def register_user(db: Session, *, name: str, email: str, password: str, phone: str | None, monthly_income) -> User:
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("Email is already registered")
    user = User(name=name, email=email, phone=phone, monthly_income=to_decimal(monthly_income), password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Email is already registered")
    db.refresh(user)
    logger.info("user_registered", user_id=user.id)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    ok = verify_password(password, user.password_hash if user else None)
    if not ok:
        logger.warning("auth_failure", reason="invalid_credentials", path="/api/v1/auth/login")
        return None
    logger.info("login_success", user_id=user.id)
    return user

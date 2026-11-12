import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
logger = get_logger("auth")


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    from app.core.security import decode_access_token

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError):
        logger.warning("auth_failure", reason="invalid_token", path=request.url.path)
        raise credentials_error
    user = db.get(User, user_id)
    if user is None:
        logger.warning("auth_failure", reason="unknown_user", path=request.url.path)
        raise credentials_error
    return user

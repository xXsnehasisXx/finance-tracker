"""Password hashing (bcrypt) and JWT bearer tokens (PyJWT). The secret comes from SECRET_KEY."""
import datetime

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.telemetry import span

ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72  # bcrypt limit
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    raw = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    target = password_hash.encode("ascii") if password_hash else _DUMMY_HASH  # constant-ish time for unknown users
    ok = bcrypt.checkpw(raw, target)
    return ok and password_hash is not None


def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = datetime.datetime.now(datetime.UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + datetime.timedelta(minutes=s.access_token_expire_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user id or raises jwt.PyJWTError."""
    with span("auth.validate") as sp:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        sp.set_attribute("auth.token_valid", True)
        return int(payload["sub"])

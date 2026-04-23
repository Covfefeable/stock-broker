from datetime import UTC, datetime, timedelta

import jwt
from flask import current_app


def create_access_token(user_id: int, email: str) -> str:
    expires_in = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
    )


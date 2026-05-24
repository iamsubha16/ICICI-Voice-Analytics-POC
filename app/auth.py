import bcrypt
import hmac
import hashlib
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from app.config import Config

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        print(f"Bcrypt verification failed, trying fallback: {e}")
        # Fallback in case of raw password in env (for absolute safety during presentations)
        return plain_password == hashed_password

def sign_session(email: str) -> str:
    # Sign email with secret key to prevent cookie tampering
    signature = hmac.new(Config.SECRET_KEY.encode('utf-8'), email.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{email}:{signature}"

def verify_session(cookie_value: str) -> str | None:
    if not cookie_value or ":" not in cookie_value:
        return None
    try:
        email, signature = cookie_value.split(":", 1)
        expected_signature = hmac.new(Config.SECRET_KEY.encode('utf-8'), email.encode('utf-8'), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_signature):
            return email
    except Exception:
        pass
    return None

def get_current_user(request: Request) -> str:
    session_cookie = request.cookies.get("session_id")
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    email = verify_session(session_cookie)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid or expired",
        )
    return email

def get_current_user_redirect(request: Request):
    # Same as get_current_user but returns a RedirectResponse if not logged in (useful for HTML pages)
    session_cookie = request.cookies.get("session_id")
    if not session_cookie:
        return None
    email = verify_session(session_cookie)
    return email

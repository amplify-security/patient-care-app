from fastapi import APIRouter, HTTPException, status, Request
import bcrypt
from app.database import get_db_connection
from app.schemas.auth import LoginRequest, TokenResponse
from app.auth.jwt_handler import create_access_token
from app.auth.lockout import is_locked, record_failure, clear_failures
from app.middleware.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, login_data: LoginRequest):
    if is_locked(login_data.email):
        log_audit(
            user_id=None,
            user_role=None,
            action="READ",
            resource_type="auth",
            details={"attempt": "login", "email": login_data.email, "reason": "account_locked"},
            ip_address=request.client.host if request.client else None,
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT id, email, password_hash, role, is_active FROM providers WHERE email = ?",
            (login_data.email,),
        )
        user = cursor.fetchone()

        if not user:
            record_failure(login_data.email)
            log_audit(
                user_id=None,
                user_role=None,
                action="READ",
                resource_type="auth",
                details={"attempt": "login", "email": login_data.email, "reason": "user_not_found"},
                ip_address=request.client.host if request.client else None,
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user["is_active"]:
            log_audit(
                user_id=user["id"],
                user_role=user["role"],
                action="READ",
                resource_type="auth",
                details={"attempt": "login", "reason": "account_inactive"},
                ip_address=request.client.host if request.client else None,
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not bcrypt.checkpw(login_data.password.encode(), user["password_hash"].encode()):
            record_failure(login_data.email)
            log_audit(
                user_id=user["id"],
                user_role=user["role"],
                action="READ",
                resource_type="auth",
                details={"attempt": "login", "reason": "invalid_password"},
                ip_address=request.client.host if request.client else None,
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        clear_failures(login_data.email)
        token = create_access_token(user["id"], user["email"], user["role"])

        log_audit(
            user_id=user["id"],
            user_role=user["role"],
            action="READ",
            resource_type="auth",
            details={"attempt": "login"},
            ip_address=request.client.host if request.client else None,
            success=True,
        )

        return TokenResponse(access_token=token)
    finally:
        conn.close()

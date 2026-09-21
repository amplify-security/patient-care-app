from datetime import datetime, timedelta, timezone

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# In-memory per-email tracking of failed login attempts.
_failed_attempts: dict[str, list[datetime]] = {}
_locked_until: dict[str, datetime] = {}


def is_locked(email: str) -> bool:
    locked_until = _locked_until.get(email)
    if locked_until is None:
        return False
    if datetime.now(timezone.utc) >= locked_until:
        _locked_until.pop(email, None)
        _failed_attempts.pop(email, None)
        return False
    return True


def record_failure(email: str) -> None:
    now = datetime.now(timezone.utc)
    attempts = _failed_attempts.setdefault(email, [])
    attempts.append(now)
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        _locked_until[email] = now + timedelta(minutes=LOCKOUT_MINUTES)


def clear_failures(email: str) -> None:
    _failed_attempts.pop(email, None)
    _locked_until.pop(email, None)

from fastapi import HTTPException, Request


def require_session(request: Request) -> None:
    """Raise 401 if the request has no valid session (user not authenticated)."""
    if not request.session.get("connected"):
        raise HTTPException(status_code=401, detail="Session expired or not authenticated")

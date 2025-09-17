
from typing import List, Optional
from fastapi import Header, Depends
from .security import verify_api_key, verify_jwt, Principal, AuthError
from .config import settings


async def get_current_principal(
x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Principal:

principal = verify_api_key(x_api_key)
if principal:
return principal



token = None
if authorization and authorization.lower().startswith("bearer "):
token = authorization.split(" ", 1)[1].strip()
principal = verify_jwt(token)
if principal:
return principal



if settings.AUTH_MODE == "api_key":
raise AuthError("Provide a valid X-API-Key header")
raise AuthError("Provide a valid Bearer token (and/or X-API-Key)")




def require_scopes(required: List[str]):
async def _inner(principal: Principal = Depends(get_current_principal)):

if settings.DEMO_MODE or settings.AUTH_MODE == "api_key":
return principal
if not principal.has_scopes(required):
raise AuthError(f"Insufficient scope. Need: {required}")
return principal
return _inner
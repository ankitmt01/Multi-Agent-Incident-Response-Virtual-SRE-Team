
from __future__ import annotations
import json, os, time
from typing import Dict, Set, List, Optional
from fastapi import Header, HTTPException

# Config
AUTH_MODE  = os.getenv("AUTH_MODE", "api_key").strip()          # api_key | scoped_jwt
DEMO_MODE  = os.getenv("DEMO_MODE", "false").lower() in ("1","true","yes")
API_KEY    = os.getenv("API_KEY", "changeme-local").strip()

JWT_SECRET   = os.getenv("JWT_SECRET", "please-change").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "incident-copilot").strip()
JWT_ISSUER   = os.getenv("JWT_ISSUER", "").strip()

# Optional: map keys -> scopes (your existing feature)
_raw = os.getenv("SCOPED_KEYS", "").strip()

def _parse_scoped_keys(raw: str) -> Dict[str, Set[str]]:
    if not raw: return {}
    # JSON form takes precedence
    if raw.startswith("{"):
        try: return {k: set(v) for k,v in json.loads(raw).items()}
        except Exception: return {}
    # "k1:run,execute; k2:kb,admin"
    out: Dict[str, Set[str]] = {}
    try:
        for part in [p.strip() for p in raw.split(";") if p.strip()]:
            k, scopes = part.split(":", 1)
            out[k.strip()] = set(s.strip() for s in scopes.split(",") if s.strip())
    except Exception:
        return {}
    return out

KEY_SCOPES: Dict[str, Set[str]] = _parse_scoped_keys(_raw)
ALL_SCOPES = {"run","execute","kb","audit","admin"}

class AuthError(HTTPException):
    def __init__(self, msg: str, code: int = 401):
        super().__init__(status_code=code, detail=msg, headers={"WWW-Authenticate":"Bearer"})

# Lazy import PyJWT
try:
    import jwt  # PyJWT
except Exception:
    jwt = None

def _principal(sub: str, scopes: List[str], mode: str):
    return {"sub": sub, "scopes": set(scopes), "mode": mode}

def _ok_for(scopes_have: Set[str], required: List[str]) -> bool:
    return set(required).issubset(scopes_have)

def _verify_jwt(bearer: Optional[str]):
    if DEMO_MODE: return _principal("demo", list(ALL_SCOPES), "demo")
    if AUTH_MODE != "scoped_jwt": return None
    if not bearer: raise AuthError("Missing bearer token")
    if jwt is None: raise AuthError("PyJWT not installed on server")
    try:
        data = jwt.decode(
            bearer, JWT_SECRET, algorithms=["HS256"],
            options={"verify_aud": bool(JWT_AUDIENCE)},
            audience=(JWT_AUDIENCE or None),
            issuer=(JWT_ISSUER or None)
        )
    except Exception as e:
        raise AuthError(f"Invalid token: {e}")
    # scopes can be 'scope' (space-delimited) or 'scopes' (array)
    raw = data.get("scope") or data.get("scopes") or []
    scopes = raw.split() if isinstance(raw,str) else list(raw)
    sub = data.get("sub") or data.get("uid") or "unknown"
    if "exp" in data and data["exp"] < int(time.time()):
        raise AuthError("Token expired")
    return _principal(sub, scopes, "jwt")

def _verify_key(x_api_key: Optional[str]):
    if DEMO_MODE: return _principal("demo", list(ALL_SCOPES), "demo")
    if x_api_key and API_KEY and x_api_key == API_KEY:
        # full access (superuser) for ops
        return _principal("apikey", list(ALL_SCOPES), "api_key")
    if x_api_key and x_api_key in KEY_SCOPES:
        return _principal("scopedkey", list(KEY_SCOPES[x_api_key]), "scoped_key")
    return None

def require_scopes(required: List[str]):
    """
    Usage: Depends(require_scopes(["run"])) etc.
    Modes:
      - DEMO_MODE: allow all.
      - api_key:    X-API-Key==API_KEY => all scopes; or SCOPED_KEYS per-key scopes.
      - scoped_jwt: X-API-Key==API_KEY => all scopes; else Bearer JWT scopes required.
    """
    def _dep(
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        # Try API key path first (works in both modes)
        p = _verify_key(x_api_key)
        if not p and AUTH_MODE == "scoped_jwt":
            token = authorization.split(" ",1)[1].strip() if (authorization or "").lower().startswith("bearer ") else None
            p = _verify_jwt(token)

        if not p:
            if AUTH_MODE == "api_key":
                raise AuthError("Provide a valid X-API-Key header")
            raise AuthError("Provide a valid Bearer token (and/or X-API-Key)")

        # api_key superuser or demo bypass
        if p["mode"] in ("api_key","demo"):
            return p

        # Enforce scopes for scoped-key or jwt
        have = set(p["scopes"])
        if not _ok_for(have, required):
            raise AuthError(f"Insufficient scope. Need: {required}", 403)
        return p
    return _dep

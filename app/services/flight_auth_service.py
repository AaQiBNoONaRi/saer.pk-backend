"""
AIQS Flight Authentication Service
In-memory async token cache with lock to prevent duplicate auth calls.
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from app.config.settings import settings


class FlightAuthService:
    """Manages AIQS API authentication with async in-memory caching."""

    _tokens: dict | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_tokens(cls) -> dict:
        """Return cached tokens or authenticate fresh."""
        if cls._tokens and cls._tokens["expires_at"] > datetime.now():
            return cls._tokens

        async with cls._lock:
            # Double-check after acquiring lock (another coroutine may have refreshed)
            if cls._tokens and cls._tokens["expires_at"] > datetime.now():
                return cls._tokens
            return await cls._authenticate()

    @classmethod
    async def _authenticate(cls) -> dict:
        """Call AIQS auth endpoint and cache the result."""
        url = f"{settings.AIQS_AUTH_URL}/client/user/signin/initiate"
        payload = {
            "clientId": settings.AIQS_CLIENT_ID,
            "authFlow": "USER_PASSWORD_AUTH",
            "authParameters": {
                "PASSWORD": settings.AIQS_PASSWORD,
                "USERNAME": settings.AIQS_USERNAME,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract tokens (handle both casing styles)
        auth_result = None
        if "data" in data and "authenticationResult" in data["data"]:
            auth_result = data["data"]["authenticationResult"]
        elif "AuthenticationResult" in data:
            auth_result = data["AuthenticationResult"]

        if not auth_result:
            raise Exception("Invalid auth response — no authenticationResult key")

        access_token = auth_result.get("accessToken") or auth_result.get("AccessToken")
        id_token = auth_result.get("idToken") or auth_result.get("IdToken")
        expires_in = auth_result.get("expiresIn") or auth_result.get("ExpiresIn") or 3600

        if not access_token or not id_token:
            raise Exception("Tokens not found in auth response")

        cls._tokens = {
            "access_token": access_token,
            "id_token": id_token,
            "expires_at": datetime.now() + timedelta(seconds=expires_in),
            "expires_in": expires_in,
        }
        return cls._tokens

    @classmethod
    def clear_cache(cls):
        cls._tokens = None

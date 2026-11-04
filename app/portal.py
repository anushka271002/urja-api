import asyncio
import time
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

SESSION_REFRESH_SECONDS = 50 * 60  # portal session is 1h; refresh early


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    portal_url: str
    portal_email: str
    portal_password: str


class PortalError(Exception): ...
class PortalNotFound(PortalError): ...


class PortalClient:
    def __init__(self, settings: Settings):
        self._s = settings
        self._http = httpx.AsyncClient(
            base_url=settings.portal_url, timeout=15, follow_redirects=False,
            headers={"Origin": settings.portal_url},  # SvelteKit rejects form POSTs without it
        )
        self._lock = asyncio.Lock()
        self._login_at = 0.0
        self._generation = 0

    @property
    def session_age(self) -> float | None:
        return time.time() - self._login_at if self._login_at else None

    async def _login(self):
        r = await self._http.post(
            "/login",
            data={"email": self._s.portal_email, "password": self._s.portal_password},
            headers={"x-sveltekit-action": "true"},
        )
        has_cookie = any(c.name.endswith("session_token") for c in self._http.cookies.jar)
        if r.status_code != 200 or '"failure"' in r.text or not has_cookie:
            raise PortalError("portal login failed")
        self._login_at = time.time()
        self._generation += 1

    async def _ensure_login(self, seen_generation: int | None = None):
        """One login at a time; if someone else already re-logged-in, don't repeat it."""
        async with self._lock:
            stale = time.time() - self._login_at > SESSION_REFRESH_SECONDS
            if seen_generation is None and not stale:
                return
            if seen_generation is not None and seen_generation != self._generation:
                return
            await self._login()

    async def get_json(self, path: str, params: dict | None = None):
        for attempt in (1, 2):
            await self._ensure_login()
            gen = self._generation
            try:
                r = await self._http.get(path, params=params)
            except httpx.HTTPError as e:
                raise PortalError(f"portal unreachable: {e}") from e
            expired = r.status_code in (301, 302, 303, 307, 401, 403) or \
                "json" not in r.headers.get("content-type", "")
            if expired and attempt == 1:
                await self._ensure_login(seen_generation=gen)
                continue
            if r.status_code == 404:
                raise PortalNotFound(path)
            if r.status_code != 200 or expired:
                raise PortalError(f"portal returned {r.status_code} for {path}")
            return r.json()

    async def aclose(self):
        await self._http.aclose()
from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, field

import httpx

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RequestRecord:
    method: str
    url: str
    status: int
    request_body: str | None = None
    response_body: str = ""
    headers_sent: dict = field(default_factory=dict)


class AuthManager:
    def __init__(self):
        self.token: str | None = None
        self.credentials: dict[str, dict] = {}

    @property
    def has_token(self) -> bool:
        return self.token is not None

    def set_token(self, token: str, email: str, password: str) -> None:
        self.token = token
        self.credentials[email] = {"password": password, "token": token}

    def switch_user(self, email: str) -> bool:
        if email in self.credentials:
            self.token = self.credentials[email]["token"]
            return True
        return False

    def decode_jwt(self) -> dict | None:
        if not self.token:
            return None
        try:
            payload = self.token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            return None

    @property
    def current_user_email(self) -> str | None:
        claims = self.decode_jwt()
        if claims:
            return claims.get("data", {}).get("email")
        return None

    def clear(self) -> None:
        self.token = None


class HttpClient:
    def __init__(self, base_url: str, delay_ms: int = 200):
        self.base_url = base_url.rstrip("/")
        self.delay_ms = delay_ms
        self.auth = AuthManager()
        self.history: list[RequestRecord] = []
        self._client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            verify=False,
        )

    async def request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        json_body: dict | None = None,
        params: dict | None = None,
        data: str | None = None,
        inject_auth: bool = True,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        hdrs = dict(headers or {})

        if inject_auth and self.auth.has_token:
            hdrs.setdefault("Authorization", f"Bearer {self.auth.token}")

        kwargs: dict = {"headers": hdrs}
        if json_body is not None:
            kwargs["json"] = json_body
        if params is not None:
            kwargs["params"] = params
        if data is not None:
            kwargs["content"] = data

        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)

        resp = await self._client.request(method, url, **kwargs)

        self.history.append(RequestRecord(
            method=method,
            url=url,
            status=resp.status_code,
            request_body=json.dumps(json_body) if json_body else data,
            response_body=resp.text[:2000],
            headers_sent=hdrs,
        ))

        logger.debug(f"{method} {path} -> {resp.status_code}")
        return resp

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def login(self, email: str, password: str) -> bool:
        resp = await self.request(
            "POST", "/rest/user/login",
            json_body={"email": email, "password": password},
            inject_auth=False,
        )
        if resp.status_code == 200:
            token = resp.json().get("authentication", {}).get("token")
            if token:
                self.auth.set_token(token, email, password)
                logger.info(f"Logged in as {email}")
                return True
        return False

    async def register(self, email: str, password: str) -> bool:
        resp = await self.request(
            "POST", "/api/Users/",
            json_body={
                "email": email,
                "password": password,
                "passwordRepeat": password,
                "securityQuestion": {"id": 1, "question": "Your eldest siblings middle name?"},
                "securityAnswer": "test",
            },
            inject_auth=False,
        )
        return resp.status_code in (200, 201)

    async def close(self) -> None:
        await self._client.aclose()

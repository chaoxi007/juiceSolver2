from __future__ import annotations

from ..http_toolkit.client import HttpClient
from .base import ActionHandler, ActionResult


class LoginHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "login"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        http: HttpClient = context["http"]
        memory = context["memory"]

        email = params.get("email", "")
        password = params.get("password", "")
        if not email or not password:
            return ActionResult(status="error", error="'email' and 'password' are required")

        success = await http.login(email, password)
        if success:
            memory.write("credentials", email, {
                "password": password,
                "token": http.auth.token[:50] + "..." if http.auth.token else "",
                "method": "login",
            })
            return ActionResult(status="success", data={
                "authenticated": True,
                "user_email": email,
                "token_preview": http.auth.token[:30] + "..." if http.auth.token else "",
            })
        return ActionResult(status="error", error=f"Login failed for {email}")


class RegisterUserHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "register_user"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        http: HttpClient = context["http"]

        email = params.get("email", "")
        password = params.get("password", "")
        role = params.get("role")
        if not email or not password:
            return ActionResult(status="error", error="'email' and 'password' are required")

        body: dict = {
            "email": email,
            "password": password,
            "passwordRepeat": password,
            "securityQuestion": {"id": 1, "question": "Your eldest siblings middle name?"},
            "securityAnswer": "test",
        }
        if role:
            body["role"] = role

        resp = await http.request("POST", "/api/Users/", json_body=body, inject_auth=False)
        if resp.status_code in (200, 201):
            data = resp.json()
            return ActionResult(status="success", data={
                "registered": True,
                "user_id": data.get("data", {}).get("id"),
                "email": email,
            })
        return ActionResult(status="error", error=f"Registration failed: {resp.status_code} {resp.text[:200]}")

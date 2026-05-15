from __future__ import annotations

import httpx

from ..http_toolkit.client import HttpClient
from ..memory.store import MemoryStore
from .base import ActionHandler, ActionResult

# Endpoints worth remembering (non-SPA, non-trivial responses)
_INTERESTING_STATUSES = {200, 201, 401, 403}


class HttpRequestHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "http_request"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        http: HttpClient = context["http"]
        memory: MemoryStore = context["memory"]

        method = params.get("method", "GET").upper()
        path = params.get("path", "")
        if not path:
            return ActionResult(status="error", error="'path' is required")
        if not path.startswith("/"):
            path = "/" + path

        headers = params.get("headers")
        body = params.get("body")
        query_params = params.get("params")
        inject_auth = params.get("inject_auth", True)

        # Strip manual Authorization header — the agent should rely on inject_auth
        if inject_auth and headers and "Authorization" in headers:
            headers = {k: v for k, v in headers.items() if k != "Authorization"}

        try:
            resp = await http.request(
                method, path,
                headers=headers,
                json_body=body if isinstance(body, dict) else None,
                data=body if isinstance(body, str) else None,
                params=query_params,
                inject_auth=inject_auth,
            )
            resp_headers = dict(list(resp.headers.items())[:10])

            # Auto-record interesting endpoints to memory
            content_type = resp.headers.get("content-type", "")
            is_api = "json" in content_type or path.startswith(("/api/", "/rest/"))
            if resp.status_code in _INTERESTING_STATUSES and is_api:
                memory.write("endpoints", f"{method} {path}", {
                    "status": resp.status_code,
                    "content_type": content_type.split(";")[0],
                })

            return ActionResult(status="success", data={
                "status_code": resp.status_code,
                "headers": resp_headers,
                "body": resp.text[:3000],
            })
        except httpx.TimeoutException:
            return ActionResult(
                status="error",
                error=f"Request timed out after 10s: {method} {path}. "
                      f"The server did not respond. This endpoint may require "
                      f"external services (e.g. Dialogflow) or WebSocket. "
                      f"Consider trying a different approach or calling give_up.",
            )
        except Exception as e:
            return ActionResult(status="error", error=f"{type(e).__name__}: {str(e)}")

"""ActionHandler for extracting information from JavaScript source files.

Strategy for large files (main.js is typically 2-5MB minified):
1. Cache: fetch once per session, reuse across challenges.
2. Pre-compiled regex bank: patterns tuned for Juice Shop's webpack output.
3. Context windows: for each search hit, extract surrounding +/-200 chars.
"""
from __future__ import annotations

import re

from ..http_toolkit.client import HttpClient
from .base import ActionHandler, ActionResult

# Pre-compiled patterns for speed on large files
_PATTERNS: dict[str, re.Pattern] = {
    "crypto_urls": re.compile(
        r'["\']https?://[^"\']*(?:blockchain|etherscan|bitcoin|crypto|dash|ether|dogechain)[^"\']*["\']',
        re.IGNORECASE,
    ),
    "credentials": re.compile(
        r'(?:password|passwd|secret|credential|apikey|api_key|token)\s*[:=]\s*["\']([^"\']{3,60})["\']',
        re.IGNORECASE,
    ),
    "emails": re.compile(r'["\']([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6})["\']'),
    "allowlists": re.compile(
        r'(?:allow|white|redirect)\w{0,20}\s*[:=]\s*\[([^\]]{10,2000})\]',
        re.IGNORECASE,
    ),
    "routes": re.compile(r'["\']/(api|rest|ftp|b2b|redirect|file-upload|profile|socket)[^"\']{0,80}["\']'),
}

_CONTEXT_CHARS = 200


class AnalyzeJsHandler(ActionHandler):
    """Analyze JS source with caching and chunked extraction."""

    _cache: dict[str, str] = {}  # path -> content, shared across calls within session

    @property
    def name(self) -> str:
        return "analyze_js"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        http: HttpClient = context["http"]

        path = params.get("path", "/main.js")
        search_terms = params.get("search", [])
        if isinstance(search_terms, str):
            search_terms = [search_terms]

        # Resolve actual main.js path
        if path == "/main.js":
            index_resp = await http.request("GET", "/", inject_auth=False)
            match = re.search(r'src="(main[^"]*\.js)"', index_resp.text)
            if match:
                path = "/" + match.group(1)

        # Cache: only fetch once per session
        if path not in self._cache:
            resp = await http.request("GET", path, inject_auth=False)
            if resp.status_code != 200:
                return ActionResult(status="error", error=f"Failed to fetch {path}: {resp.status_code}")
            self._cache[path] = resp.text

        js = self._cache[path]
        size_mb = len(js) / (1024 * 1024)
        findings: list[str] = []

        # Run pre-built pattern bank
        for label, pattern in _PATTERNS.items():
            matches = pattern.findall(js)
            if matches:
                unique = list(set(matches))[:15]
                findings.append(f"[{label}] ({len(matches)} hits): {unique[:10]}")

        # User-specified search terms with context windows
        for term in search_terms:
            hits = [m.start() for m in re.finditer(re.escape(term), js, re.IGNORECASE)]
            if not hits:
                findings.append(f"[search] '{term}': NOT FOUND")
                continue
            findings.append(f"[search] '{term}': {len(hits)} occurrences")
            for idx in hits[:5]:
                start = max(0, idx - _CONTEXT_CHARS)
                end = min(len(js), idx + len(term) + _CONTEXT_CHARS)
                snippet = js[start:end].replace('\n', ' ').replace('\r', '')
                findings.append(f"  ...{snippet}...")

        if not findings:
            return ActionResult(status="success", data={
                "message": f"Fetched {path} ({size_mb:.1f}MB) but no notable patterns found. Try specific search terms.",
                "size_mb": round(size_mb, 1),
            })

        return ActionResult(status="success", data={
            "findings": findings,
            "size_mb": round(size_mb, 1),
            "cached": True,
        })

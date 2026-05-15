from __future__ import annotations

import json

from ..discovery.challenges import Challenge
from ..skills.hints import CHALLENGE_HINTS
from ..skills.library import ALL_SKILLS, GENERIC_SKILLS


ACTION_DOCS = """\
Available actions (reply with exactly one JSON object per turn):

1. use_skill — Execute a pre-built multi-step attack skill (PREFERRED)
   {"action": "use_skill", "params": {"skill": "<skill_name>", ...skill_params}}
   Skills run multiple steps automatically and call check_solved for you.

2. http_request — Send a raw HTTP request (use when no skill fits)
   {"action": "http_request", "params": {"method": "GET|POST|PUT|DELETE", "path": "/...", "headers": {}, "body": {}, "params": {}, "inject_auth": true}}

3. browser_navigate — Open a URL in a real browser (use for SPA routes with /#/, DOM XSS, or when http_request returns HTML shell without triggering the challenge)
   {"action": "browser_navigate", "params": {"path": "/#/some-route", "wait_until": "networkidle", "wait_for_selector": "css-selector", "extract_selector": "css-selector"}}
   Use this when: path contains /#/, challenge requires client-side rendering, or repeated http_request 200s don't solve the challenge.

4. analyze_js — Extract secrets, URLs, and patterns from JavaScript source files (use to find hardcoded credentials, redirect allowlists, API keys)
   {"action": "analyze_js", "params": {"path": "/main.js", "search": ["keyword1", "keyword2"]}}
   path defaults to the app's main bundle. Use search to look for specific terms in the JS source.

5. login — Authenticate and store token (token is auto-injected into subsequent requests)
   {"action": "login", "params": {"email": "...", "password": "..."}}
   NOTE: After login, all http_request calls automatically include the auth token. Do NOT manually set Authorization headers.

6. check_solved — Check if the current challenge is solved
   {"action": "check_solved", "params": {}}

7. think — Internal reasoning step (no side effects)
   {"action": "think", "params": {"reasoning": "..."}}

8. give_up — Abandon this challenge
   {"action": "give_up", "params": {"reason": "..."}}

9. read_memory / write_memory — Persistent memory access
   {"action": "read_memory", "params": {"category": "...", "key": "..."}}
   {"action": "write_memory", "params": {"category": "...", "key": "...", "value": ...}}
"""


def _format_known_hint(hint_data: dict) -> str:
    """Format a CHALLENGE_HINTS entry into a human-readable attack playbook."""
    lines = []
    if "approach" in hint_data:
        lines.append(f"  Approach: {hint_data['approach']}")
    if "note" in hint_data:
        lines.append(f"  Note: {hint_data['note']}")
    if "requires_auth" in hint_data:
        lines.append(f"  Requires auth: {hint_data['requires_auth']}")
    if "steps" in hint_data:
        lines.append("  Steps:")
        for i, step in enumerate(hint_data["steps"], 1):
            step_str = json.dumps(step, ensure_ascii=False)
            lines.append(f"    {i}. {step_str}")
    return "\n".join(lines)


def _build_skills_section(challenge_key: str) -> str:
    """Build the skills documentation section for the system prompt."""
    lines = ["== Available Skills =="]

    # Check for a direct solution skill
    solve_skill_name = f"solve_{challenge_key}"
    if solve_skill_name in ALL_SKILLS:
        skill = ALL_SKILLS[solve_skill_name]
        lines.append(f">>> RECOMMENDED: Use this skill to solve the challenge directly:")
        lines.append(f'    {{"action": "use_skill", "params": {{"skill": "{solve_skill_name}"}}}}')
        lines.append(f"    Description: {skill.description}")
        if skill.requires_auth:
            lines.append(f"    ⚠ Requires auth: {skill.requires_auth} (login first)")
        lines.append("")

    # List generic skills
    lines.append("Generic skills (provide required params):")
    for name, skill in GENERIC_SKILLS.items():
        param_str = ", ".join(f'"{k}": ...' for k in skill.params_schema)
        auth_note = f" [requires {skill.requires_auth}]" if skill.requires_auth else ""
        lines.append(f"  - {name}: {skill.description}{auth_note}")
        if param_str:
            lines.append(f'    {{"action": "use_skill", "params": {{"skill": "{name}", {param_str}}}}}')

    return "\n".join(lines)


def build_system_prompt(
    challenge: Challenge,
    memory_context: dict,
    max_turns: int,
    world_model_summary: str = "",
) -> str:
    parts = [
        "You are a security testing agent targeting OWASP Juice Shop.",
        "Your goal: solve the challenge below by discovering and exploiting vulnerabilities.",
        "Reply with exactly ONE JSON object per turn. No other text.",
        "",
        "== Actions ==",
        ACTION_DOCS,
        _build_skills_section(challenge.key),
        "",
        "== Current Challenge ==",
        f"Name: {challenge.name}",
        f"Key: {challenge.key}",
        f"Category: {challenge.category}",
        f"Difficulty: {challenge.difficulty}/6",
        f"Description: {challenge.description}",
    ]

    if challenge.hint:
        parts.append(f"Hint: {challenge.hint}")

    # Auto-inject known attack playbook from the knowledge base
    known_hint = CHALLENGE_HINTS.get(challenge.key)
    if known_hint:
        parts.append("")
        parts.append("== Known Attack Playbook (from knowledge base) ==")
        parts.append("A proven attack approach exists for this challenge. Follow it closely:")
        parts.append(_format_known_hint(known_hint))

    parts.append("")
    parts.append("== Memory Context ==")
    if memory_context.get("credentials"):
        parts.append(f"Known credentials: {json.dumps(memory_context['credentials'], ensure_ascii=False)}")
    if memory_context.get("endpoints"):
        parts.append(f"Endpoint intel: {json.dumps(memory_context['endpoints'], ensure_ascii=False)}")
    if memory_context.get("attack_results"):
        parts.append(f"Related attack results: {json.dumps(memory_context['attack_results'], ensure_ascii=False)}")
    if memory_context.get("target_profile"):
        parts.append(f"Target profile: {json.dumps(memory_context['target_profile'], ensure_ascii=False)}")
    if not any(memory_context.values()):
        parts.append("(No prior memory available)")

    if world_model_summary:
        parts.append("")
        parts.append("== World Model (accumulated knowledge about the target) ==")
        parts.append(world_model_summary)

    parts.append("")
    parts.append("== Rules ==")
    parts.extend([
        f"- You have at most {max_turns} turns.",
        "- **PREFER use_skill** over raw http_request when a matching skill exists.",
        "- If a solve_<challengeKey> skill is listed as RECOMMENDED, use it immediately.",
        "- After a successful attack, call check_solved to confirm (skills do this automatically).",
        "- Write important discoveries to memory (credentials, endpoints, techniques).",
        "- If stuck after several attempts, try a completely different approach or skill.",
        "- For authentication challenges, try known credentials from memory first.",
        "- **AUTH**: After login, tokens are auto-injected. NEVER manually set Authorization headers.",
        "- **JS ANALYSIS**: Use analyze_js to find hardcoded secrets, redirect allowlists, or credentials in frontend source code. This is essential for challenges involving exposed credentials or allowlist bypasses.",
        "- **GIVE UP POLICY**: If you receive the same error repeatedly (e.g., 500 Server Error) for 3+ attempts, or if you realize the challenge requires capabilities you don't have, call `give_up` immediately. Do not waste turns.",
    ])

    return "\n".join(parts)


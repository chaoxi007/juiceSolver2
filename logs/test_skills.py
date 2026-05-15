from src.skills.library import ALL_SKILLS, list_skills

print(f"Total skills: {len(ALL_SKILLS)}")
print()
for s in list_skills():
    name = s["name"]
    cat = s["category"]
    params = s["params"]
    print(f"  {name:35s} {cat:20s} {params}")

print()
print("--- Test prompt generation ---")
from src.discovery.challenges import Challenge
from src.agent.prompt import build_system_prompt

c = Challenge(id=1, key="loginAdminChallenge", name="Login Admin", category="Injection",
              difficulty=2, description="Log in as admin", hint="", solved=False)
prompt = build_system_prompt(c, {}, 25)
# Print just the skills section
for line in prompt.split("\n"):
    if "skill" in line.lower() or "RECOMMEND" in line:
        print(line)

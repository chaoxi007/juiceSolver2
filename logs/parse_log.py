import json

with open("logs/run_20260514_182752.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

current = ""
for l in lines:
    d = json.loads(l)
    ch = d["challenge"]
    if ch != current:
        print(f"\n=== {ch} ===")
        current = ch
    action = d["action"]
    status = d["result_status"]
    turn = d["turn"]
    # extra info
    extra = ""
    if action == "http_request":
        p = d.get("params", {})
        extra = f'{p.get("method","?")} {p.get("path","?")[:60]}'
    elif action == "login":
        extra = d.get("params", {}).get("email", "")
    elif action == "search_knowledge":
        extra = d.get("params", {}).get("query", "")[:40]
    elif action == "check_solved":
        rd = d.get("result_data", {})
        if isinstance(rd, dict):
            extra = f'solved={rd.get("solved","?")}'
    elif action == "think":
        extra = d.get("params", {}).get("reasoning", "")[:60]
    elif action == "give_up":
        extra = d.get("params", {}).get("reason", "")[:60]
    print(f"  T{turn:2d} {action:20s} [{status:7s}] {extra}")

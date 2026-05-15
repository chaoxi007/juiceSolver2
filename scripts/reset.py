"""Reset Juice Shop and local session state.

Usage:
    python scripts/reset.py                    # reset everything
    python scripts/reset.py --local-only       # only reset local files
    python scripts/reset.py --target http://localhost:3000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def reset_juice_shop(base_url: str) -> bool:
    """Reset Juice Shop by recreating the Docker container + applying blank state."""
    print(f"[*] Resetting Juice Shop at {base_url} ...")

    # Check current status
    try:
        r = httpx.get(f"{base_url}/api/Challenges/", timeout=10)
        challenges = r.json().get("data", [])
        solved = sum(1 for c in challenges if c.get("solved"))
        print(f"[*] Current: {solved}/{len(challenges)} challenges solved")
        if solved == 0:
            print("[*] Already clean!")
            return True
    except httpx.ConnectError:
        print(f"[!] Cannot connect to {base_url}. Is Juice Shop running?")
        return False

    # Find the running container
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}} {{.Image}} {{.Ports}}"],
            capture_output=True, text=True, timeout=10,
        )
        container_id = None
        for line in result.stdout.strip().split("\n"):
            if "juice-shop" in line.lower() or "3000->3000" in line:
                container_id = line.split()[0]
                break

        if not container_id:
            print("[!] Could not find Juice Shop container")
            return False

        # Get image name
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Config.Image}}", container_id],
            capture_output=True, text=True, timeout=10,
        )
        image = result.stdout.strip() or "bkimminich/juice-shop"

        # Remove old container
        print(f"[*] Removing container {container_id} ...")
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=30)

        # Start fresh
        print(f"[*] Starting fresh container from {image} ...")
        result = subprocess.run(
            ["docker", "run", "-d", "-p", "3000:3000", image],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"[!] Failed: {result.stderr}")
            return False

        new_id = result.stdout.strip()[:12]
        print(f"[+] New container: {new_id}")

        # Wait for startup
        print("[*] Waiting for Juice Shop to boot ", end="", flush=True)
        for _ in range(30):
            time.sleep(2)
            try:
                r = httpx.get(f"{base_url}/api/Challenges/", timeout=5)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            print(".", end="", flush=True)
        print()

        # IMMEDIATELY capture the blank continue code before any browser restores progress
        r = httpx.get(f"{base_url}/rest/continue-code", timeout=10)
        blank_code = r.json().get("continueCode", "")
        if blank_code:
            code_file = PROJECT_ROOT / "data" / "blank_continue_code.txt"
            code_file.parent.mkdir(parents=True, exist_ok=True)
            code_file.write_text(blank_code, encoding="utf-8")
            print(f"[+] Saved blank continue code to {code_file}")

        # Verify
        r = httpx.get(f"{base_url}/api/Challenges/", timeout=10)
        challenges = r.json().get("data", [])
        solved = sum(1 for c in challenges if c.get("solved"))
        print(f"[+] Server state: {solved}/{len(challenges)} solved")

        if solved > 0:
            print("[!] WARNING: Browser may have restored progress via cookie.")
            print("[!] This won't affect the agent (uses httpx, no cookies).")
            print("[!] To clear browser: delete 'continueCode' cookie or use incognito.")
        
        return True

    except FileNotFoundError:
        print("[!] 'docker' not found")
        return False


def apply_blank_code(base_url: str) -> bool:
    """Try to apply a previously saved blank continue code to reset without recreating container."""
    code_file = PROJECT_ROOT / "data" / "blank_continue_code.txt"
    if not code_file.exists():
        return False
    
    code = code_file.read_text(encoding="utf-8").strip()
    if not code:
        return False
    
    print(f"[*] Applying saved blank continue code ...")
    try:
        r = httpx.put(f"{base_url}/rest/continue-code/apply/{code}", timeout=10)
        if r.status_code == 200:
            # Verify
            r2 = httpx.get(f"{base_url}/api/Challenges/", timeout=10)
            challenges = r2.json().get("data", [])
            solved = sum(1 for c in challenges if c.get("solved"))
            print(f"[+] After applying blank code: {solved}/{len(challenges)} solved")
            return solved == 0
    except Exception as e:
        print(f"[!] Failed to apply blank code: {e}")
    
    return False


def reset_local_state() -> None:
    """Reset local session_state.json and memory.json."""
    session_file = PROJECT_ROOT / "session_state.json"
    if session_file.exists():
        old = json.loads(session_file.read_text(encoding="utf-8"))
        print(f"[*] Clearing session_state.json ({len(old.get('solved_keys', []))} solved)")

    session_file.write_text(
        json.dumps({"solved_keys": [], "records": []}, indent=2), encoding="utf-8",
    )
    print("[+] session_state.json reset")

    memory_file = PROJECT_ROOT / "data" / "memory.json"
    if memory_file.exists():
        old = json.loads(memory_file.read_text(encoding="utf-8"))
        print(f"[*] Clearing memory.json ({len(old.get('attack_results', {}))} results)")
    else:
        memory_file.parent.mkdir(parents=True, exist_ok=True)

    memory_file.write_text(
        json.dumps({"credentials": {}, "endpoints": {}, "attack_results": {}, "target_profile": {}}, indent=2),
        encoding="utf-8",
    )
    print("[+] memory.json reset")

    wm_dir = PROJECT_ROOT / "logs" / "working_memory"
    if wm_dir.exists():
        count = sum(1 for f in wm_dir.glob("*.json") if f.unlink() or True)
        if count:
            print(f"[+] Cleared {count} working memory snapshots")

    print("[+] Local state reset!")


def main():
    parser = argparse.ArgumentParser(description="Reset Juice Shop and local state")
    parser.add_argument("--target", "-t", default="http://localhost:3000")
    parser.add_argument("--local-only", "-l", action="store_true")
    parser.add_argument("--server-only", "-s", action="store_true")
    parser.add_argument("--fast", "-f", action="store_true",
                        help="Try blank continue code first (no container restart)")
    args = parser.parse_args()

    print("=" * 50)
    print("  Juice Solver 2 — Reset Tool")
    print("=" * 50)
    print()

    if not args.server_only:
        reset_local_state()
        print()

    if not args.local_only:
        if args.fast and apply_blank_code(args.target):
            print("[+] Fast reset succeeded!")
        else:
            if args.fast:
                print("[*] Fast reset failed, falling back to container rebuild...")
            if not reset_juice_shop(args.target):
                sys.exit(1)

    print()
    print("[✓] Done! Run 'python -m src.main' to start fresh.")


if __name__ == "__main__":
    main()

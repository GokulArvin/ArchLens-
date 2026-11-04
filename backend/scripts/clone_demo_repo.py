"""
Sprint 7: clone the real repository used for the Git-evidence demo (D31-D34)
into data/repositories/. Gitignored (like backend/models/) - a nested git
clone shouldn't be committed into this repo's own history; re-run this
script to reproduce it instead.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/clone_demo_repo.py
"""

import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/mblitherland/flask-microservice-demo.git"
REPO_ROOT = Path(__file__).resolve().parents[2]
CLONE_PATH = REPO_ROOT / "data" / "repositories" / "flask-microservice-demo"


def main():
    if CLONE_PATH.exists():
        print(f"{CLONE_PATH} already exists, skipping clone.")
        return
    CLONE_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", REPO_URL, str(CLONE_PATH)], check=True)
    print(f"Cloned {REPO_URL} -> {CLONE_PATH}")


if __name__ == "__main__":
    sys.exit(main())

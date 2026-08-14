"""Validate the GitHub Actions workflow YAML."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml

path = Path(__file__).resolve().parent.parent.parent / ".github/workflows/quality.yml"
with open(path, encoding="utf-8") as f:
    data = yaml.safe_load(f)

print("jobs:", list(data.get("jobs", {}).keys()))
for name, job in data["jobs"].items():
    print(f"  {name}: if={job.get('if', 'none')}")

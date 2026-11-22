import re
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
INVALID_ROLE = re.compile(r"\b(HR_MANAGER|PROJECT_MANAGER)\b")


def test_no_invalid_role_literals():
    hits = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if INVALID_ROLE.search(line):
                hits.append(f"{path.relative_to(APP_DIR.parent)}:{lineno}: {line.strip()}")
    assert not hits, "Invalid role literals found:\n" + "\n".join(hits)

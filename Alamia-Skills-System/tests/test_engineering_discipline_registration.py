"""Regression tests for engineering-discipline skill registration."""
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from reconciler import ProjectReconciler


def test_engineering_discipline_skill_is_registered():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "package.json").write_text('{"name":"engineering-discipline-test"}', encoding="utf-8")

        ProjectReconciler(root).reconcile()

        skills_json = root / ".agents" / "skills.json"
        assert skills_json.exists()
        config = json.loads(skills_json.read_text(encoding="utf-8"))
        paths = [entry.get("path", "").replace("\\", "/") for entry in config.get("entries", [])]
        assert any(path.endswith("/skills/engineering-discipline") for path in paths)


if __name__ == "__main__":
    test_engineering_discipline_skill_is_registered()
    print("[PASS] Engineering discipline skill registration verified!")

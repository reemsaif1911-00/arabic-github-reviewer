import json
import subprocess
import sys
from pathlib import Path

from reviewer.repair import repair_python


def test_repairs_python2_compatibility_and_safe_eval():
    source = "value = xrange(3)\ntext = raw_input('x')\nresult = eval(\"'ok'\")\n"
    modified, changes = repair_python(source)
    assert modified.startswith("import ast\n")
    assert "range(3)" in modified
    assert "input('x')" in modified
    assert "ast.literal_eval" in modified
    assert any(change.rule == "safe-literal-eval" for change in changes)


def test_exec_is_explained_not_silently_changed():
    modified, changes = repair_python("exec(code)\n")
    assert modified == "exec(code)\n"
    assert any(change.rule == "dynamic-exec-warning" for change in changes)


def test_repair_cli_outputs_original_modified_and_reasons(tmp_path: Path):
    (tmp_path / "sample.py").write_text("value = xrange(2)\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "reviewer/main.py", str(tmp_path), "--repair", "--format", "json"], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert data["repairs"][0]["original"]
    assert "range(2)" in data["repairs"][0]["modified"]
    assert data["repairs"][0]["changes"][0]["reason"]

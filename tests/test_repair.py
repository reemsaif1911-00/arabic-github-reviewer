import json
import ast
import subprocess
import sys
from pathlib import Path

from reviewer.repair import repair_python

CONTRACT = json.loads(Path(__file__).with_name("repair_contract.json").read_text(encoding="utf-8"))


def test_repairs_python2_compatibility_and_safe_eval():
    source = "value = xrange(3)\ntext = raw_input('x')\nresult = eval(\"'ok'\")\n"
    modified, changes = repair_python(source)
    assert modified.startswith("import ast\n")
    assert "range(3)" in modified
    assert "input('x')" in modified
    assert "ast.literal_eval" in modified
    ast.parse(modified)
    assert any(change.rule == "safe-literal-eval" for change in changes)


def test_exec_is_explained_not_silently_changed():
    modified, changes = repair_python("exec(code)\n")
    assert modified == "exec(code)\n"
    assert any(change.rule == "dynamic-exec-warning" for change in changes)


def test_strings_and_comments_are_never_rewritten():
    source = "# xrange raw_input eval\ntext = 'xrange raw_input eval'\nvalue = xrange(2)\n"
    modified, changes = repair_python(source)
    assert "# xrange raw_input eval" in modified
    assert "'xrange raw_input eval'" in modified
    assert "value = range(2)" in modified
    assert len([change for change in changes if change.before != change.after]) == 1


def test_dynamic_eval_is_not_rewritten():
    source = "user_value = input()\nresult = eval(user_value)\n"
    modified, changes = repair_python(source)
    assert modified == source
    assert any(change.rule == "dynamic-eval-warning" for change in changes)


def test_invalid_repair_is_rejected_and_original_is_preserved():
    source = "def broken(:\n    return xrange(2)\n"
    modified, changes = repair_python(source)
    assert modified == source
    assert any(change.rule in {"repair-rejected", "invalid-input"} for change in changes)


def test_shared_repair_contract_cases():
    for case in CONTRACT:
        modified, _ = repair_python(case["source"])
        for expected in case["must_include"]:
            assert expected in modified, case["name"]
        for preserved in case["must_preserve"]:
            assert preserved in modified, case["name"]


def test_repair_cli_outputs_original_modified_and_reasons(tmp_path: Path):
    (tmp_path / "sample.py").write_text("value = xrange(2)\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "reviewer/main.py", str(tmp_path), "--repair", "--format", "json"], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert data["repairs"][0]["original"]
    assert "range(2)" in data["repairs"][0]["modified"]
    assert data["repairs"][0]["changes"][0]["reason"]

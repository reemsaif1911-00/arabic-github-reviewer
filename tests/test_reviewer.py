from pathlib import Path

from reviewer.main import load_config, markdown, review


def test_detects_secret_and_long_line(tmp_path: Path):
    sample = tmp_path / "sample.py"
    key_name = "api" + "_key"
    sample.write_text(f"{key_name} = 'abcdefghijklmnop'\n" + "x = '" + "a" * 130 + "'\n", encoding="utf-8")
    findings = review(tmp_path)
    assert any(f.rule == "API key محتمل" and f.severity == "high" for f in findings)
    assert any(f.rule == "سطر طويل" for f in findings)


def test_markdown_when_clean(tmp_path: Path):
    (tmp_path / "clean.py").write_text("print('مرحبا')\n", encoding="utf-8")
    report = markdown(review(tmp_path))
    assert "لم يتم العثور على مشاكل" in report


def test_config_and_selected_paths(tmp_path: Path):
    (tmp_path / ".arabic-reviewer.toml").write_text("max_line_length = 20\n", encoding="utf-8")
    (tmp_path / "changed.py").write_text("print('" + "x" * 30 + "')\n", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("api_key = 'abcdefghijklmnop'\n", encoding="utf-8")
    config = load_config(tmp_path, None)
    findings = review(tmp_path, ["changed.py"], config)
    assert config["max_line_length"] == 20
    assert any(f.rule == "سطر طويل" for f in findings)
    assert not any(f.file == "ignored.py" for f in findings)


def test_empty_selected_paths_do_not_scan_the_repository(tmp_path: Path):
    (tmp_path / "secret.py").write_text("api_key = 'abcdefghijklmnop'\n", encoding="utf-8")
    assert review(tmp_path, []) == []


def test_python_syntax_error_is_reported(tmp_path: Path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    findings = review(tmp_path)
    assert any(f.rule == "خطأ صياغة Python" and f.severity == "high" for f in findings)

from pathlib import Path

from reviewer.main import markdown, review


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

"""مراجع كود عربي خفيف يعمل دون خدمة خارجية أو مفتاح API."""
from __future__ import annotations

import argparse
import json
import re
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    import tomli as tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .repair import repair_python
except ImportError:  # تشغيل الملف مباشرة عبر python reviewer/main.py
    from repair import repair_python


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    file: str
    line: int
    message: str
    suggestion: str


DEFAULTS = {
    "max_line_length": 120,
    "ignore": [".git", ".venv", "node_modules", "dist", "build", "__pycache__"],
    "fail_on": "high",
}

SECRET_PATTERNS = [
    ("API key محتمل", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-/+=]{12,}['\"]")),
    ("مفتاح خاص", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def load_config(root: Path, config_path: str | None) -> dict:
    path = Path(config_path) if config_path else root / ".arabic-reviewer.toml"
    config = dict(DEFAULTS)
    if path.exists():
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
        config.update({key: value for key, value in loaded.items() if key in config})
    return config


def review_file(path: Path, root: Path, config: dict) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    rel = str(path.relative_to(root))
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding("high", rule, rel, number, "يبدو أن هذا السطر يحتوي على سر أو مفتاح حساس.", "انقل السر إلى GitHub Secrets أو متغيرات البيئة ودوّر المفتاح المكشوف."))
        if len(line) > int(config["max_line_length"]):
            findings.append(Finding("low", "سطر طويل", rel, number, f"السطر أطول من {config['max_line_length']} حرفًا وقد يصعب قراءته.", "قسّم السطر إلى عدة أسطر أو استخدم دالة مساعدة."))
        if re.search(r"(?i)\b(eval|exec)\s*\(", line):
            findings.append(Finding("high", "تنفيذ ديناميكي", rel, number, "استخدام eval/exec قد يسمح بتنفيذ كود غير موثوق.", "استبدله بتحليل آمن للمدخلات أو خريطة وظائف معروفة."))
        if "TODO" in line or "FIXME" in line:
            findings.append(Finding("info", "مهمة مؤجلة", rel, number, "يوجد TODO/FIXME يحتاج إلى متابعة.", "حوّل المهمة إلى Issue أو عالجها قبل الدمج."))
    return findings


def review(root: Path, paths: list[str] | None = None, config: dict | None = None) -> list[Finding]:
    config = config or load_config(root, None)
    ignored = set(config.get("ignore", DEFAULTS["ignore"]))
    candidates = [root / item for item in paths] if paths else list(root.rglob("*"))
    findings: list[Finding] = []
    for path in candidates:
        if path.is_file() and not ignored.intersection(path.parts):
            findings.extend(review_file(path, root, config))
    return findings


def markdown(findings: list[Finding]) -> str:
    counts = {level: sum(f.severity == level for f in findings) for level in ("high", "medium", "low", "info")}
    lines = ["## مراجعة الكود بالعربية", "", f"**النتيجة:** {len(findings)} ملاحظة — مرتفع: {counts['high']}، متوسط: {counts['medium']}، منخفض: {counts['low']}، معلوماتي: {counts['info']}", ""]
    if not findings:
        lines.append("لم يتم العثور على مشاكل ضمن القواعد الحالية. هذا ليس بديلًا عن مراجعة بشرية أو فحص أمني شامل.")
        return "\n".join(lines) + "\n"
    lines += ["| الخطورة | القاعدة | الملف | السطر | الملاحظة | الاقتراح |", "|---|---|---|---:|---|---|"]
    for finding in findings:
        lines.append(f"| {finding.severity} | {finding.rule} | `{finding.file}` | {finding.line} | {finding.message} | {finding.suggestion} |")
    lines += ["", "> هذه نسخة أولية تعتمد على قواعد ثابتة، ولا تدّعي اكتشاف كل الأخطاء."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Arabic static code reviewer")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--config", default=None)
    parser.add_argument("--paths-file", default=None, help="ملف يحوي مسارًا واحدًا لكل ملف مطلوب فحصه")
    parser.add_argument("--repair", action="store_true", help="إظهار إصلاحات Python القابلة للتفسير")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    config = load_config(root, args.config)
    paths = None
    if args.paths_file:
        paths = [line.strip() for line in Path(args.paths_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    findings = review(root, paths, config)
    if args.repair:
        repaired = []
        candidates = [root / item for item in paths] if paths else list(root.rglob("*.py"))
        for path in candidates:
            if path.is_file():
                original = path.read_text(encoding="utf-8", errors="ignore")
                modified, changes = repair_python(original)
                if changes:
                    repaired.append({"file": str(path.relative_to(root)), "original": original, "modified": modified, "changes": [asdict(change) for change in changes]})
        print(json.dumps({"findings": [asdict(finding) for finding in findings], "repairs": repaired}, ensure_ascii=False, indent=2))
        raise SystemExit(1 if any(f.severity == "high" for f in findings) else 0)
    if args.format == "json":
        print(json.dumps([asdict(finding) for finding in findings], ensure_ascii=False, indent=2))
    else:
        print(markdown(findings))
    severity_order = {"info": 0, "low": 1, "medium": 2, "high": 3}
    raise SystemExit(1 if any(severity_order[f.severity] >= severity_order.get(str(config["fail_on"]), 3) for f in findings) else 0)


if __name__ == "__main__":
    main()

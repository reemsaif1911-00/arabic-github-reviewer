"""مراجع كود عربي خفيف يعمل دون خدمة خارجية أو مفتاح API."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    file: str
    line: int
    message: str
    suggestion: str


SECRET_PATTERNS = [
    ("API key محتمل", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-/+=]{12,}['\"]")),
    ("مفتاح خاص", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def review_file(path: Path, root: Path) -> list[Finding]:
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
        if len(line) > 120:
            findings.append(Finding("low", "سطر طويل", rel, number, "السطر أطول من 120 حرفًا وقد يصعب قراءته.", "قسّم السطر إلى عدة أسطر أو استخدم دالة مساعدة."))
        if re.search(r"(?i)\b(eval|exec)\s*\(", line):
            findings.append(Finding("high", "تنفيذ ديناميكي", rel, number, "استخدام eval/exec قد يسمح بتنفيذ كود غير موثوق.", "استبدله بتحليل آمن للمدخلات أو خريطة وظائف معروفة."))
        if "TODO" in line or "FIXME" in line:
            findings.append(Finding("info", "مهمة مؤجلة", rel, number, "يوجد TODO/FIXME يحتاج إلى متابعة.", "حوّل المهمة إلى Issue أو عالجها قبل الدمج."))
    return findings


def review(root: Path) -> list[Finding]:
    ignored = {".git", ".venv", "node_modules", "dist", "build", "__pycache__"}
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if path.is_file() and not ignored.intersection(path.parts):
            findings.extend(review_file(path, root))
    return findings


def markdown(findings: list[Finding]) -> str:
    counts = {level: sum(f.severity == level for f in findings) for level in ("high", "medium", "low", "info")}
    lines = ["## مراجعة الكود بالعربية", "", f"**النتيجة:** {len(findings)} ملاحظة — مرتفع: {counts['high']}، متوسط: {counts['medium']}، منخفض: {counts['low']}، معلوماتي: {counts['info']}", ""]
    if not findings:
        lines.append("لم يتم العثور على مشاكل ضمن القواعد الحالية. هذا ليس بديلًا عن مراجعة بشرية أو فحص أمني شامل.")
        return "\n".join(lines) + "\n"
    lines += ["| الخطورة | القاعدة | الملف | السطر | الملاحظة | الاقتراح |", "|---|---|---|---:|---|---|"]
    for f in findings:
        lines.append(f"| {f.severity} | {f.rule} | `{f.file}` | {f.line} | {f.message} | {f.suggestion} |")
    lines += ["", "> هذه نسخة أولية تعتمد على قواعد ثابتة، ولا تدّعي اكتشاف كل الأخطاء."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Arabic static code reviewer")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    findings = review(Path(args.root).resolve())
    if args.format == "json":
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        print(markdown(findings))
    raise SystemExit(1 if any(f.severity == "high" for f in findings) else 0)


if __name__ == "__main__":
    main()

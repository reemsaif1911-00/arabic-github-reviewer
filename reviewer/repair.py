"""إصلاحات Python محافظة وقابلة للتفسير، دون نموذج خارجي أو مفتاح API."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Change:
    rule: str
    line: int
    before: str
    after: str
    reason: str


def repair_python(source: str) -> tuple[str, list[Change]]:
    """Apply safe, deterministic compatibility repairs and return a change log."""
    lines = source.splitlines(keepends=True)
    changes: list[Change] = []
    output: list[str] = []
    needs_ast = False

    for number, original in enumerate(lines, start=1):
        updated = original
        newline = "\n" if original.endswith("\n") else ""
        content = original[:-1] if newline else original

        replacements = [
            (r"\bxrange\b", "range", "python3-xrange", "استبدال xrange بـ range المتوافق مع Python 3."),
            (r"\braw_input\s*\(", "input(", "python3-raw-input", "استبدال raw_input بـ input المتوافق مع Python 3."),
            (r"\bunicode\s*\(", "str(", "python3-unicode", "استبدال unicode بـ str المتوافق مع Python 3."),
        ]
        for pattern, replacement, rule, reason in replacements:
            candidate = re.sub(pattern, replacement, content)
            if candidate != content:
                changes.append(Change(rule, number, content, candidate, reason))
                content = candidate

        candidate = re.sub(r"except\s+([^:]+),\s*([A-Za-z_]\w*)\s*:", r"except \1 as \2:", content)
        if candidate != content:
            changes.append(Change("python3-except-as", number, content, candidate, "تحديث صيغة التقاط الاستثناء إلى صيغة Python 3."))
            content = candidate

        if re.search(r"\beval\s*\(", content):
            candidate = re.sub(r"\beval\s*\(", "ast.literal_eval(", content)
            if candidate != content:
                changes.append(Change("safe-literal-eval", number, content, candidate, "استبدال eval بـ ast.literal_eval لتجنب تنفيذ كود غير موثوق؛ راجعي الحالات غير الحرفية يدويًا."))
                content = candidate
                needs_ast = True
        if re.search(r"\bexec\s*\(", content):
            changes.append(Change("dynamic-exec-warning", number, content, content, "لم يتم تعديل exec تلقائيًا لأنه يحتاج إعادة تصميم؛ استخدمي خريطة وظائف أو واجهة آمنة."))

        output.append(content + newline)

    if needs_ast and not any(re.match(r"\s*(import\s+ast\b|from\s+ast\s+import\s+)", line) for line in output):
        output.insert(0, "import ast\n")
        changes.insert(0, Change("add-ast-import", 1, "", "import ast", "إضافة الاستيراد المطلوب لـ ast.literal_eval."))

    return "".join(output), changes


def changes_as_dict(changes: list[Change]) -> list[dict]:
    return [asdict(change) for change in changes]

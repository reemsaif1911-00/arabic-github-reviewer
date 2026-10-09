"""إصلاحات Python محافظة وقابلة للتفسير، دون خدمة خارجية أو مفتاح API."""
from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Change:
    rule: str
    line: int
    before: str
    after: str
    reason: str


def _byte_col(line: str, char_col: int) -> int:
    return len(line[:char_col].encode("utf-8"))


def _safe_eval_positions(source: str) -> set[tuple[int, int]]:
    """Return token positions for eval calls whose argument is a literal."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    lines = source.splitlines()
    positions: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "eval":
            continue
        if len(node.args) != 1 or node.keywords:
            continue
        try:
            ast.literal_eval(node.args[0])
        except (ValueError, TypeError, SyntaxError):
            continue
        line = lines[node.func.lineno - 1]
        positions.add((node.func.lineno, _byte_col(line, node.func.col_offset)))
    return positions


def _has_ast_import(tokens: list[tokenize.TokenInfo]) -> bool:
    for index, token in enumerate(tokens):
        if token.type == tokenize.NAME and token.string == "import":
            following = tokens[index + 1 : index + 4]
            if any(item.type == tokenize.NAME and item.string == "ast" for item in following):
                return True
    return False


def _insertion_index(lines: list[str]) -> int:
    index = 1 if lines and lines[0].startswith("#!") else 0
    encoding = re.compile(r"coding[:=]\s*[-\w.]+")
    while index < min(2, len(lines)) and encoding.search(lines[index]):
        index += 1
    return index


def repair_python(source: str) -> tuple[str, list[Change]]:
    """Apply only token/AST-aware repairs and reject a result that is not valid Python."""
    lines = source.splitlines(keepends=True)
    original_lines = [line[:-1] if line.endswith("\n") else line for line in lines]
    safe_eval = _safe_eval_positions(source)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        tokens = []

    replacements: list[tuple[int, int, int, int, str, str, str]] = []
    significant: list[tokenize.TokenInfo] = []
    previous_by_position: dict[tuple[int, int], tokenize.TokenInfo | None] = {}
    for token in tokens:
        if token.type not in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
            previous_by_position[token.start] = significant[-1] if significant else None
            significant.append(token)

    for token in tokens:
        if token.type != tokenize.NAME or token.string not in {"xrange", "raw_input", "unicode", "eval", "exec"}:
            continue
        previous = previous_by_position.get(token.start)
        if previous and previous.string == ".":
            continue
        line_no, char_start = token.start
        line = source.splitlines()[line_no - 1] if source.splitlines() else ""
        byte_start = _byte_col(line, char_start)
        if token.string == "eval":
            if (line_no, byte_start) in safe_eval:
                replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, "ast.literal_eval", "استبدال eval بـ ast.literal_eval للحالات الحرفية فقط لتجنب تنفيذ كود غير موثوق."))
            else:
                replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, token.string, "لم يتم تعديل eval تلقائيًا لأن مدخله ليس literal آمنًا؛ راجعيه يدويًا."))
        elif token.string == "exec":
            replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, token.string, "لم يتم تعديل exec تلقائيًا؛ يحتاج إعادة تصميم آمنة."))
        elif token.string == "xrange":
            replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, "range", "استبدال xrange بـ range المتوافق مع Python 3."))
        elif token.string == "raw_input":
            replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, "input", "استبدال raw_input بـ input المتوافق مع Python 3."))
        elif token.string == "unicode":
            replacements.append((line_no, char_start, token.end[1], token.end[1], token.string, "str", "استبدال unicode بـ str المتوافق مع Python 3."))

    changes: list[Change] = []
    changed_lines: dict[int, str] = {index + 1: value for index, value in enumerate(original_lines)}
    actual_replacement = False
    for line_no, start, end, _unused, before, after, reason in sorted(replacements, key=lambda item: (item[0], item[1]), reverse=True):
        current = changed_lines[line_no]
        updated = current[:start] + after + current[end:]
        if before != after:
            changes.append(Change("safe-literal-eval" if before == "eval" else f"python3-{before}", line_no, current, updated, reason))
            actual_replacement = True
        else:
            changes.append(Change("dynamic-exec-warning" if before == "exec" else "dynamic-eval-warning", line_no, current, current, reason))
        changed_lines[line_no] = updated

    modified_lines = [changed_lines[index + 1] for index in range(len(original_lines))]
    modified = "\n".join(modified_lines)
    if source.endswith("\n"):
        modified += "\n"

    if actual_replacement and any(change.rule == "safe-literal-eval" for change in changes):
        try:
            parsed = ast.parse(source)
            has_import = _has_ast_import(list(tokenize.generate_tokens(io.StringIO(source).readline)))
        except (SyntaxError, tokenize.TokenError, IndentationError):
            has_import = False
        if not has_import:
            index = _insertion_index(modified_lines)
            modified_lines.insert(index, "import ast")
            modified = "\n".join(modified_lines) + ("\n" if source.endswith("\n") else "")
            changes.append(Change("add-ast-import", index + 1, "", "import ast", "إضافة الاستيراد المطلوب لـ ast.literal_eval."))

    try:
        ast.parse(modified)
    except SyntaxError as error:
        if changes:
            return source, [Change("repair-rejected", error.lineno or 1, modified, source, "رُفضت التعديلات لأن الناتج لم يمر بفحص صياغة Python؛ لم يتم تغيير الكود.")]
        return source, [Change("invalid-input", error.lineno or 1, source, source, "لم تُطبّق إصلاحات لأن الكود الأصلي لا يمر بفحص صياغة Python.")]
    return modified, list(reversed(changes))


def changes_as_dict(changes: list[Change]) -> list[dict]:
    return [asdict(change) for change in changes]

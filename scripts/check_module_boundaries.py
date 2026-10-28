"""EKO TIZIM modul chegarasi tekshiruvi (TZ §2.1, `backend/app/modules/__init__.py`).

Qoida: `app.modules.<m>` ga uning tashqarisidan faqat `app.modules.<m>.service` orqali
murojaat qilinadi. Modul o'z ichida xohlagan qismini import qiladi.

    python scripts/check_module_boundaries.py      # buzilish bo'lsa exit 1
"""

import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "backend" / "app"
PREFIX = "app.modules."


def owner_of(path: Path) -> str | None:
    parts = path.relative_to(APP).parts
    return parts[1] if len(parts) > 2 and parts[0] == "modules" else None


def module_name(path: Path) -> str:
    rel = path.relative_to(APP.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def resolve(node: ast.ImportFrom, current: str, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    base = current.split(".")
    if not is_package:
        base = base[:-1]
    base = base[: len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def targets(tree: ast.Module, current: str, is_package: bool) -> list[tuple[int, str]]:
    """(qator, to'liq nom) — import qilingan har bir narsa nuqtali yo'l bilan."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = resolve(node, current, is_package)
            out += [(node.lineno, f"{base}.{a.name}") for a in node.names]
    return out


def violation(owner: str | None, name: str) -> bool:
    if not name.startswith(PREFIX):
        return False
    rest = name[len(PREFIX) :].split(".")
    target = rest[0]
    if target == owner:
        return False
    # `app.modules.X.service` yoki undan ichkariroq (`...service.reserve`) — ruxsat
    return len(rest) < 2 or rest[1] != "service"


def main() -> int:
    problems: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        owner = owner_of(path)
        for line, name in targets(tree, module_name(path), path.name == "__init__.py"):
            if violation(owner, name):
                problems.append(f"{path.relative_to(APP.parent)}:{line}: {name} - faqat .service orqali")
    for p in problems:
        print(p)
    print(f"Modul chegarasi: {len(problems)} ta buzilish")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

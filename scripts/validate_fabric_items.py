"""Validate the Fabric item folders in the Git folder without calling any API."""

import json
import logging
import py_compile
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_ITEM_TYPES = {
    "Lakehouse",
    "Notebook",
    "DataPipeline",
    "Eventstream",
    "Eventhouse",
    "KQLDatabase",
    "KQLDashboard",
    "SemanticModel",
    "Report",
}

JSON_SUFFIXES = {".json", ".platform"}


def find_item_dirs(root: Path) -> list[Path]:
    """Return directories named `<name>.<ItemType>` with a known item type."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_dir() and path.suffix.removeprefix(".") in KNOWN_ITEM_TYPES
    )


def check_json_files(root: Path) -> list[str]:
    """Return one error per `.json` or `.platform` file that does not parse."""
    errors = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in JSON_SUFFIXES:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: invalid JSON ({exc})")
    return errors


def check_python_sources(root: Path) -> list[str]:
    """Return one error per `notebook-content.py` file that does not compile."""
    errors = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for path in sorted(root.rglob("notebook-content.py")):
            try:
                py_compile.compile(
                    str(path), cfile=str(Path(tmp_dir) / "out.pyc"), doraise=True
                )
            except py_compile.PyCompileError as exc:
                errors.append(f"{path}: does not compile ({exc.msg.strip()})")
    return errors


def check_platform_file(item_dir: Path) -> list[str]:
    """Return errors for a missing or inconsistent `.platform` file of an item."""
    platform_path = item_dir / ".platform"
    if not platform_path.is_file():
        return [f"{item_dir}: missing .platform file"]
    try:
        metadata = json.loads(platform_path.read_text(encoding="utf-8")).get("metadata", {})
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []  # already reported by check_json_files
    expected_type = item_dir.suffix.removeprefix(".")
    if metadata.get("type") != expected_type:
        return [
            f"{platform_path}: metadata.type is {metadata.get('type')!r}, "
            f"expected {expected_type!r}"
        ]
    return []


def validate(root: Path) -> list[str]:
    """Run every check on the Git folder and return all errors."""
    if not root.is_dir():
        return [f"{root}: folder does not exist"]
    errors = check_json_files(root) + check_python_sources(root)
    for item_dir in find_item_dirs(root):
        errors.extend(check_platform_file(item_dir))
    return errors


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = Path(argv[1]) if len(argv) > 1 else Path("fabric")
    errors = validate(root)
    for error in errors:
        logger.error("[FAIL] %s", error)
    if errors:
        return 1
    logger.info("[OK] %d item folder(s) validated in %s", len(find_item_dirs(root)), root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

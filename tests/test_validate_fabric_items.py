import json
from pathlib import Path

import validate_fabric_items as vfi


def make_item(root: Path, folder: str, item_type: str, content: str | None = None) -> Path:
    item_dir = root / folder
    item_dir.mkdir(parents=True)
    platform = {"metadata": {"type": item_type, "displayName": folder.split(".")[0]}}
    (item_dir / ".platform").write_text(json.dumps(platform), encoding="utf-8")
    if content is not None:
        (item_dir / "notebook-content.py").write_text(content, encoding="utf-8")
    return item_dir


def test_empty_folder_is_valid(tmp_path):
    assert vfi.validate(tmp_path) == []


def test_missing_folder_is_reported(tmp_path):
    errors = vfi.validate(tmp_path / "missing")
    assert len(errors) == 1
    assert "does not exist" in errors[0]


def test_valid_notebook_item_passes(tmp_path):
    make_item(tmp_path, "nb_ingest.Notebook", "Notebook", content="print('ok')\n")
    assert vfi.validate(tmp_path) == []


def test_invalid_json_is_reported(tmp_path):
    item_dir = make_item(tmp_path, "pl_daily.DataPipeline", "DataPipeline")
    (item_dir / "pipeline-content.json").write_text("{not json", encoding="utf-8")
    errors = vfi.validate(tmp_path)
    assert len(errors) == 1
    assert "invalid JSON" in errors[0]


def test_type_mismatch_is_reported(tmp_path):
    make_item(tmp_path, "nb_ingest.Notebook", "Lakehouse")
    errors = vfi.validate(tmp_path)
    assert len(errors) == 1
    assert "expected 'Notebook'" in errors[0]


def test_missing_platform_file_is_reported(tmp_path):
    (tmp_path / "lh_bronze.Lakehouse").mkdir()
    errors = vfi.validate(tmp_path)
    assert len(errors) == 1
    assert "missing .platform" in errors[0]


def test_notebook_that_does_not_compile_is_reported(tmp_path):
    make_item(tmp_path, "nb_ingest.Notebook", "Notebook", content="def broken(:\n")
    errors = vfi.validate(tmp_path)
    assert len(errors) == 1
    assert "does not compile" in errors[0]


def test_unknown_item_type_folder_is_ignored(tmp_path):
    (tmp_path / "notes.Unknown").mkdir()
    assert vfi.find_item_dirs(tmp_path) == []

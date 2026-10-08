import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import upload_dat_pack as udp

SCRIPT = Path(udp.__file__)


@pytest.fixture
def azure(monkeypatch):
    import azure.storage.filedatalake as fdl
    mock_cls = MagicMock(name="DataLakeServiceClient")
    monkeypatch.setattr(fdl, "DataLakeServiceClient", mock_cls)
    return mock_cls


def _fs(azure):
    return azure.from_connection_string.return_value.get_file_system_client.return_value


@pytest.mark.parametrize("name,ok", [
    ("POSITION_20250106_101500.dat", True),
    ("CASH_20250106_101500_FULL.dat", True),
    ("position_20250106_101500.dat", False),
    ("POSITION_2025016_101500.dat", False),
    ("POSITION_20250106_10150.dat", False),
    ("POSITION_20250106_101500.csv", False),
])
def test_filename_pattern(name, ok):
    assert bool(udp.FILENAME_PATTERN.match(name)) is ok


def test_filename_pattern_groups():
    assert udp.FILENAME_PATTERN.match("CASH_20250106_101500_FULL.dat").groups() == (
        "CASH", "20250106", "101500", "FULL")


def test_upload_dat_pack_routes_files(tmp_path, monkeypatch, capsys):
    for name in ["POSITION_20250106_101500.dat", "CASH_20250106_101500_FULL.dat", "MANIFEST.dat",
                 "README.txt", "pack.zip", "notes.dat", "lower_20250106_101500.dat"]:
        (tmp_path / name).write_text("x")
    calls = []
    monkeypatch.setattr(udp, "_upload_single_file", lambda d, f, r: calls.append((f, r)))

    udp.upload_dat_pack(str(tmp_path))

    assert calls == [  # sorted filename order
        ("CASH_20250106_101500_FULL.dat", "external_dat/cash/business_date=2025-01-06"),
        ("MANIFEST.dat", "external_dat/_manifest"),
        ("POSITION_20250106_101500.dat", "external_dat/position/business_date=2025-01-06"),
    ]
    out = capsys.readouterr().out
    assert "Skipping unrecognized filename: notes.dat" in out
    assert "Skipping unrecognized filename: lower_20250106_101500.dat" in out
    assert "README" not in out and "pack.zip" not in out
    assert "Done. Uploaded 3 files, skipped 2." in out


def test_upload_dat_pack_empty_dir(tmp_path, capsys):
    udp.upload_dat_pack(str(tmp_path))
    assert "Uploaded 0 files, skipped 0." in capsys.readouterr().out


def test_single_file_skips_without_connection_string(azure, tmp_path, capsys):
    udp._upload_single_file(str(tmp_path), "A.dat", "remote")
    azure.from_connection_string.assert_not_called()
    assert "skipping A.dat" in capsys.readouterr().out


def test_single_file_uploads_bytes_with_default_container(azure, tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "conn")
    (tmp_path / "A.dat").write_bytes(b"payload")

    udp._upload_single_file(str(tmp_path), "A.dat", "external_dat/a/business_date=2025-01-06")

    azure.from_connection_string.assert_called_once_with("conn")
    azure.from_connection_string.return_value.get_file_system_client.assert_called_once_with("ingested")
    fs = _fs(azure)
    fs.create_file_system.assert_called_once()
    fs.get_file_client.assert_called_once_with("external_dat/a/business_date=2025-01-06/A.dat")
    fs.get_file_client.return_value.upload_data.assert_called_once_with(b"payload", overwrite=True)


def test_single_file_honours_container_env_and_swallows_create_error(azure, tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "conn")
    monkeypatch.setenv("ADLS_CONTAINER", "other")
    _fs(azure).create_file_system.side_effect = RuntimeError("exists")
    (tmp_path / "A.dat").write_bytes(b"1")

    udp._upload_single_file(str(tmp_path), "A.dat", "r")

    azure.from_connection_string.return_value.get_file_system_client.assert_called_once_with("other")
    _fs(azure).get_file_client.return_value.upload_data.assert_called_once()


def test_cli_runs_with_source(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["upload_dat_pack.py", "--source", str(tmp_path)])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    assert "Uploaded 0 files, skipped 0." in capsys.readouterr().out


def test_cli_requires_source(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["upload_dat_pack.py"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exc.value.code == 2

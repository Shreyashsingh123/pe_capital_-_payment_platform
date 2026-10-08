import importlib
from unittest.mock import MagicMock

import pytest

import src.common.adls_upload as adls


@pytest.fixture
def client(monkeypatch):
    mock_cls = MagicMock(name="DataLakeServiceClient")
    monkeypatch.setattr(adls, "DataLakeServiceClient", mock_cls)
    return mock_cls


def _fs(client):
    return client.from_connection_string.return_value.get_file_system_client.return_value


def test_skips_without_connection_string(client, tmp_path, capsys):
    adls.upload_folder(str(tmp_path), "t/ingestion_date=2025-01-06")
    client.from_connection_string.assert_not_called()
    assert "skipping" in capsys.readouterr().out


def test_uploads_each_file_and_skips_subdirs(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(adls, "CONTAINER_NAME", "box")
    (tmp_path / "a.csv").write_bytes(b"aaa")
    (tmp_path / "b.csv").write_bytes(b"bb")
    (tmp_path / "sub").mkdir()

    adls.upload_folder(str(tmp_path), "rel/path")

    client.from_connection_string.assert_called_once_with("UseDevelopmentStorage=true")
    svc = client.from_connection_string.return_value
    svc.get_file_system_client.assert_called_once_with("box")
    fs = _fs(client)
    fs.create_file_system.assert_called_once()
    called = {c.args[0] for c in fs.get_file_client.call_args_list}
    assert called == {"rel/path/a.csv", "rel/path/b.csv"}
    uploads = {c.args[0] for c in fs.get_file_client.return_value.upload_data.call_args_list}
    assert uploads == {b"aaa", b"bb"}
    for c in fs.get_file_client.return_value.upload_data.call_args_list:
        assert c.kwargs == {"overwrite": True}


def test_create_file_system_error_is_swallowed(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "x")
    _fs(client).create_file_system.side_effect = RuntimeError("exists")
    (tmp_path / "a.csv").write_bytes(b"1")
    adls.upload_folder(str(tmp_path), "r")
    _fs(client).get_file_client.assert_called_once_with("r/a.csv")


def test_empty_folder_uploads_nothing(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "x")
    adls.upload_folder(str(tmp_path), "r")
    _fs(client).get_file_client.assert_not_called()


def test_container_name_from_env(monkeypatch):
    monkeypatch.setenv("ADLS_CONTAINER", "custom")
    try:
        importlib.reload(adls)
        assert adls.CONTAINER_NAME == "custom"
    finally:
        monkeypatch.delenv("ADLS_CONTAINER")
        importlib.reload(adls)
    assert adls.CONTAINER_NAME == "ingested"

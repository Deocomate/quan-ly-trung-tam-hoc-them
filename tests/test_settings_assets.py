from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.bootstrap as bootstrap_module
import app.routers.settings as settings_module
from main import app


@pytest.fixture()
def isolated_assets(tmp_path, monkeypatch):
    fake_base = tmp_path / "app"
    assets_dir = fake_base / "static" / "assets"
    monkeypatch.setattr(bootstrap_module, "BASE_DIR", fake_base)
    monkeypatch.setattr(settings_module, "ASSETS_DIR", assets_dir)
    return assets_dir


def _image_bytes(fmt: str, color: tuple[int, ...]) -> bytes:
    buffer = BytesIO()
    mode = "RGBA" if len(color) == 4 else "RGB"
    Image.new(mode, (8, 8), color).save(buffer, format=fmt)
    return buffer.getvalue()


def _login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123*#"})
    assert response.status_code == 200


def test_default_assets_are_created_when_volume_is_empty(isolated_assets):
    bootstrap_module.ensure_default_assets()

    for filename in ("logo.png", "qr.png"):
        path = isolated_assets / filename
        assert path.exists()
        with Image.open(path) as image:
            assert image.format == "PNG"


def test_logo_and_qr_upload_accept_common_image_formats(isolated_assets):
    with TestClient(app) as client:
        _login(client)

        logo = client.post(
            "/api/settings/logo",
            files={"file": ("logo.jpg", _image_bytes("JPEG", (16, 96, 160)), "image/jpeg")},
        )
        assert logo.status_code == 200
        assert logo.json()["url"].startswith("/static/assets/logo.png?v=")

        qr = client.post(
            "/api/settings/qr",
            files={"file": ("qr.gif", _image_bytes("GIF", (0, 0, 0)), "image/gif")},
        )
        assert qr.status_code == 200
        assert qr.json()["url"].startswith("/static/assets/qr.png?v=")

    for filename in ("logo.png", "qr.png"):
        with Image.open(isolated_assets / filename) as image:
            assert image.format == "PNG"


def test_upload_rejects_non_image_file(isolated_assets):
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/api/settings/logo",
            files={"file": ("logo.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 400

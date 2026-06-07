from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.bootstrap import seed_defaults
from app.main import app

def setup_module() -> None:
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)

def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200

def test_auto_backup_scheduler_flow() -> None:
    with TestClient(app) as client:
        login(client)

        # 1. Ban đầu cấu hình backup_schedule_day trống -> due: False
        client.put("/api/settings", json=[{"key": "backup_schedule_day", "value": ""}, {"key": "last_auto_backup_date", "value": ""}])
        
        resp = client.get("/api/data/check-auto-backup").json()
        assert resp["due"] is False

        # 2. Mock ngày hôm nay là 2026-06-07. Cài lịch mùng 7 hàng tháng.
        # backup_schedule_day = 7, t_now = 2026-06-07.
        # Target backup sẽ là 2026-06-07.
        # last_auto_backup_date là trống -> due: True, backup_date: 2026-06-07.
        with patch("app.timezone.today_vietnam", return_value=date(2026, 6, 7)):
            client.put("/api/settings", json=[{"key": "backup_schedule_day", "value": "7"}, {"key": "last_auto_backup_date", "value": ""}])
            
            resp = client.get("/api/data/check-auto-backup").json()
            assert resp["due"] is True
            assert resp["backup_date"] == "2026-06-07"

            # Xác nhận tải về thành công
            confirm_resp = client.post("/api/data/confirm-auto-backup", json={"backup_date": "2026-06-07"})
            assert confirm_resp.status_code == 200
            
            # Kiểm tra lại -> do đã tải nên due: False
            resp_after = client.get("/api/data/check-auto-backup").json()
            assert resp_after["due"] is False

        # 3. Mock ngày hôm nay là 2026-06-07. Cài lịch mùng 15 hàng tháng (Chưa tới ngày 15).
        # backup_schedule_day = 15, t_now = 2026-06-07.
        # Target backup sẽ là ngày 15 của tháng trước (2026-05-15).
        # Nếu chưa từng tải -> due: True, backup_date: 2026-05-15.
        with patch("app.timezone.today_vietnam", return_value=date(2026, 6, 7)):
            client.put("/api/settings", json=[{"key": "backup_schedule_day", "value": "15"}, {"key": "last_auto_backup_date", "value": ""}])
            
            resp = client.get("/api/data/check-auto-backup").json()
            assert resp["due"] is True
            assert resp["backup_date"] == "2026-05-15"

            # Nếu đã tải ngày 2026-05-15 trước đó -> due: False
            client.put("/api/settings", json=[{"key": "last_auto_backup_date", "value": "2026-05-15"}])
            resp_loaded = client.get("/api/data/check-auto-backup").json()
            assert resp_loaded["due"] is False

            # Nếu ngày tải gần nhất cũ hơn (ví dụ 2026-04-15) -> due: True
            client.put("/api/settings", json=[{"key": "last_auto_backup_date", "value": "2026-04-15"}])
            resp_old = client.get("/api/data/check-auto-backup").json()
            assert resp_old["due"] is True
            assert resp_old["backup_date"] == "2026-05-15"

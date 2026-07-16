# Deployment & Installation Guide

This document provides step-by-step instructions on setting up, running, and deploying the Hoang Classroom Management System.

---

## 1. Local Environment Setup

### Prerequisites
* **Python**: Python 3.11 or newer.
* **System Libraries (Optional but recommended)**:
  - `WeasyPrint` is used for high-fidelity PDF rendering. Under the hood, WeasyPrint depends on GTK3/Pango libraries.
  - On Ubuntu/Debian: `sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`.
  - On Windows: You can download the GTK+ installer or let the application fall back to the built-in `ReportLab` engine (which has no extra system dependencies).

### Installation Steps
1. **Extract/Clone the codebase** and navigate into the root directory:
   ```bash
   cd hoang-quanlylophoc
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```
3. **Activate the virtual environment**:
   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - **Linux/macOS**:
     ```bash
     source venv/bin/activate
     ```
4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Run the application**:
   ```bash
   python main.py
   ```
   *Note: The script searches for an available port starting from `8000`, binds Uvicorn, and automatically opens the user's default browser.*

---

## 2. Docker Deployment (Recommended for Production/VPS)

The application includes a `Dockerfile` and `docker-compose.yml` to support containerized deployments. Docker handles the installation of GTK3/Pango dependencies automatically, ensuring WeasyPrint is fully operational.

### Starting the Container
1. Ensure Docker and Docker Compose are installed on your host system.
2. In the project root folder, execute:
   ```bash
   docker compose up -d
   ```
3. The server starts running on port `8000` (configurable in `docker-compose.yml`). Access it via: `http://localhost:8000`.

### Data Persistence
The `docker-compose.yml` file maps two volumes to preserve crucial data:
* `ql_db_data`: Maps the database folder `/app/database` containing the SQLite file.
* `ql_assets_data`: Maps the static uploaded folder `/app/static/assets` containing custom logos and QR code images.

---

## 3. Database Seeding & Mock Data

When launched for the first time, the application automatically builds schemas and sets up the default administration credentials:
* **Username**: `admin`
* **Password**: `Admin@123*#`

To seed the database with mock student records, teachers, and attendance tables for month 06/2026:
```bash
# Run in local virtual environment
python -m app.seeder
```
*Note: The seeder script safely drops and recreates mock tables, which does not affect actual custom configurations.*

---

## 4. Backups, Restores, & Migrations

### Manual Backups
All data is stored inside a single file: `database/quanlylophoc.sqlite3`.
* You can back up the system by copying this database file.
* Alternatively, navigate to **Quản lý dữ liệu** in the sidebar admin dashboard and click **Xuất bản sao SQL** to download a complete SQL text dump.

### Data Restoration
If you need to restore or migrate data to a new server:
1. Navigate to the **Quản lý dữ liệu** dashboard.
2. Under the **Phục hồi cơ sở dữ liệu** card, select your exported SQL dump.
3. Click upload. The system parses the SQL dump, clears current active tables, and restores the database state.

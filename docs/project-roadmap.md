# Project Roadmap

This document outlines the development milestones, completed features, and future targets for the Hoang Classroom Management System.

---

## 1. Completed Milestones (Phase 1)

* **Core Directory & Management**:
  - Full CRUD operations for Students, Classes, and Teachers.
  - Multi-class enrollment tracking with customization (custom fees, exemptions).
* **Attendance Engine**:
  - Class-based grid check-in for students and teachers with multiple status logs (`P` / `V` / `M`).
* **Financial Calculations**:
  - Automatic tuition fees based on attendance totals.
  - Dynamic VietQR quick link generation on bills.
  - Multiple teacher compensation schemas (flat per-session fee vs class revenue percentage coefficient).
* **Reports & Exports**:
  - High-fidelity PDF rendering with `WeasyPrint` and fallback `ReportLab` engine for billing invoice statements and teacher payroll slips.
  - Custom `.xlsx` template exports using `openpyxl` for students list, attendance templates, and payroll sheets.
* **System Settings & Data Resiliency**:
  - Customizable invoice templates (intro text, deadline, hotline, address, footers).
  - Configurable student code templates via JSON.
  - Complete backup utility (database download, SQL script export, manual SQL restore, and periodic automated backup triggers).
* **Access & Security**:
  - Session authorization using HTTPOnly JWT cookies, admin account creation, and password rotation guards.

---

## 2. Near-Term Roadmap (Phase 2)

* **Automated Payment Checking (Bank Integration)**:
  - Integrate Vietnamese banking transaction check APIs (such as SePay or Casso) to listen for transfer webhook events.
  - Parse inbound transfer details to identify payment descriptions matching `HP <StudentCode> <Month><Year>`.
  - Automatically mark corresponding `tuition_records` as "paid" without requiring admin manual reconciliation.
* **Notification System**:
  - Implement SMS or Zalo API integrations to notify parents automatically once monthly tuition invoices are finalized.
* **Attendance Mobile Interface**:
  - Optimize the student attendance page for mobile view to streamline teacher operations inside the classroom.

---

## 3. Long-Term Roadmap (Phase 3)

* **Parent Portal**:
  - Build a lightweight client interface where parents can log in securely using the student's code and parent phone number.
  - Display attendance history, class schedules, and billing history.
  - Integrate online payment gateways (VNPay, MoMo, etc.) alongside bank transfers.
* **Multi-Branch Tenant Support**:
  - Add multi-tenant capability to manage multiple tutoring center branches under a single centralized deployment.
* **Advanced Financial Analytics**:
  - Integrate predictive analytics to forecast future center revenue based on historical attendance curves and seasonal enrollment trends.
  - Build detailed teacher contribution charts (revenue generated vs payroll paid).

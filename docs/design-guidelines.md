# Front-End Design & UI Guidelines

This document outlines the UI patterns, frontend framework decisions, and design system elements of the Hoang Classroom Management System.

---

## 1. UI Foundation & Styling

* **Base Framework**: Tailwind CSS is imported via CDN in the base template for rapid, modern styling.
* **Custom Overrides**: Custom CSS rules are managed in **[app.css](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/static/css/app.css)**. It configures:
  - Sidebar drawer navigation layout.
  - Custom scrollbars.
  - Form field visual spacing.
  - Print layout overrides (`@media print` rules) to clean up invoice PDF/payslip styling.

---

## 2. Layout Structure & Jinja2 Templates

* **Master Base Template**: **[base.html](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/templates/base.html)** is the parent template.
  - **Sidebar Drawer**: Collapsible menu holding system page routes.
  - **Active State Highlights**: Route highlight indicator matching the `active` variable passed from Python FastAPI handlers.
  - **Script/Style Anchors**: Provides `{% block styles %}` and `{% block scripts %}` to inject page-specific resources.
* **Component Blocks**: Inner templates (e.g. `students.html`, `attendance.html`) inherit from `base.html` using the standard `{% extends "base.html" %}` instruction.

---

## 3. UI Colors & Interaction States

We use consistent visual color cues for data lists:

| Semantic State | Tailwind Color Code | Hex Value | Application |
| :--- | :---: | :---: | :--- |
| **Active / Present** | `bg-green-100 text-green-800` | `#D1FAE5` / `#065F46` | Attendances status "P", paid bills |
| **Late / Pending** | `bg-yellow-100 text-yellow-800` | `#FEF3C7` / `#92400E` | Attendances status "M", partially paid bills |
| **Absent / Unpaid** | `bg-red-100 text-red-800` | `#FEE2E2` / `#991B1B` | Attendances status "V", unpaid bills |
| **Exempt / Inactive** | `bg-gray-100 text-gray-800` | `#F3F4F6` / `#1F2937` | Exempt tuition status |

---

## 4. Front-End Libraries & Usage

* **jQuery**: Used for DOM selections, event tracking, and AJAX network requests.
* **DataTables**:
  - Automatically initializes on lists (e.g., student roster grids).
  - Setup uses search filters, paginator controls, and custom Vietnamese translation labels.
* **Select2**:
  - Enriches standard HTML dropdown elements with search filters.
  - Applied when selecting students for class enrollments or assigning teachers.
* **Chart.js**:
  - Renders visual revenue charts on the dashboard home page.
  - Displays monthly earnings, active enrollment bars, and quarterly reports.
* **Summernote**:
  - Embedded rich text editor inside the settings dashboard to easily format invoice templates (payment conditions, bold titles, lists, headers).

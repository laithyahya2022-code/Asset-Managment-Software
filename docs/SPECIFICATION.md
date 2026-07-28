# Mada Asset Management System (AMS)
## Version 3.0 – Final Professional Specification

This is the official requirements specification for the school's AMS system.
Implementation status is tracked at the bottom of this document.

---

### 1. Executive Summary
A modern, enterprise-grade, web-based IT Asset Management System for schools
and educational institutions. Centralized management, monitoring, assignment,
maintenance, tracking, and reporting of all IT assets across their complete
lifecycle. Replaces Excel spreadsheets. Initially supports ~3,000 assets with
future scalability. Accessible from modern browsers on Windows, macOS, Linux,
iPhone, iPad, and Android. Responsive, modern, secure, multilingual UI.

### 2. Main Objectives
Replace Excel tracking · centralize asset information · improve inventory
accuracy · track full lifecycle · improve accountability · simplify
maintenance · manage software licenses · manage warranties · enterprise
reports · reduce manual work · improve decision making · support expansion.

### 3. User Roles & Permissions (RBAC)
Roles: Super Administrator, Administrator, IT Manager, IT Staff, Asset
Manager, Inventory Manager, Data Entry, Department Manager, Employee,
Read-Only User, Auditor. Permissions control view/create/edit/delete/import/
export/print/reports/dashboard/settings/administration. Each role has
configurable permissions.

### 4. Authentication & Security
Secure login, logout, password reset, change password, user profile, session
management, activity logs, audit logs, password encryption.
Future: Google Workspace SSO, Microsoft 365 SSO.

### 5. Dashboard
Cards: Total / Assigned / Available / Reserved / In-Maintenance / Lost /
Damaged / Retired assets. Charts: by category, status, department, branch,
building; maintenance, warranty, and license statistics. Widgets: recent
activity, upcoming warranty & license expirations, assets due for return,
notifications, quick actions.

### 6. Asset Categories
Desktop Computers, Laptops, Tablets, Monitors, Printers, Projectors, Servers,
Switches, Routers, Firewalls, Access Points, UPS Devices, CCTV, Telephones,
Accessories, Peripherals, Software Licenses — plus unlimited admin-created
categories.

### 7. Asset Information
General: ID, tag, type, category, manufacturer, model, serial.
Technical: OS, OS version, CPU, RAM, storage, graphics card, device
name/hostname, MAC address, IP address.
Purchase: date, cost, vendor, warranty expiration, warranty certificate,
invoice number. Status: status, condition, lifecycle, notes.
Attachments: images, warranty files, invoices, manuals, documents.

### 8. Asset Status
Available, Assigned (Checked Out), Reserved, In Use, In Storage,
Under Maintenance, Lost, Damaged, Retired, Disposed.

### 9. Asset Condition
New, Excellent, Good, Fair, Poor, Damaged — with condition history.

### 10. Automatic Asset Numbering
Per-category sequential tags: PC-000001, LPT-000001, PR-000001, DS-000001,
TAB-000001, MON-000001, SRV-000001, RTR-000001, SW-000001, AP-000001.

### 11. QR Code & Barcode Management
Automatic QR + barcode per asset; generation, printing, scanning, bulk label
printing. Every code uniquely identifies one asset.

### 12. Location Management
Hierarchy: Branch (Mada 1 / Mada 2 / Mada 3) → Building → Floor → Room, plus
Departments: Admissions & Registration, Accounting, Secretariat, Information
Technology, International Section, National Section – Primary, National
Section – Secondary. Unlimited additions by administrators.

### 13. Employee Management
Profile: name, employee ID, employee type (Administrative Staff / Teacher),
department, email, phone. Pages show assigned assets, lending history,
returned assets, current count.

### 14. Inventory Management
Physical inventory, verification, missing assets, reports, history;
last-inventory date/scan/verified-by tracked per asset; updates automatically
with every asset movement.

### 15–18. Lending, Return, Transfer, Check-In/Out
Lending records employee + location + dates + notes; complete history.
Return with inspection, condition-after-return, damage notes. Transfers
between employees/departments/buildings/branches with audit logging.
Check-out/check-in, reservations, overdue tracking, return reminders.

### 19. Asset Inquiry (QR / Barcode Scan)
Scan opens the full asset page: identity, tech specs, purchase & warranty,
status, assignment, location, maintenance & lending history, licenses,
files, notes, last inventory, last updated.

### 20. Maintenance Management
Preventive & corrective, scheduling, repair tracking, technician assignment,
costs, spare parts, reports; records include problem description, solution,
cost, status.

### 21. Asset Lifecycle Management
Purchased → In Inventory → Assigned → In Use → Under Maintenance → Returned →
Ready for Reassignment → End of Life → Retired → Disposed. End-of-life
identification with replacement recommendations.

### 22. Warranty Management
Tracking, expiration, alerts, history, certificates, vendor info, automatic
reminders.

### 23. Software License Management
Inventory, keys, assignment, device-to-license mapping, seats, expiration,
renewal, compliance, renewal alerts, custom reminder periods.

### 24. File Management
Images, PDFs, warranty certificates, invoices, manuals; upload / preview /
download / replace / delete.

### 25. Reporting
Asset inventory, employee, department, branch, building, maintenance,
warranty, license, audit log, inventory, movement, lifecycle, custom reports.
Export: Excel, CSV, PDF (print). Printable and downloadable.

### 26–28. Analytics, Search, Notifications
Live dashboards and analytics; global + advanced search across all key
fields; in-app and email notifications with configurable alert periods.

### 29. Audit Logs
Every important action recorded with user, timestamp, action, IP, details.

### 30. Enterprise Features
Asset timeline, movement history, bulk import/update/assign/transfer,
bulk QR/barcode printing, custom fields, asset relationships
(laptop → dock → monitor…), inventory verification history.

### 31. Import & Export
Excel (.xlsx) and CSV import with preview, field mapping, duplicate
detection, validation and error reporting; Excel/CSV/PDF(print) export.

### 32. Backup & Recovery
Database backup/restore, automatic daily backup, manual backup, history,
admin-only access.

### 33. Administration Panel
Manage users, roles, permissions, branches/buildings/floors/rooms,
departments, employee types, categories, statuses, conditions, notification/
email/QR/backup/language/system settings — without code changes.

### 34. Multi-Language Support
English (default) + Arabic with full RTL and a language switcher.

### 35–36. Responsive Design & UI/UX
Fully responsive on all devices; professional dashboard, modern navigation,
enterprise layout, modern icons, fast pages, consistent design.

### 37–38. Analytics & Search Performance
Asset/inventory/maintenance/warranty/license/department analytics, executive
insights, trend analysis; instant search on tags, serials, employees,
locations, specs.

### 39–40. Development & Future Maintenance
Developed and maintainable with Replit Pro **and** Microsoft Visual Studio
Code. Modular architecture; each module planned, designed, developed, tested,
reviewed. Industry-standard practices for long-term maintainability.

### 41–42. Deployment & Ownership
Deployed on the school's own on-premises servers, operating independently of
any hosting provider. The school owns the complete source code, database,
schema, configuration, installation files, and documentation.

### 43–45. Future Expansion & Final Vision
Architecture supports new categories, branches, roles, reports, widgets,
mobile apps, API and third-party integrations, optional cloud sync and
AI analytics — without a system redesign.

---

## Implementation Status

| Spec area | Status |
|---|---|
| §1–2 Web app, responsive, multilingual | ✅ Implemented |
| §3 11 roles with editable permission matrix | ✅ Implemented |
| §4 Auth & security (SSO = future) | ✅ Implemented (SSO planned) |
| §5 Dashboard cards/charts/widgets | ✅ Implemented |
| §6 Categories incl. defaults + unlimited custom | ✅ Implemented |
| §7 Full asset info incl. technical specs | ✅ Implemented |
| §8–9 Statuses & conditions with history | ✅ Implemented |
| §10 Automatic per-category numbering | ✅ Implemented |
| §11 QR/barcode generate/print/scan/bulk | ✅ Implemented |
| §12 Mada branches → buildings → floors → rooms | ✅ Implemented |
| §13 Employees with ID and type | ✅ Implemented |
| §14 Inventory with verification history | ✅ Implemented |
| §15–18 Lending, return inspection, transfer, check-in/out | ✅ Implemented |
| §19 Asset inquiry via scan | ✅ Implemented |
| §20 Maintenance with problem/solution | ✅ Implemented |
| §21 Lifecycle + end-of-life report | ✅ Implemented |
| §22–23 Warranty & licenses with custom alert periods | ✅ Implemented |
| §24 File management | ✅ Implemented |
| §25 Reports incl. movement & lifecycle; Excel/CSV/print | ✅ Implemented |
| §26–29 Analytics, search, notifications, audit logs | ✅ Implemented |
| §30 Timeline, bulk assign/transfer, relationships | ✅ Implemented |
| §31 Excel/CSV import with preview & validation | ✅ Implemented |
| §32 Backup & recovery incl. automatic daily | ✅ Implemented |
| §33 Administration panel | ✅ Implemented |
| §34 English + Arabic RTL | ✅ Implemented |
| §35–38 Responsive, UI, analytics, search | ✅ Implemented |
| §39–40 Replit Pro + VS Code maintainability | ✅ .replit + .vscode included |
| §41–42 On-premises deployment & full ownership | ✅ DEPLOYMENT.md + full repo |
| §43 Mobile apps, SSO, integrations, AI analytics | 🔭 Future expansion |
| Scheduled report emails | 🔭 Future (alert emails implemented) |
| Electronic signature on lending | 🔭 Future (optional in spec) |

# IHMIS — Integrated Health Management Information System

A multi-role clinic management web platform built for the Federal Polytechnic Ilaro school health center, digitizing the full walk-in patient workflow from registration through discharge.

> Final-year Computer Science software project — Federal Polytechnic Ilaro
> Supervisor: Mr. Akinode J. Lekan

---

## Overview

IHMIS replaces the clinic's paper-based file system with a role-based digital workflow covering six staff roles: **Admin, Medical Health Officer (MHO), Doctor, Nurse, Pharmacist,** and **Lab Technician**. Each role gets a dedicated portal scoped to exactly the actions and data it needs, enforced end-to-end through role-based access control (RBAC).

## Patient Journey

```
MHO (Registration & File Custody)
        │
        ▼
     Nurse (Vitals & Triage)
        │
        ▼
     Doctor (Diagnosis, Prescription, Lab Orders)
        │
    ┌───┴────┐
    ▼         ▼
  Lab      Pharmacy
(optional)  (Dispense & Auto-Close)
    │         │
    └────┬────┘
         ▼
   Patient Discharged
```

- **MHO / Records Officer** — first point of contact; registers patients, opens/searches health files, and forwards them onward. Can also manually close files.
- **Nurse** — receives the forwarded file, records vital signs (weight, height, temperature, blood pressure), triages, and forwards to the Doctor.
- **Doctor** — reviews history and vitals, diagnoses, prescribes, and may request a lab test or issue a certificate/referral/admission.
- **Laboratory Technician** — receives test requests, records and uploads results back to the Doctor.
- **Pharmacist** — receives the final prescription, dispenses medicine, updates drug inventory, and auto-closes the file (last stop in the flow).
- **Admin** — manages users/roles, views audit logs and system-wide analytics.

## Key Features

- **Six dedicated role-based portals**, each with its own dashboard, navigation, and permission scope
- **Two-layer RBAC**: dynamic role assignment at the database level, enforced by a static `role_required()` decorator at the API layer
- **Full patient file lifecycle** across six tabs: Biodata, Visit History, Diagnoses, Prescriptions, Lab Results, and Documents
- **Immutable audit logging** for every clinical read/write action
- **AI-assisted clinical decision support** (Phase 1 — knowledge-based / rule-based, not model-trained):
  - **Triage Assistant** — NEWS2-inspired vitals scoring for Nurses
  - **Drug Interaction Checker** — flags interactions and recommendations for Doctors
  - **Inventory Forecast** — stock-level prediction for Pharmacists
- **In-app notifications and profile management** across all six portals
- **Admission workflow** with dedicated `admitted` patient status
- **Hybrid deployment architecture** — on-premise application server with encrypted nightly cloud backup, so core clinic functions keep running through internet or power outages

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| ORM | SQLAlchemy |
| Auth | Flask-JWT-Extended |
| Migrations | Flask-Migrate / Alembic |
| Database | MySQL (XAMPP for local dev, Aiven Cloud for deployment) |
| Frontend | HTML, CSS, vanilla JavaScript |
| Charts | Chart.js |
| Dev server | VS Code Live Server |

## Project Structure

```
ihmis/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (auth, patients, vitals, laboratory, prescriptions, ai, etc.)
│   │   ├── models/          # SQLAlchemy models
│   │   └── services/        # Business logic layer
│   ├── migrations/          # Alembic migration history
│   └── run.py
├── frontend/
│   ├── assets/
│   │   ├── css/
│   │   ├── js/               # Shared modules: api.js, sidebar.js, notifications-widget.js, utils.js
│   │   └── img/
│   └── pages/
│       ├── admin/
│       ├── mho/
│       ├── nurse/
│       ├── doctor/
│       ├── lab/
│       └── pharmacist/
└── .gitignore
```

## Design System

Emerald Green / White / Gray / Blue palette on a dark sidebar layout, kept consistent across all six portals.

## Getting Started (Local Development)

**Prerequisites:** Python 3.x, MySQL (or XAMPP), Node-free frontend (plain JS)

```bash
# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Configure environment
copy .env.example .env         # then fill in your DB credentials and JWT secret

# Run migrations
python -m flask db upgrade

# Seed demo accounts (one per non-Admin role, password: Password123!)
python -m flask seed-demo-users

# Start the server
python run.py
```

```bash
# Frontend
# Open the /frontend folder in VS Code and launch with Live Server
```

## Academic Context

This project includes a full academic artifact set alongside the working software: system diagrams (component, class, sequence), an RBAC and data privacy addendum, a gap analysis, and a defense presentation. The AI layer is intentionally scoped as **Phase 1 — Knowledge-Based Decision Support** (rule-based, no model training); federated learning across institutions is documented as future work (Phase 2).

## Known Limitations

- RBAC is currently enforced at the role level, not the object level (documented gap — e.g. a Nurse with a valid patient ID could technically query a patient not yet forwarded to them).
- AI features are rule-based decision support, not predictive ML models, by design for this phase.

## License

Academic project — Federal Polytechnic Ilaro, Department of Computer Science.
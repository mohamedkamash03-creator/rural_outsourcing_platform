# Rural Workforce OS

A runnable MVP for a B2B managed rural outsourcing company. It covers workforce registration, ID verification workflow, skills, assessments, free training, clients, service requests, projects, assignments, village offices, shifts, attendance, tasks and dashboards.

## Stack
- FastAPI
- SQLite
- JWT authentication
- Vanilla HTML/CSS/JavaScript frontend

## Run
```bash
cd rural_outsourcing_platform
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install fastapi uvicorn PyJWT
uvicorn app:app --reload
```
Open http://127.0.0.1:8000

## Demo accounts
- Admin: admin@ruralos.local / Admin123!
- HR: hr@ruralos.local / HR123!
- Operations: ops@ruralos.local / Ops123!
- Coordinator: coord@ruralos.local / Coord123!
- Worker: worker@ruralos.local / Worker123!
- Client: client@ruralos.local / Client123!

## Important production work still required
This is a functional MVP/prototype, not a production deployment. Before real users or sensitive ID data are used, add production secrets, HTTPS, stronger password policy, encrypted document storage, real identity verification, audit hardening, backups, CSRF protection where applicable, rate limiting, granular client/worker data isolation, payroll/accounting integrations, legal contracts/consent, and a proper production database/object storage.

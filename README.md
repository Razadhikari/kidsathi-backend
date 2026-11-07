# KidSathi API (किडसाथी)

Backend for **KidSathi**, a school–parent app for Montessori schools in Nepal.
Parents follow their child's day; schools run attendance, communication and fees.

Django + Django REST Framework, PostgreSQL, JWT auth, built as a **modular monolith**.

## Modules in this first version

| Module | What it does |
|---|---|
| `apps.accounts` | Users (one person = one phone number), **parent login with SMS OTP**, staff login with phone/email + password, JWT tokens, `/me` |
| `apps.schools` | Schools (tenants), memberships (school admin / teacher / accountant / parent), classrooms, inviting members |
| `apps.children` | Children, guardians (mother/father/grandparent…, who can pick up), parents' "my children" view, Nepali (BS) dates |
| `apps.core` | Shared base models, multi-tenancy via `X-School-ID`, role permissions, Nepali phone + date helpers |

## How multi-tenancy works

- Every school-owned table has a `school` foreign key.
- Clients send the school they're acting in as the `X-School-ID` header.
- The API checks that the user has an active membership in that school, and every query is filtered by it.
- PostgreSQL row-level security will be added later as a second layer of protection.

## API (v1)

| Method | Path | Who |
|---|---|---|
| POST | `/api/v1/auth/otp/request/` | Parent: send code to `phone_number` |
| POST | `/api/v1/auth/otp/verify/` | Parent: `phone_number` + `code` → `access`, `refresh` |
| POST | `/api/v1/auth/login/` | Staff: `identifier` (phone or email) + `password` |
| POST | `/api/v1/auth/token/refresh/` | Everyone |
| GET/PATCH | `/api/v1/auth/me/` | Everyone |
| GET/POST/PATCH | `/api/v1/schools/` | Members see their schools; school admins can edit theirs; only the KidSathi team can create schools |
| CRUD | `/api/v1/classrooms/` | Staff read, school admin write (needs `X-School-ID`) |
| GET, POST `invite/` | `/api/v1/members/` | School admin (needs `X-School-ID`) |
| CRUD | `/api/v1/children/` | Staff read, school admin write (needs `X-School-ID`) |
| POST | `/api/v1/children/{id}/guardians/` | School admin: link a parent by phone number (invites them) |
| GET | `/api/v1/my/children/` | Parent: own children across schools |

Interactive docs are served at `/api/docs/` when the server is running.

## Run locally

```bash
cp .env.example .env
docker compose up --build          # API on http://localhost:8000, Postgres, Redis
docker compose exec api python manage.py createsuperuser
```

Or without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate           # uses SQLite if DATABASE_URL is not set
python manage.py runserver
```

In development, OTP codes are printed to the server log (`SMS_BACKEND=console`).

## Tests and linting

```bash
pytest
ruff check .
```

GitHub Actions runs linting, Django checks, a check for missing migrations, the tests (on Postgres) and a Docker build on every push.

## Roadmap for the next modules

1. Attendance (check-in/out) and absence registration
2. Daily agenda and care log (meals, nap, notes)
3. Messaging and notice board, with push (FCM) and SMS fallback
4. Photos (S3 pre-signed uploads, consent-aware)
5. Billing: fee plans, monthly invoices (BS months), PDF, eSewa/Khalti/Fonepay
6. Montessori progress tracking

Next steps on the infrastructure side: Terraform for AWS (ECS Fargate, RDS, S3, CloudFront) in `ap-south-1`.

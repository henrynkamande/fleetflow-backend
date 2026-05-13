# Fleet Flow — Backend API

REST API for **Fleet Flow**, a fleet management platform: fleet-owner and driver accounts, company onboarding, vehicles, trips, and KYC document handling.

**Repository:** [github.com/wametee/fleetflow-backend](https://github.com/wametee/fleetflow-backend)

## Stack

| Layer | Technology |
|--------|------------|
| Framework | [Django](https://www.djangoproject.com/) 5.2 |
| API | [Django REST Framework](https://www.django-rest-framework.org/) 3.17 |
| Auth | [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/) (access + refresh, rotation, blacklist) |
| DB (local) | SQLite (`db.sqlite3`) |
| Other | `django-cors-headers`, Pillow (uploads), `pyotp`, WhiteNoise, Gunicorn |

API versioning uses **Accept header** versioning (`DEFAULT_VERSION` `1.0`). Send requests with the version your client expects per DRF’s `AcceptHeaderVersioning` rules.

## Project layout

- **`oauth`** — Custom user model, registration/login, JWT refresh/logout, OTP for drivers, company CRUD, driver onboarding, profiles, password flows, KYC uploads, fleet-owner dashboards.
- **`vehicles`** — Vehicle CRUD and driver assignment.
- **`trips`** — Trip lifecycle: create, update, start, complete, cancel, approve.

URL prefixes (all under the Django site root):

| Prefix | Purpose |
|--------|---------|
| `/admin/` | Django admin |
| `/users/api/` | Auth, users, company, drivers, KYC, dashboards |
| `/vehicles/api/` | Vehicles |
| `/trips/api/` | Trips |

## Prerequisites

- **Python** 3.12+ (3.14 used in some environments is fine if dependencies install cleanly)
- `pip` and a virtual environment tool (`python -m venv`)

## Quick start

```bash
git clone https://github.com/wametee/fleetflow-backend.git
cd fleetflow-backend

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/

python manage.py runserver
```

The API defaults to `http://127.0.0.1:8000/`. With `DEBUG=True`, the browsable API is enabled for JSON endpoints.

## Configuration (environment variables)

Create a `.env` file or export variables in your shell (values below are illustrative; production must override secrets).

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret; **required in production** |
| `DEBUG` | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts (default includes a Render hostname in code—override for your domain) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins when `DEBUG=False` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF (e.g. your frontend HTTPS URL) |
| `FRONTEND_URL` | Base URL for email links (verify email, reset password, login) |
| `EMAIL_*` | SMTP and sender settings when not using console email (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, etc.) |
| `ADMIN_EMAIL` | Used in `ADMINS` for error notifications |

PostgreSQL is prepared as commented configuration in `fleetflow/settings.py`; set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` when you switch the `DATABASES` block to Postgres.

## Production notes

- Run with **Gunicorn** (already in `requirements.txt`), e.g. `gunicorn fleetflow.wsgi:application`, behind a reverse proxy with TLS.
- Set `DEBUG=False`, strong `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`.
- Use PostgreSQL for production instead of SQLite.
- Collect static files: `python manage.py collectstatic`.
- Media uploads go under `media/` (avatars, KYC, logos); ensure persistent storage or object storage in production.

## Tests

```bash
python manage.py test
```

## License

No license file is present in this repository; add a `LICENSE` file if you intend to specify terms for reuse.

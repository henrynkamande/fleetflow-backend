# Fleet Flow — Backend API

REST API for **Fleet Flow**, a fleet management platform: fleet-owner and driver accounts, company onboarding, vehicles, trips, and KYC document handling.

**Repository:** [github.com/wametee/fleetflow-backend](https://github.com/wametee/fleetflow-backend)

## Stack

| Layer | Technology |
|--------|------------|
| Framework | [Django](https://www.djangoproject.com/) 6.0 |
| API | [Django REST Framework](https://www.django-rest-framework.org/) 3.17 |
| Auth | [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/) (access + refresh, rotation) |
| DB | [MongoDB](https://www.mongodb.com/) via [django-mongodb-backend](https://www.mongodb.com/docs/languages/python/django-mongodb/) |
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
| `/reports/api/` | Financial reports |
| `/billing/api/` | Stripe billing |
| `/platform/api/` | Platform admin: `auth/login`, `auth/register`, overview, companies, users |
| `/content/api/` | Public blog + admin blog CRUD (admin: platform JWT) |

### Platform admin bootstrap

```bash
export PLATFORM_ADMIN_EMAIL=you@example.com
export PLATFORM_ADMIN_PASSWORD='your-secure-password'
python manage.py create_platform_admin
```

Sign in on the frontend; platform admins are sent to `/platform` (`redirect_url: /platform`).

If login returns **400** with a small JSON body (`non_field_errors`: “Invalid email or password”), the user does not exist or the password is wrong. Run `migrate`, then `create_platform_admin` (or reset the password with the same command — it updates an existing email). Confirm locally:

```bash
python manage.py verify_login --email you@example.com --password 'YourSecurePass1!'
```

On failure, Django logs the exact validation errors when you attempt sign-in (`Login failed for …` in the runserver terminal).

Product decisions: `docs/PLATFORM_AND_CONTENT.md` in the monorepo.

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

## Email (SendGrid) on Render / production

Signup and password reset need outbound email. Set on the **backend** service:

| Variable | Purpose |
|----------|---------|
| `SENDGRID_API_KEY` | SendGrid API key (Mail Send → SMTP uses `apikey` as username) |
| `DEFAULT_FROM_EMAIL` | Must match a **verified** sender in SendGrid (e.g. `noreply@myfleetvault.com`) |
| `APP_BRAND_NAME` | Optional; used in subject lines (default `FleetVault`) |

Do **not** set `EMAIL_CONSOLE=true` in production. After deploy, check logs for `Auth email sent` or `Auth email failed`.

Fleet owner signup stores data in `pending_fleet_owner_signups` until OTP succeeds; no `User` row is created until verification.

## Configuration (environment variables)

Copy `.env.template` to `.env` and fill in values (loaded automatically at startup), or export variables in your shell.

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret; **required in production** |
| `DEBUG` | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts (default: Render hostname; with `DEBUG=True`, `localhost` and `127.0.0.1` are added automatically) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins when `DEBUG=False` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF (e.g. your frontend HTTPS URL) |
| `FRONTEND_URL` | Base URL for email links (verify email, reset password, login) |
| `EMAIL_*` | SMTP and sender settings when not using console email (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, etc.) |
| `ADMIN_EMAIL` | Used in `ADMINS` for error notifications |
| `MONGO_URI` | **Required.** MongoDB connection string (Atlas SRV or `mongodb://…`). |
| `MONGO_DB_NAME` | Database name (default: `fleetflow`). Should match the database in `MONGO_URI` if the URI includes one. |

Run `python manage.py migrate` against your cluster before serving traffic. JWT refresh rotation does not use the token blacklist app (Simple JWT’s blacklist models are SQL-oriented); access and refresh tokens still work.

## Render + MongoDB Atlas

If deploy logs show `ServerSelectionTimeoutError` / `SSL handshake failed` / `TLSV1_ALERT_INTERNAL_ERROR` during `manage.py migrate`, check the following:

1. **Python version** — New Render services default to Python 3.14, which can break TLS to Atlas. This repo pins **`3.12`** via `.python-version`. Alternatively set `PYTHON_VERSION` to a full version (e.g. `3.12.8`) on the service. Redeploy after changing.
2. **Atlas Network Access** — In Atlas → Network Access, allow outbound from Render (e.g. `0.0.0.0/0` for a quick test, or [Render outbound IPs](https://render.com/docs/static-outbound-ip-addresses) on a paid plan).
3. **`MONGO_URI` on Render** — Set the same Atlas SRV URI you use locally (`mongodb+srv://…`), with URL-encoded password if it contains special characters.
4. **Start command** — Example: `python manage.py migrate && gunicorn fleetflow.wsgi:application --bind 0.0.0.0:$PORT`

## Scale & performance

- **List APIs** (`trips`, `vehicles`, company `users` / `drivers`, KYC) accept `page` and `page_size` (alias `limit`, max **100**). Responses include `count`, `page`, `page_size`, and `total_pages` plus the list key (`trips`, `vehicles`, etc.). Trip lists support `include_stats=true` on page 1 for dashboard aggregates without loading every row.
- **Indexes**: trips are indexed on `(company, planned_departure_time)` and common filter fields; run `python manage.py migrate` after deploy.
- **Throttling**: DRF default user/anon throttles are configured in `settings.py`; tune for production load.
- **Horizontal scale**: run stateless Gunicorn workers behind a load balancer; use MongoDB connection limits appropriate to worker count.
- **Later**: Redis cache for dashboard overview, read preference for reporting, background workers for exports and billing webhooks (Celery/RQ).

## Production notes

- Run with **Gunicorn** (already in `requirements.txt`), e.g. `gunicorn fleetflow.wsgi:application`, behind a reverse proxy with TLS.
- Set `DEBUG=False`, strong `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`.
- Set `MONGO_URI` (and optionally `MONGO_DB_NAME`) for production data storage.
- Collect static files: `python manage.py collectstatic`.
- Media uploads go under `media/` (avatars, KYC, logos); ensure persistent storage or object storage in production.

## Tests

```bash
python manage.py test
```

## License

No license file is present in this repository; add a `LICENSE` file if you intend to specify terms for reuse.

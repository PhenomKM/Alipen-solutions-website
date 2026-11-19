# Backend setup

The website quote API stores requests in Supabase PostgreSQL and sends transactional email through the Resend HTTPS API. SQLite and Gmail SMTP are no longer used by the application.

For local setup, production environment variables, Render configuration, GitHub commands, and troubleshooting, see [DEPLOYMENT_README.md](DEPLOYMENT_README.md).

Required settings are `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and `SITE_URL`. Configure `RESEND_API_KEY`, `MAIL_FROM`, and `ADMIN_EMAIL` for quote email notifications. Copy `.env.example` to `.env` for local work and replace the placeholders. See [DEPLOYMENT_README.md](DEPLOYMENT_README.md#admin-dashboard-and-credentials) for generating the Argon2id admin hash and the Render setup. Never commit `.env`, database connection strings, API keys, admin credentials, or quote/customer records.

Install the PostgreSQL driver and start the app with:

```powershell
python -m pip install -r requirements.txt
python server.py
```

The server binds to `0.0.0.0` and uses the `PORT` environment variable (3000 locally when it is not set). At startup it creates `quote_requests` if needed and applies an additive migration creating the `admin_users` table and unique username index; it does not modify or delete quote records. `GET /healthz` checks database connectivity. The existing `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` environment variables continue to define the primary administrator; additional admins are managed by that account in the dashboard. Quote submissions are saved even if Resend email delivery is unavailable; the response identifies each message as `accepted` (accepted by Resend), `failed`, or `not_configured` without returning customer data. `accepted` does not guarantee inbox delivery.

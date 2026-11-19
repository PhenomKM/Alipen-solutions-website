# Backend setup

The website quote API stores requests in Supabase PostgreSQL and sends transactional email through the Resend HTTPS API. SQLite and Gmail SMTP are no longer used by the application.

For local setup, production environment variables, Render configuration, GitHub commands, and troubleshooting, see [DEPLOYMENT_README.md](DEPLOYMENT_README.md).

Required settings are `DATABASE_URL`, `RESEND_API_KEY`, `MAIL_FROM`, `ADMIN_EMAIL`, and `SITE_URL`. Copy `.env.example` to `.env` for local work and replace the placeholders. Never commit `.env`, database connection strings, API keys, or quote/customer records.

Install the PostgreSQL driver and start the app with:

```powershell
python -m pip install -r requirements.txt
python server.py
```

The server binds to `0.0.0.0` and uses the `PORT` environment variable (3000 locally when it is not set). It creates the PostgreSQL `quote_requests` table at startup. `GET /healthz` checks database connectivity. Quote submissions are saved even if Resend email delivery is unavailable; the response identifies each message as `accepted` (accepted by Resend), `failed`, or `not_configured` without returning customer data. `accepted` does not guarantee inbox delivery.

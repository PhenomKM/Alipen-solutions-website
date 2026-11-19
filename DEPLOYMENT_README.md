# Alipen website deployment guide

This project uses one Render Python web service for the existing pages and quote API, Supabase PostgreSQL for quote records, and Resend's HTTPS API for transactional emails. The public site will use its Render `onrender.com` URL initially. No live service has been created or connected by these local changes.

## 1. Create a Supabase project

1. Create an account at [Supabase](https://supabase.com/) and create a project.
2. Save the database password in a password manager. It cannot be recovered as plain text.
3. Wait for the database to finish provisioning.
4. Open the project dashboard's **Connect** panel. Copy the PostgreSQL connection string for the **Session pooler**. A persistent Render web service is not serverless, but the pooler's IPv4 endpoint avoids direct-endpoint IPv6 reachability issues from some hosts.
5. Replace the password placeholder. URL-encode reserved characters in the password (for example `@`, `#`, `%`, `?`, `/`, or spaces).
6. Keep the complete URL private; it grants database access. Set `sslmode=require` if the copied URL does not include an SSL option.

The server creates `quote_requests` on startup. The existing local SQLite database is not migrated or read.

The quote endpoint accepts JSON requests up to 64 KiB and applies a basic in-memory limit of 8 submissions per IP per 15 minutes. This limiter resets on restart and does not coordinate across multiple instances; add an edge or shared-store rate limit before scaling out.

See [Supabase's PostgreSQL connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres) for current connection modes, pooler selection, and SSL guidance.

## 2. Configure Resend

1. Create a [Resend](https://resend.com/) account.
2. Under **Domains**, add a domain or sending subdomain that you control.
3. Add the DNS records Resend displays (usually sending verification/DKIM and SPF records) at the DNS provider that hosts your domain. Do not copy example DNS values from another project.
4. Return to Resend and run **Verify**. Wait until sending is marked verified. Resend's required records and status are specific to your domain.
5. Under **API Keys**, create a key that can send email. Store it as `RESEND_API_KEY`; never commit it.
6. Set `MAIL_FROM` to a sender address on the verified domain, for example `Alipen Quotes <quotes@send.yourdomain.example>`.
7. Set `ADMIN_EMAIL` to the inbox that should receive quote notifications.

Without a configured key/from address, or if Resend rejects a message, the quote stays saved and the API reports email delivery as `not_configured` or `failed`. A successful API response is reported as `accepted`, meaning Resend accepted the message for delivery; it does not guarantee inbox placement. The customer sees that status and is asked to keep their quote reference when email was not accepted.

See [Resend's domain setup](https://resend.com/docs/dashboard/domains/introduction) and [email API](https://resend.com/docs/api-reference/emails/send-email) documentation for the current dashboard workflow and API rules.

## 3. Prepare the private GitHub repository

Create a **private** repository on GitHub. Do not upload `.env`, database files, real credentials, or customer records. `.gitignore` excludes those local files; `.env.example` contains placeholders only.

From PowerShell in the project directory, after creating the empty private repo, use:

```powershell
git init
git add .
git status
git commit -m "Prepare Alipen website for deployment"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-PRIVATE-REPO.git
git push -u origin main
```

Replace the remote URL with the URL shown by GitHub. Review `git status` before the commit. These commands are instructions only; no GitHub repository has been created or pushed by this work.

## 4. Create the Render Web Service

1. In Render choose **New → Blueprint** and connect the private GitHub repository, or create a **New Web Service** from it.
2. If using the Blueprint, Render reads `render.yaml`. If configuring manually, use:
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `python server.py`
   - Health check path: `/healthz`
3. Connect the GitHub account and select the private repository and `main` branch. Enable automatic deploys if desired.
4. In **Environment**, add these values:

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | Supabase Session pooler URL, including password and SSL mode |
   | `RESEND_API_KEY` | Secret key from Resend |
   | `MAIL_FROM` | Sender address on the verified Resend domain |
   | `ADMIN_EMAIL` | Admin notification inbox |
   | `SITE_URL` | The assigned HTTPS URL, e.g. `https://alipen-website.onrender.com` |

   Render sets `PORT` for the running service. The server binds to `0.0.0.0` and reads that value automatically.
5. Deploy. Confirm the service becomes healthy before testing quote submission.

Render's [web service documentation](https://render.com/docs/web-services) covers Git integration, port binding, environment variables, and health checks.

## 5. Test the deployed website

1. Open the Render URL and visit `/`, `/products`, `/products/contec-e12-ecg`, `/about`, and `/contact`.
2. Open `/healthz`; expect HTTP 200 and `{"status":"ok"`. A database connectivity problem returns 503.
3. Submit one clearly marked test quote using an inbox you control. Confirm a reference is shown, the row appears in Supabase's `quote_requests` table, and the admin/customer emails arrive.
4. If email is unconfigured or rejected, the API response and confirmation dialog must say so; it must not say the emails were sent.
5. Check that `/server.py`, `/.env`, `/.env.example`, `/requirements.txt`, `/README.md`, and `/alipen_quotes.db` return 404.
6. Delete the test quote from Supabase after validation if it is no longer needed.

Example health request:

```powershell
Invoke-WebRequest https://YOUR-SERVICE.onrender.com/healthz
```

## 6. Free-tier limits and production considerations

Free plans are suitable for a low-traffic trial, not a production service that needs availability guarantees or backups. Provider quotas and prices can change; check each dashboard before launch.

- **Render Free web service:** sleeps after 15 minutes without incoming traffic and can take about a minute to wake. The filesystem is ephemeral. This app stores quotes in Supabase and serves checked-in static assets, so it does not depend on local persistent storage. Free compute has no uptime SLA and limited included usage. See [Render free services](https://render.com/docs/free).
- **Supabase Free:** currently includes a 500 MB database, but projects pause after one week of inactivity and do not include automatic backups. A paused database makes quote submission unavailable until resumed. Upgrade for a continuously active production database, backups, support, and additional capacity. See [Supabase pricing](https://supabase.com/pricing).
- **Resend Free:** currently includes 3,000 transactional emails per month with a 100-per-day limit. The app sends two emails per successful quote (admin and customer). A verified sender domain is required for normal recipient delivery. See [Resend pricing](https://resend.com/pricing).
- **GitHub:** a private repository is sufficient for source hosting; it does not run this Python backend by itself.

If the free limits are not suitable, provider entry pricing checked 19 November 2026 is Render paid web compute from about $7/month per service, Supabase Pro from $25/month, and Resend Pro from $20/month. These are provider list prices and can change; Resend can remain free while volume stays within its free quota. For a production healthcare procurement site, budget for always-on web compute, a non-pausing PostgreSQL plan with backups, and suitable email volume. Confirm privacy, retention, and backup obligations for customer contact information before accepting real requests.

## 7. Troubleshooting

- **Render says no open port:** confirm the start command is `python server.py`; the app must bind to `0.0.0.0` and Render's `PORT`.
- **Deploy fails importing psycopg:** check `requirements.txt` is committed and the build log completed `pip install -r requirements.txt`.
- **`/healthz` returns 503:** check `DATABASE_URL`, URL-encoded database password, SSL mode, Supabase project state, and the exact session-pooler host/user/port copied from Supabase Connect.
- **Quote submission returns 503:** inspect the Render application logs for startup/database failures. API responses deliberately do not expose database details or customer information.
- **Quote is saved but email is not accepted:** inspect Resend's email logs; verify the API key, sender domain status, `MAIL_FROM`, recipient, and account limits. The saved quote reference remains valid.
- **Resend accepted the messages but they do not arrive:** inspect Resend's email logs, spam/quarantine, and domain SPF/DKIM setup. `accepted` means the provider accepted the API request; it does not guarantee inbox placement.
- **Product page image missing:** confirm the referenced file exists under `public/images/` and its path capitalization matches the catalog entry.

## 8. Local verification

Install dependencies and configure a local `.env` from `.env.example`, using a test Supabase project/connection string and Resend key only if you intend to test external services. Then run:

```powershell
python -m pip install -r requirements.txt
python -m py_compile server.py
python -m unittest discover -s tests -v
python server.py
```

The automated suite uses database and Resend mocks, so passing tests do not prove that Supabase, Resend, or Render credentials and services are configured correctly.

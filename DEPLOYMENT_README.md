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

## Admin dashboard and credentials

The protected dashboard is available at `/admin`; sign in at `/admin/login`. There is no public registration. Configure `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` before deployment. The password hash must be Argon2id, and the original password is never stored in this project. Generate one locally without putting the password in shell history:

```powershell
python -m pip install -r requirements.txt
python -c "from getpass import getpass; from argon2 import PasswordHasher; print(PasswordHasher().hash(getpass('Admin password: ')))"
```

Set the printed hash as `ADMIN_PASSWORD_HASH` and choose a private `ADMIN_USERNAME` in your local `.env` or Render environment settings. Keep `.env` private and never commit actual credentials. The dashboard uses an HttpOnly, SameSite Strict server-side session cookie, CSRF tokens for changes, HTTPS Secure cookies in production, and a per-IP login limit. Sessions are held in process memory and expire after inactivity; restarting the service signs admins out. Run a single web instance unless session storage is moved to a shared store.

The environment-configured account remains the primary administrator and keeps the existing Render variables. Only this account sees **Admin accounts** in the dashboard. It can create, rename, reset passwords for, and deactivate additional accounts. To change the primary administrator's own credentials, update `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` in Render. Additional accounts use Argon2id hashes stored in PostgreSQL; passwords and hashes are never returned by the API. Account changes invalidate that account's existing sessions. At startup, the server safely creates the new `admin_users` table and a case-insensitive unique-username index if they do not exist. This additive migration does not alter or remove quote records. No new Render environment variables are required; keep `DATABASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH` configured as before.

Quote records remain in the existing `quote_requests` table. Admin notifications continue through the existing Resend setup and go to `ADMIN_EMAIL` after the quote is saved. The quote endpoint sends one admin and one customer message per successfully saved submission.

The quote endpoint accepts JSON requests up to 64 KiB and applies a basic in-memory limit of 8 submissions per IP per 15 minutes. This limiter resets on restart and does not coordinate across multiple instances; add an edge or shared-store rate limit before scaling out.

See [Supabase's PostgreSQL connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres) for current connection modes, pooler selection, and SSL guidance.

## 2. Configure Resend

1. Create a [Resend](https://resend.com/) account.
2. Under **Domains**, add a domain or sending subdomain that you control.
3. Add the DNS records Resend displays (usually sending verification/DKIM and SPF records) at the DNS provider that hosts your domain. Do not copy example DNS values from another project.
4. Return to Resend and run **Verify**. Wait until sending is marked verified. Resend's required records and status are specific to your domain.
5. Under **API Keys**, create a key that can send email. Store it as `RESEND_API_KEY`; never commit it.
6. Set `MAIL_FROM` to a sender address on the verified domain, for example `Alipen Quotes <quotes@send.yourdomain.example>`.
7. Set `ADMIN_EMAIL` to `kayvo18@gmail.com` for Alipen quote notifications.

Without a configured key/from address, or if Resend rejects a message, the quote stays saved and the API reports email delivery as `not_configured` or `failed`. A successful API response is reported as `accepted`, meaning Resend accepted the message for delivery; it does not guarantee inbox placement. The customer sees that status and is asked to keep their quote reference when email was not accepted.

When delivery fails, Render logs include the notification type, quote reference, HTTP status, and a safe Resend error code. Raw Resend response text, recipients, and credentials are excluded. Check Render's **Logs** and Resend's **Emails/Logs** for the same submission time and reference. In Render's **Environment** settings, make sure `RESEND_API_KEY`, `MAIL_FROM`, and `ADMIN_EMAIL` are present; `ADMIN_EMAIL` should be `kayvo18@gmail.com`. Do not copy the example sender address: set `MAIL_FROM` to an address on a domain already verified for sending in your Resend account.

See [Resend's domain setup](https://resend.com/docs/dashboard/domains/introduction) and [email API](https://resend.com/docs/api-reference/emails/send-email) documentation for the current dashboard workflow and API rules.

## 3. Prepare the private GitHub repository

Create a **private** repository on GitHub. Do not upload `.env`, database files, real credentials, or customer records. `.gitignore` excludes those local files; `.env.example` contains placeholders for credentials and sender values.

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
   | `ADMIN_EMAIL` | `kayvo18@gmail.com` |
   | `ADMIN_USERNAME` | Private administrator login name |
   | `ADMIN_PASSWORD_HASH` | Argon2id hash generated with the command above |
   | `SITE_URL` | The assigned HTTPS URL, e.g. `https://alipen-website.onrender.com` |

   Render sets `PORT` for the running service. The server binds to `0.0.0.0` and reads that value automatically.
5. Deploy. Confirm the service becomes healthy before testing quote submission.

After deploy, visit `/admin/login` and sign in with the configured username and the password used to make the hash. Use the Requests page to search by reference, customer, facility, or email; filter by status; open a request to view its details; and update its status. Sign out using the account section.

Render's [web service documentation](https://render.com/docs/web-services) covers Git integration, port binding, environment variables, and health checks.

## 5. Test the deployed website

1. Open the Render URL and visit `/`, `/products`, `/products/contec-e12-ecg`, `/about`, and `/contact`.
2. Open `/healthz`; expect HTTP 200 and `{"status":"ok"`. A database connectivity problem returns 503.
3. Submit one clearly marked test quote using an inbox you control. Confirm a reference is shown, the row appears in Supabase's `quote_requests` table, and the admin/customer emails arrive.
4. Visit `/admin/login`, sign in, and confirm the request is listed. Test search, status filters, pagination, request details, status updates, and logout.
5. If email is unconfigured or rejected, the API response and confirmation dialog must say so; it must not say the emails were sent.
6. Check that `/server.py`, `/.env`, `/.env.example`, `/requirements.txt`, `/README.md`, and `/alipen_quotes.db` return 404.
7. Delete the test quote from Supabase after validation if it is no longer needed.

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
- **Admin login says it is not configured:** confirm both `ADMIN_USERNAME` and a valid Argon2id `ADMIN_PASSWORD_HASH` are set in Render, then redeploy/restart.
- **Admin login fails:** recreate the Argon2id hash using the command above, update the Render value without surrounding quotes, and check that the username matches exactly.
- **Admin pages show unavailable quote data:** verify the same Supabase PostgreSQL connection and `quote_requests` table used by public quote submissions.
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

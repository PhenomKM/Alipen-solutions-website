# Alipen Solutions Agency Ltd Website

Static multi-page catalogue and Python backend for quote requests, using PostgreSQL and Resend.

## Run locally

1. Create and activate a virtual environment, then run `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL`. Add Resend/admin email values to enable notifications.
3. Run `python server.py`.
4. Open `http://localhost:3000`.

The server creates the PostgreSQL quote table automatically. See [BACKEND_SETUP.md](BACKEND_SETUP.md) for production deployment and environment variable details.

## Project layout

- `*.html`, `styles.css`, `app.js`, `products.js`, `script.js`: website pages, styling, and browser logic.
- `public/images/`: images served by the website.
- `brand-assets/`: original design and product source images.
- `server.py`: local and production HTTP server plus quote API.
- `requirements.txt`: psycopg PostgreSQL driver with its binary distribution.

Keep `.env`, database files, and Python cache files out of version control; `.gitignore` covers them. See [DEPLOYMENT_README.md](DEPLOYMENT_README.md) for the complete deployment guide and free-tier limitations.

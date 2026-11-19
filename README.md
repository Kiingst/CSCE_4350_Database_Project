# Auto Parts — Phase III 

## Quick start (Linux / WSL, Python 3.10+)

```bash
cd /home/kiingst/CSCE_4350_Database_Project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
```


### MySQL 8.4 through Docker

Start Docker Desktop (with WSL integration enabled) or Docker Engine first.

```bash
docker compose up -d --wait
export DATABASE_URL='mysql+mysqlconnector://autoparts:local-demo-only@127.0.0.1:3307/autoparts'
python init_db.py
python app.py
```

Open http://localhost:5001. Stop the app with Ctrl+C. `docker compose stop` preserves database data. Initializing is a one-time operation; subsequent launches need only the environment variable and `python app.py`.

## Demo accounts

Every demo account uses DemoPass123! 

| Account type | Username | Scope |
| --- | --- | --- |
| Customer | lluthor | Lex Luthor; prefers Main Street |
| Customer | ckent | Clark Kent; prefers Northside |
| Employee / Clerk | bwayne | Main Street |
| Employee / Manager | tdrake | Main Street; authorized all-store reporting |
| Employee / Clerk | ballen | Northside |


## Database initialization / reset

`init_db.py` creates the selected database if needed, refuses to initialize when any table already exists, and loads `APschema.sql`, `APsample_data.sql`, then `01_mvp_extensions.sql`. It ignores the original schema's database-level DROP/CREATE/USE statements. MySQL DDL is not transactional: if initialization fails midway, select a fresh database or explicitly recreate the dedicated failed demo database before retrying.

For an existing database containing the original nine tables and sample data, back it up, apply **only** `sql/01_mvp_extensions.sql` once, and replace placeholder password hashes using `operations.password_hash` through an administrative script. The initializer is the supported reproducible path for a fresh demo.

To reset a disposable `autoparts` database deliberately, stop the app, explicitly drop only that named database with your database admin tools, and run the initializer again. Never run the original `APschema.sql` directly against data you need: it contains `DROP DATABASE`.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | FastHTML routes, template context, sessions and CSRF |
| `templates/` | Dedicated Jinja2 HTML screens plus shared layout and form/table macros |
| `static/style.css` | Shared screen styling, served at `/static/style.css` |
| `operations.py` | Validation, authorization and transactional business operations |
| `db.py` | SQLAlchemy engine and bound-query helpers |
| `init_db.py` | Explicit fresh-demo initialization and password replacement |
| `sql/` | Original schema/data/queries and local database account setup |
| `requirements-lock.txt` | Exact Python dependency versions used in verification |

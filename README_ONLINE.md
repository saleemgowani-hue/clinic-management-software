# SN Clinic Management System — Online (PostgreSQL) Edition

This is the same application as the Offline edition — same `app.py`, same
features, same UI — running against **PostgreSQL** instead of SQLite, so
it can be deployed to the cloud and used by multiple clinics at once.

## What's different from Offline

| | Offline | Online |
|---|---|---|
| Database | SQLite (`clinic.db`, a local file) | PostgreSQL (cloud-hosted) |
| Where it runs | Your computer | A server / cloud host |
| Internet required | No | Yes |
| Setup | Double-click a launcher | Set `DATABASE_URL`, deploy |

Everything else — the modules, the license system, the multi-tenant
model, the PDF prescriptions/receipts, WhatsApp links — is identical,
because it's literally the same `app.py`. A thin compatibility layer
(`db_postgres.py`) is what makes the same code work against either
database; see "How this works" below if you're curious.

## 1. Set up a PostgreSQL database

Any PostgreSQL 13 or newer works. Pick one:
- **Managed/free-tier options**: Supabase, Neon, Railway, Render, ElephantSQL
- **Your own server**: `apt install postgresql` (Ubuntu/Debian) or your
  distro's equivalent

Whichever you choose, you'll end up with a connection string that looks
like:
```
postgresql://username:password@host:5432/dbname
```

## 2. Configure the connection

Copy `.env.example` to `.streamlit/secrets.toml` and fill in your real
`DATABASE_URL`:
```toml
DATABASE_URL = "postgresql://username:password@host:5432/dbname"
```
(Or set `DATABASE_URL` as a plain environment variable on your server —
either is checked automatically. Environment variable takes priority if
both are set.)

**Never commit `secrets.toml` or a real `.env` file to git.**

## 3. Install dependencies

```bash
pip install -r requirements-online.txt
```
This is the same as the offline `requirements.txt` plus `psycopg2-binary`
(the PostgreSQL driver).

## 4. Run it

```bash
streamlit run app.py
```
On first run, the app automatically creates every table, the default
Super Admin account (`admin` / `admin123` — **change this password
immediately**), and the 50 pre-issued license keys, directly on your
PostgreSQL database. No separate migration command needed for a brand
new deployment — this happens the same way `clinic.db` gets created
automatically offline.

For real deployment, put this behind HTTPS (via your host's built-in
TLS, a reverse proxy, or a platform like Streamlit Community Cloud /
Render / Railway that provides it for you) — never serve patient data
over plain HTTP.

## 5. Moving an existing Offline clinic online

If a clinic has been using the Offline version and wants to switch to
Online, use the included migration script **once**:

```bash
export DATABASE_URL="postgresql://username:password@host:5432/dbname"
python migrate_to_online.py /path/to/their/clinic.db
```

This copies every patient, appointment, consultation, fee, medicine,
staff record, etc. into the Online database, correctly relinking all the
internal relationships (a patient's appointments still point to that
same patient, etc.) — verified with zero broken links in testing. It's
safe to run more than once: anything already present is skipped, nothing
is duplicated. Their original `clinic.db` file is never modified.

After migrating, log into the Online app and spot-check that the data
looks right before the clinic switches to using it day-to-day.

## Known limitations — please read before relying on this for production

This Online edition gives you a **real, tested PostgreSQL backend** for
the exact same application — that part is solid. But two things from a
"complete SaaS platform" wishlist are **intentionally not included**,
and you should know why:

**No continuous automatic sync between Offline and Online.**
The `migrate_to_online.py` script is a **one-time, one-direction** copy
you run manually when a clinic is ready to switch. It is not a live
sync engine — after it runs, the two databases are independent again.
Building real bidirectional sync (so a clinic could use Offline and
Online interchangeably, day to day, with changes flowing both ways
automatically) means solving conflict detection, retry logic, and
partial-failure recovery correctly — get any of that wrong and a clinic
can lose or duplicate real patient/billing data. That's a substantial,
multi-week engineering effort in its own right, not something to bolt
on quickly. If you need this, budget for it as a dedicated follow-on
project, ideally with a real staging environment and load testing before
any paying clinic depends on it.

**No formal load/scale testing.** The Postgres backend has been verified
correct (every module, every query pattern, real foreign-key integrity
after migration) but not load-tested with many concurrent tenants or
large data volumes. Fine for an early-stage rollout; worth a proper load
test pass before scaling to many paying clinics at once.

## How this works (for developers extending this further)

The existing `app.py`/`database.py`/`demo_data.py`/`licensing.py` code
was written for SQLite and uses `conn.execute("... ? ...", params)`,
`row["col"]` access, and `cur.lastrowid` throughout — none of which
PostgreSQL's driver (`psycopg2`) supports natively in that exact form.
Rather than rewrite every one of those ~165 call sites (error-prone, and
would make the two versions diverge over time), `db_postgres.py` provides
a thin connection/cursor wrapper that:

- Translates `?` placeholders to `%s` (and safely escapes any *other*
  literal `%` in a query, e.g. from `LIKE '%text%'`, which would
  otherwise collide with PostgreSQL's placeholder syntax)
- Auto-quotes the bare word `user` (a reserved keyword in PostgreSQL,
  but not in SQLite, and used unquoted throughout the existing code)
- Emulates `cur.lastrowid` via an automatic `RETURNING id` on INSERTs
- Returns rows that support both `row["col"]` and `row[0]` access,
  matching `sqlite3.Row`'s behavior
- Defines a `STRFTIME()` SQL function on the Postgres side (used by the
  Reports module, which is SQLite syntax with no native Postgres
  equivalent)

`database.py::get_db()` picks SQLite or this Postgres wrapper based on
whether `DATABASE_URL` is set — the rest of the application has no idea
which backend it's talking to. This is also why `db_postgres.py` and
`migrate_to_online.py` aren't included in the Offline ZIP: they depend
on `psycopg2`, which isn't needed there.

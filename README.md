# Magazine Subscriber Accounts (web)

Fortnightly magazine · 250 Taka / year · Financial year July–June.
Python + Flask + SQLite. No separate database server is needed: all data is in one file, `subscribers.db`.

## 1. First-time setup (VS Code, Windows)

1. Install **Python 3.11 or newer** from python.org (tick "Add Python to PATH").
2. Unzip this folder, then in VS Code: **File → Open Folder** → select it.
3. Open the terminal (**Terminal → New Terminal**) and run:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(Mac/Linux: `source .venv/bin/activate`.)
In VS Code choose the interpreter: **Ctrl+Shift+P → Python: Select Interpreter → .venv**.

4. Create your login (it asks for a password):

```
set FLASK_APP=app
flask create-user admin
```

(Mac/Linux: `export FLASK_APP=app`.)

5. Start:

```
python run.py
```

Open **http://localhost:8000** and sign in.

## 2. Importing from the old Access file

The package already includes `subscribers.db` with your Access data imported.
To import again from a newer `.mdb` (this wipes the current data!):

```
flask import-access "The_Ahmadi.mdb" --force
```

Rows that could not be imported are written to `import_orphan_payments.csv`
(payments with no matching subscriber) and `import_bad_rows.csv` (empty rows).

## 3. Daily use

* **Subscribers → + New**: add person (Jamaat can be picked or typed new), then record the first payment.
* **+ Payment** on any subscriber: enter date, amount, receipt/book no. The "valid until" date is
  filled automatically (250 Taka = 12 months; if still running, it is added after the current expiry). You can overwrite it.
* **Jamaat-wise**: subscriber list grouped by Jamaat with expiry; filter Current / Expired / Inactive; Excel + Print.
* **Expiry**: who expires between two dates, or who has already expired; "+ Renew" button.
* **Yearly (Jul–Jun)**: month-wise collection, Jamaat-wise collection, all payments, history of all years; Excel download.
* Subscriber page: full payment history grouped by financial year, printable.

Status meaning: **Valid** = active and latest expiry is today or later · **Expired** · **No payment** · **Inactive** (Active unticked).

## 4. Before using it for real

* Set a secret key: `set SECRET_KEY=any-long-random-text` before `python run.py`.
* **Back up** `subscribers.db` regularly (just copy the file).
* If put on the internet, use HTTPS (e.g. behind Nginx/Caddy or a host such as PythonAnywhere/Render).

## Files

| File | Purpose |
|---|---|
| `app.py` | pages, reports, login |
| `db.py` | database tables |
| `import_access.py` | Access → SQLite importer |
| `templates/` | HTML pages |
| `run.py` | start server |

"""Online start-up (Render):  python start.py
1. waits until the PostgreSQL database accepts connections (it may still be starting),
2. creates / upgrades the tables and the first admin,
3. starts the web server on the port Render gives us.
"""
import os
import sys
import time

import db
from app import app, ensure_admin


def prepare(tries=30):
    for i in range(1, tries + 1):
        try:
            db.init_db()
            ensure_admin()
            print("Database ready.", flush=True)
            return
        except Exception as e:                      # database not reachable yet
            print(f"Waiting for the database ({i}/{tries}): {e}", flush=True)
            time.sleep(5)
    sys.exit("The database could not be reached - check DATABASE_URL in the Render environment settings.")


if __name__ == "__main__":
    prepare()
    from waitress import serve
    port = int(os.environ.get("PORT", 10000))
    print(f"Serving on port {port}", flush=True)
    serve(app, host="0.0.0.0", port=port)

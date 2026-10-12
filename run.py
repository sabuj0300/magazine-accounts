"""Start the web server:  python run.py
Open http://localhost:8000 in the browser.
To let other computers on the office network use it, they open http://<this-PC-IP>:8000
"""
import os

from waitress import serve

import db
from app import app

if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 8000))
    print(f"Running on http://localhost:{port}  (Ctrl+C to stop)")
    serve(app, host="0.0.0.0", port=port)

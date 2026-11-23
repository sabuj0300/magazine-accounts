"""Backup of the whole database to the user's Google Drive (and as a download).

What a backup is: ONE zip file  magazine_backup_YYYY-MM-DD_HHMMSS.zip  holding
    subscribers.db                  - a complete, restorable database file (desktop program -> "Restore", or
                                      flask migrate-sqlite)
    subscribers_and_payments.xlsx   - all subscribers and all payments, readable in Excel
It works with SQLite (office PC) and PostgreSQL (Render).

Google Drive is used with a one-time authorisation (OAuth refresh token, see GOOGLE_DRIVE_BACKUP.md). The program
can only see the files and the folder it created itself (scope drive.file) - nothing else in the Drive.

Settings (environment variables, on Render: Environment tab):
    GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN     required for Google Drive
    GDRIVE_FOLDER_NAME   (default "Magazine Accounts Backups")
    BACKUP_HOUR          (default 2)   a backup is made every day after this hour, Bangladesh time
    BACKUP_KEEP          (default 60)  how many backup files stay in the Drive folder
"""
import io
import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import db

TOKEN_URL = os.environ.get("GDRIVE_TOKEN_URL", "https://oauth2.googleapis.com/token")
API_URL = os.environ.get("GDRIVE_API_URL", "https://www.googleapis.com/drive/v3")
UPLOAD_URL = os.environ.get("GDRIVE_UPLOAD_URL", "https://www.googleapis.com/upload/drive/v3")
FILE_PREFIX = "magazine_backup_"
FOLDER_MIME = "application/vnd.google-apps.folder"


def settings():
    return dict(
        client_id=os.environ.get("GDRIVE_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("GDRIVE_CLIENT_SECRET", "").strip(),
        refresh_token=os.environ.get("GDRIVE_REFRESH_TOKEN", "").strip(),
        folder=os.environ.get("GDRIVE_FOLDER_NAME", "").strip() or "Magazine Accounts Backups",
        hour=int(os.environ.get("BACKUP_HOUR", "2") or 2),
        keep=int(os.environ.get("BACKUP_KEEP", "60") or 60),
    )


def configured():
    s = settings()
    return bool(s["client_id"] and s["client_secret"] and s["refresh_token"])


def now_bd():
    return datetime.now(timezone(timedelta(hours=6))).replace(tzinfo=None)


# ------------------------------------------------------------------ building the backup file
def _vals(row):
    return list(row.values()) if hasattr(row, "values") else list(row)


TABLES = [("jamaats", "id,name"),
          ("users", "id,username,password_hash,role,jamaat_id"),
          ("subscribers", "id,local_id,name,father_name,jamaat_id,address,mobile,email,by_hand,active,notes,created_at"),
          ("payments", "id,subscriber_id,receipt_no,book_no,paid_date,amount,expiry_date,note,created_at")]


def copy_to_sqlite(src, path):
    """Copy every table of the open connection `src` (SQLite or PostgreSQL) into a new SQLite file."""
    db.init_db(path)
    dst = db.connect(path)
    counts = {}
    for table, cols in TABLES:
        rows = [_vals(r) for r in src.execute(f"SELECT {cols} FROM {table} ORDER BY id").fetchall()]
        if rows:
            dst.executemany(f"INSERT INTO {table}({cols}) VALUES ({','.join('?' * len(rows[0]))})", rows)
        counts[table] = len(rows)
    dst.commit()
    dst.close()
    return counts


def _excel_bytes(src):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Subscribers"
    ws.append(["ID", "Local ID", "Name", "Father's name", "Jama'at", "Address", "Mobile", "E-mail", "Delivery",
               "Status", "Expiry date", "Total paid", "Payments"])
    for r in src.execute("""SELECT id, local_id, name, father_name, jamaat, address, mobile, email, by_hand, status,
                                   expiry, total_paid, payment_count FROM v_subscribers
                            ORDER BY (jamaat IS NULL), lower(jamaat), lower(name), id""").fetchall():
        v = _vals(r)
        v[8] = "By hand" if v[8] else "Post"
        ws.append(v)
    wp = wb.create_sheet("Payments")
    wp.append(["Payment ID", "Subscriber ID", "Local ID", "Name", "Jama'at", "Receipt No", "Book No", "Payment date",
               "Amount", "Valid until", "Note"])
    for r in src.execute("""SELECT p.id, p.subscriber_id, s.local_id, s.name, COALESCE(j.name,''), p.receipt_no,
                                   p.book_no, p.paid_date, p.amount, p.expiry_date, p.note
                            FROM payments p JOIN subscribers s ON s.id = p.subscriber_id
                            LEFT JOIN jamaats j ON j.id = s.jamaat_id ORDER BY p.paid_date, p.id""").fetchall():
        wp.append(_vals(r))
    for sheet in (ws, wp):
        for c in sheet[1]:
            c.font = Font(bold=True)
        sheet.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_zip():
    """Returns (zip_bytes, file_name, counts)."""
    src = db.connect()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "subscribers.db")
            counts = copy_to_sqlite(src, path)
            xlsx = _excel_bytes(src)
            with open(path, "rb") as f:
                dbbytes = f.read()
    finally:
        src.close()
    name = f"{FILE_PREFIX}{now_bd():%Y-%m-%d_%H%M%S}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("subscribers.db", dbbytes)
        z.writestr("subscribers_and_payments.xlsx", xlsx)
        z.writestr("README.txt", f"Magazine Accounts backup made {now_bd():%Y-%m-%d %H:%M} (Bangladesh time).\n"
                   f"Rows: {counts}\nsubscribers.db = restorable database; the .xlsx is for reading in Excel.\n")
    return buf.getvalue(), name, counts


# ------------------------------------------------------------------ Google Drive
class DriveError(Exception):
    pass


def _http(method, url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise DriveError(f"Google answered {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise DriveError(f"Cannot reach Google: {e.reason}") from None
    return json.loads(body) if body else {}


def _access_token(s):
    body = urllib.parse.urlencode({"client_id": s["client_id"], "client_secret": s["client_secret"],
                                   "refresh_token": s["refresh_token"], "grant_type": "refresh_token"}).encode()
    out = _http("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if "access_token" not in out:
        raise DriveError("Google did not give an access token - the refresh token may be wrong or expired.")
    return out["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _find_or_create_folder(token, name):
    q = f"mimeType='{FOLDER_MIME}' and name='{name.replace(chr(39), chr(92) + chr(39))}' and trashed=false"
    url = f"{API_URL}/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id,name)", "spaces": "drive"})
    found = _http("GET", url, _auth(token)).get("files", [])
    if found:
        return found[0]["id"]
    meta = json.dumps({"name": name, "mimeType": FOLDER_MIME}).encode()
    return _http("POST", f"{API_URL}/files?fields=id", {**_auth(token), "Content-Type": "application/json"}, meta)["id"]


def _upload(token, folder_id, name, data):
    boundary = uuid.uuid4().hex
    meta = json.dumps({"name": name, "parents": [folder_id]}).encode()
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta +
            f"\r\n--{boundary}\r\nContent-Type: application/zip\r\n\r\n".encode() + data +
            f"\r\n--{boundary}--".encode())
    headers = {**_auth(token), "Content-Type": f"multipart/related; boundary={boundary}"}
    return _http("POST", f"{UPLOAD_URL}/files?uploadType=multipart&fields=id,name", headers, body)


def _prune(token, folder_id, keep):
    q = f"'{folder_id}' in parents and trashed=false"
    url = f"{API_URL}/files?" + urllib.parse.urlencode(
        {"q": q, "orderBy": "createdTime desc", "pageSize": 1000, "fields": "files(id,name)"})
    files = [f for f in _http("GET", url, _auth(token)).get("files", []) if f["name"].startswith(FILE_PREFIX)]
    removed = 0
    for f in files[keep:]:
        _http("DELETE", f"{API_URL}/files/{f['id']}", _auth(token))
        removed += 1
    return removed


def upload_to_drive(data, name):
    s = settings()
    token = _access_token(s)
    folder = _find_or_create_folder(token, s["folder"])
    _upload(token, folder, name, data)
    return _prune(token, folder, s["keep"]) if s["keep"] > 0 else 0


# ------------------------------------------------------------------ status + running
def get_meta(key):
    con = db.connect()
    try:
        r = con.execute("SELECT v FROM app_meta WHERE k=?", (key,)).fetchone()
        return r["v"] if r else None
    finally:
        con.close()


def set_meta(**items):
    con = db.connect()
    try:
        for k, v in items.items():
            con.execute("INSERT INTO app_meta(k,v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
        con.commit()
    finally:
        con.close()


def status():
    return {"configured": configured(), "folder": settings()["folder"], "hour": settings()["hour"],
            "keep": settings()["keep"], "last_ok": get_meta("last_backup_at"),
            "last_result": get_meta("last_backup_result"), "last_attempt": get_meta("last_attempt_at")}


_lock = threading.Lock()


def run_backup():
    """Make a backup now and send it to Google Drive. Returns (ok, message)."""
    if not _lock.acquire(blocking=False):
        return False, "A backup is already running."
    stamp = f"{now_bd():%Y-%m-%d %H:%M:%S}"
    try:
        try:
            set_meta(last_attempt_at=stamp)
            if not configured():
                raise DriveError("Google Drive is not set up yet (GDRIVE_* settings are missing).")
            data, name, counts = build_zip()
            removed = upload_to_drive(data, name)
            msg = (f"OK - {name} ({len(data) // 1024} KB) saved to Google Drive folder \"{settings()['folder']}\"; "
                   f"{counts['subscribers']} subscribers, {counts['payments']} payments."
                   + (f" {removed} old backup(s) removed." if removed else ""))
            set_meta(last_backup_at=stamp, last_backup_result=msg)
            return True, msg
        except Exception as e:                       # never let a backup problem stop the site
            msg = f"FAILED - {e}"
            try:
                set_meta(last_backup_result=msg)
            except Exception:
                pass
            return False, msg
    finally:
        _lock.release()


_done_day = None      # remembered in memory so that a finished day costs no database query (lets Neon sleep)


def due():
    global _done_day
    if not configured():
        return False
    n = now_bd()
    if n.hour < settings()["hour"] or _done_day == f"{n:%Y-%m-%d}":
        return False
    last = get_meta("last_backup_at")
    if last and last[:10] == f"{n:%Y-%m-%d}":
        _done_day = last[:10]
        return False
    tried = get_meta("last_attempt_at")
    if tried:
        try:
            if (n - datetime.strptime(tried, "%Y-%m-%d %H:%M:%S")).total_seconds() < 3600:   # retry hourly at most
                return False
        except ValueError:
            pass
    return True


_last_tick = 0.0


def tick():
    """Called often (every request and by the timer); starts the daily backup in the background when it is due."""
    global _last_tick
    if time.time() - _last_tick < 600 or not configured():
        return
    _last_tick = time.time()

    def work():
        try:
            if due():
                run_backup()
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


def start_scheduler():
    def loop():
        time.sleep(60)
        while True:
            try:
                if due():
                    run_backup()
            except Exception:
                pass
            time.sleep(600)
    threading.Thread(target=loop, daemon=True).start()

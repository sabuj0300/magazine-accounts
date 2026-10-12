"""Import The_Ahmadi.mdb (MS Access) into the new SQLite database.

Usage:  flask --app app import-access path/to/The_Ahmadi.mdb [--force]
Pure Python (access-parser) - no Access driver or Windows needed.
"""
import csv
import os
from datetime import datetime

from access_parser import AccessParser

import db


def _num(v):
    if v in (None, ""):
        return 0.0
    return float(str(v).replace(",", "").strip() or 0)


def _date(v):
    if not v:
        return None
    s = str(v)[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def _txt(v):
    if v is None:
        return None
    v = " ".join(str(v).replace("\r", " ").replace("\n", ", ").split())
    return v or None


def _rows(table):
    cols = list(table.keys())
    n = len(table[cols[0]]) if cols else 0
    for i in range(n):
        yield {c: table[c][i] for c in cols}


def run(mdb_path, force=False, report_dir="."):
    db.init_db()
    con = db.connect()
    if con.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0] and not force:
        raise SystemExit("Database already has subscribers. Use --force to wipe and re-import.")
    keep_links = {}
    if force:
        # remember which Jama'at each local user belongs to, so it can be re-linked after the import
        for r in con.execute("""SELECT u.id, j.name FROM users u JOIN jamaats j ON j.id = u.jamaat_id"""):
            keep_links[r["id"]] = r["name"]
        con.execute("UPDATE users SET jamaat_id = NULL")
        con.execute("DELETE FROM payments")
        con.execute("DELETE FROM subscribers")
        con.execute("DELETE FROM jamaats")

    mdb = AccessParser(mdb_path)
    subs = list(_rows(mdb.parse_table("Identi")))
    pays = list(_rows(mdb.parse_table("Chanda Status")))
    jams = list(_rows(mdb.parse_table("Jamaat Name")))

    names = {_txt(r["Jamaat"]) for r in jams if _txt(r["Jamaat"])}
    names |= {_txt(r["Jamaat"]) for r in subs if _txt(r["Jamaat"])}
    for n in sorted(names):
        con.execute("INSERT INTO jamaats(name) VALUES (?)", (n,))
    jid = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM jamaats")}
    for uid, jname in keep_links.items():
        if jname in jid:
            con.execute("UPDATE users SET jamaat_id=? WHERE id=?", (jid[jname], uid))

    ids = set()
    for r in subs:
        sid = int(r["ID NO"])
        ids.add(sid)
        con.execute(
            """INSERT INTO subscribers(id,name,father_name,jamaat_id,address,mobile,email,by_hand,active)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (sid, _txt(r["Sub Name"]) or "(no name)", _txt(r["Father Name"]),
             jid.get(_txt(r["Jamaat"])), _txt(r["Adress"]), _txt(r["Mobile No"]),
             _txt(r["E-mail"]), 1 if r["By Hand?"] else 0, 1 if r["Active"] else 0),
        )

    orphans, bad = [], []
    ok = 0
    for r in pays:
        sid = r["ID No"]
        paid = _date(r["Date"]) or _date(r["Rec Date"])
        exp = _date(r["Expier Date"])
        row = [sid, r["Reciet No"], r["Date"], r["Recieved Fee"], r["Expier Date"]]
        if sid is None or int(sid) not in ids:
            orphans.append(row)
            continue
        if not paid or not exp:
            bad.append(row)
            continue
        con.execute(
            """INSERT INTO payments(subscriber_id,receipt_no,book_no,paid_date,amount,expiry_date)
               VALUES (?,?,?,?,?,?)""",
            (int(sid), _txt(r["Reciet No"]), _txt(r["Book No"]), paid, _num(r["Recieved Fee"]), exp),
        )
        ok += 1
    db.sync_sequences(con)
    con.commit()
    con.close()

    for fname, rows in (("import_orphan_payments.csv", orphans), ("import_bad_rows.csv", bad)):
        if rows:
            with open(os.path.join(report_dir, fname), "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["ID No", "Receipt No", "Date", "Received Fee", "Expiry Date"])
                w.writerows(rows)
    return dict(subscribers=len(subs), jamaats=len(names), payments=ok,
                orphan_payments=len(orphans), bad_rows=len(bad))

import sqlite3
from .config import DB_PATH


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS owners (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      vehicle_id TEXT NOT NULL,
      registration TEXT DEFAULT '',
      battery_pct REAL NOT NULL,
      personal_range_km REAL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS purchases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id INTEGER NOT NULL,
      plan TEXT NOT NULL,
      amount TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(owner_id) REFERENCES owners(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS route_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id INTEGER,
      source TEXT NOT NULL,
      destination TEXT NOT NULL,
      vehicle_id TEXT NOT NULL,
      distance_km REAL,
      duration_min REAL,
      decision TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(owner_id) REFERENCES owners(id) ON DELETE SET NULL
    );
    """)
    con.commit(); con.close()


def upsert_owner(data):
    con = connect()
    row = con.execute("SELECT id FROM owners WHERE lower(email)=lower(?)", (data["email"],)).fetchone()
    values = (data["owner_name"], data["vehicle_id"], data.get("registration", ""), data["battery_pct"], data.get("personal_range_km"))
    if row:
        con.execute("""UPDATE owners SET owner_name=?,vehicle_id=?,registration=?,battery_pct=?,personal_range_km=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", values + (row["id"],))
        oid = row["id"]
    else:
        cur = con.execute("INSERT INTO owners(owner_name,email,vehicle_id,registration,battery_pct,personal_range_km) VALUES(?,?,?,?,?,?)", (data["owner_name"], data["email"], *values[1:]))
        oid = cur.lastrowid
    con.commit(); result = dict(con.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone()); con.close(); return result


def get_owner(owner_id=None, email=None):
    con = connect()
    if owner_id is not None:
        row = con.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()
    else:
        row = con.execute("SELECT * FROM owners WHERE lower(email)=lower(?)", (email,)).fetchone()
    con.close(); return dict(row) if row else None


def add_purchase(data):
    con = connect(); cur = con.execute("INSERT INTO purchases(owner_id,plan,amount) VALUES(?,?,?)", (data["owner_id"], data["plan"], data["amount"]))
    con.commit(); row = dict(con.execute("SELECT * FROM purchases WHERE id=?", (cur.lastrowid,)).fetchone()); con.close(); return row


def add_route(data):
    con = connect(); con.execute("INSERT INTO route_history(owner_id,source,destination,vehicle_id,distance_km,duration_min,decision) VALUES(?,?,?,?,?,?,?)", (data.get("owner_id"),data["source"],data["destination"],data["vehicle_id"],data.get("distance_km"),data.get("duration_min"),data.get("decision"))); con.commit(); con.close()


def list_owners():
    con=connect(); rows=[dict(r) for r in con.execute("SELECT * FROM owners ORDER BY updated_at DESC")]; con.close(); return rows

def list_purchases():
    con=connect(); rows=[dict(r) for r in con.execute("SELECT p.*,o.owner_name,o.email FROM purchases p JOIN owners o ON o.id=p.owner_id ORDER BY p.created_at DESC")]; con.close(); return rows

def list_routes():
    con=connect(); rows=[dict(r) for r in con.execute("SELECT * FROM route_history ORDER BY created_at DESC LIMIT 500")]; con.close(); return rows

def delete_owner(owner_id):
    con=connect(); cur=con.execute("DELETE FROM owners WHERE id=?",(owner_id,)); con.commit(); con.close(); return cur.rowcount>0

def delete_purchase(purchase_id):
    con=connect(); cur=con.execute("DELETE FROM purchases WHERE id=?",(purchase_id,)); con.commit(); con.close(); return cur.rowcount>0

def clear_all():
    con=connect(); con.executescript("DELETE FROM purchases;DELETE FROM route_history;DELETE FROM owners;"); con.commit(); con.close()

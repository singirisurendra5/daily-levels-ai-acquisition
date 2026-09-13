import sqlite3
from pathlib import Path
import pandas as pd

SCHEMA = '''
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    platform TEXT,
    url TEXT,
    text TEXT,
    date TEXT,
    source TEXT,
    ingested_at TEXT,
    intent_score INTEGER,
    customer_fit_score INTEGER,
    category TEXT,
    market TEXT,
    problem TEXT,
    recommended_action TEXT,
    status TEXT DEFAULT 'New',
    first_seen_at TEXT,
    last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT,
    source_type TEXT,
    source_name TEXT,
    rows_fetched INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    signal_id TEXT,
    event TEXT,
    platform TEXT,
    market TEXT,
    problem TEXT,
    content_type TEXT,
    notes TEXT
);
'''

class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._conn() as con:
            con.executescript(SCHEMA)

    def upsert_signals(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        new_count = 0
        with self._conn() as con:
            for _, r in df.iterrows():
                sid = str(r.get('signal_id',''))
                exists = con.execute('SELECT 1 FROM signals WHERE signal_id=?', (sid,)).fetchone()
                if exists:
                    con.execute('''UPDATE signals SET last_seen_at=?, ingested_at=?, text=?, date=?, source=?, intent_score=?, customer_fit_score=?, category=?, market=?, problem=?, recommended_action=? WHERE signal_id=?''',
                        (now, str(r.get('ingested_at', now)), str(r.get('text','')), str(r.get('date','')), str(r.get('source','')), int(r.get('intent_score',0)), int(r.get('customer_fit_score',0)), str(r.get('category','')), str(r.get('market','Unknown')), str(r.get('problem','')), str(r.get('recommended_action','')), sid))
                else:
                    con.execute('''INSERT INTO signals(signal_id,platform,url,text,date,source,ingested_at,intent_score,customer_fit_score,category,market,problem,recommended_action,status,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (sid,str(r.get('platform','')),str(r.get('url','')),str(r.get('text','')),str(r.get('date','')),str(r.get('source','')),str(r.get('ingested_at',now)),int(r.get('intent_score',0)),int(r.get('customer_fit_score',0)),str(r.get('category','')),str(r.get('market','Unknown')),str(r.get('problem','')),str(r.get('recommended_action','')),'New',now,now))
                    new_count += 1
        return new_count

    def signals(self) -> pd.DataFrame:
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM signals ORDER BY customer_fit_score DESC, intent_score DESC', con)

    def update_status(self, signal_id: str, status: str):
        with self._conn() as con:
            con.execute('UPDATE signals SET status=? WHERE signal_id=?', (status, signal_id))

    def log_run(self, source_type, source_name, rows, error=''):
        import datetime as dt
        with self._conn() as con:
            con.execute('INSERT INTO source_runs(run_at,source_type,source_name,rows_fetched,error) VALUES(?,?,?,?,?)', (dt.datetime.now(dt.timezone.utc).isoformat(),source_type,source_name,int(rows),str(error)))

    def runs(self):
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM source_runs ORDER BY id DESC LIMIT 50', con)

    def add_conversion(self, signal_id, event, platform='', market='', problem='', content_type='', notes=''):
        import datetime as dt
        with self._conn() as con:
            con.execute('INSERT INTO conversions(created_at,signal_id,event,platform,market,problem,content_type,notes) VALUES(?,?,?,?,?,?,?,?)', (dt.datetime.now(dt.timezone.utc).isoformat(),signal_id,event,platform,market,problem,content_type,notes))

    def conversions(self):
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM conversions ORDER BY id DESC', con)

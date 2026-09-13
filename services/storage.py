import sqlite3
from pathlib import Path
from datetime import datetime, timezone
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
    intent_score INTEGER DEFAULT 0,
    customer_fit_score INTEGER DEFAULT 0,
    category TEXT,
    market TEXT,
    problem TEXT,
    daily_levels_solution TEXT,
    recommended_action TEXT,
    matched_terms TEXT,
    signal_explanation TEXT,
    spam_probability REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
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
    new_rows INTEGER DEFAULT 0,
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
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._conn() as con:
            con.executescript(SCHEMA)
            existing = {r[1] for r in con.execute('PRAGMA table_info(signals)').fetchall()}
            additions = {
                'daily_levels_solution': 'TEXT', 'matched_terms': 'TEXT',
                'signal_explanation': 'TEXT', 'spam_probability': 'REAL DEFAULT 0',
                'confidence': 'REAL DEFAULT 0'
            }
            for col, typ in additions.items():
                if col not in existing:
                    con.execute(f'ALTER TABLE signals ADD COLUMN {col} {typ}')
            run_cols = {r[1] for r in con.execute('PRAGMA table_info(source_runs)').fetchall()}
            if 'new_rows' not in run_cols:
                con.execute('ALTER TABLE source_runs ADD COLUMN new_rows INTEGER DEFAULT 0')

    def upsert_signals(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        new_count = 0
        with self._conn() as con:
            for _, r in df.iterrows():
                sid = str(r.get('signal_id', '')).strip()
                if not sid:
                    continue
                values = (
                    str(r.get('platform','')), str(r.get('url','')), str(r.get('text','')),
                    str(r.get('date','')), str(r.get('source','')), str(r.get('ingested_at', now)),
                    int(r.get('intent_score',0)), int(r.get('customer_fit_score',0)), str(r.get('category','')),
                    str(r.get('market','Unknown')), str(r.get('problem','')),
                    str(r.get('daily_levels_solution','')), str(r.get('recommended_action','')),
                    str(r.get('matched_terms','')), str(r.get('signal_explanation','')),
                    float(r.get('spam_probability',0)), float(r.get('confidence',0))
                )
                exists = con.execute('SELECT 1 FROM signals WHERE signal_id=?', (sid,)).fetchone()
                if exists:
                    con.execute('''UPDATE signals SET platform=?, url=?, text=?, date=?, source=?, ingested_at=?,
                        intent_score=?, customer_fit_score=?, category=?, market=?, problem=?, daily_levels_solution=?,
                        recommended_action=?, matched_terms=?, signal_explanation=?, spam_probability=?, confidence=?, last_seen_at=?
                        WHERE signal_id=?''', values + (now, sid))
                else:
                    con.execute('''INSERT INTO signals(
                        platform,url,text,date,source,ingested_at,intent_score,customer_fit_score,category,market,problem,
                        daily_levels_solution,recommended_action,matched_terms,signal_explanation,spam_probability,confidence,
                        status,first_seen_at,last_seen_at,signal_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        values + ('New', now, now, sid))
                    new_count += 1
        return new_count

    def signals(self) -> pd.DataFrame:
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM signals ORDER BY customer_fit_score DESC, intent_score DESC, first_seen_at DESC', con)

    def update_status(self, signal_id: str, status: str):
        with self._conn() as con:
            con.execute('UPDATE signals SET status=? WHERE signal_id=?', (status, signal_id))

    def log_run(self, source_type, source_name, rows, new_rows=0, error=''):
        with self._conn() as con:
            con.execute('INSERT INTO source_runs(run_at,source_type,source_name,rows_fetched,new_rows,error) VALUES(?,?,?,?,?,?)',
                        (datetime.now(timezone.utc).isoformat(), source_type, source_name, int(rows), int(new_rows), str(error)))

    def runs(self):
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM source_runs ORDER BY id DESC LIMIT 100', con)

    def last_run_at(self):
        with self._conn() as con:
            row = con.execute('SELECT run_at FROM source_runs ORDER BY id DESC LIMIT 1').fetchone()
            return row[0] if row else None

    def add_conversion(self, signal_id, event, platform='', market='', problem='', content_type='', notes=''):
        with self._conn() as con:
            con.execute('INSERT INTO conversions(created_at,signal_id,event,platform,market,problem,content_type,notes) VALUES(?,?,?,?,?,?,?,?)',
                        (datetime.now(timezone.utc).isoformat(), signal_id, event, platform, market, problem, content_type, notes))

    def conversions(self):
        with self._conn() as con:
            return pd.read_sql_query('SELECT * FROM conversions ORDER BY id DESC', con)

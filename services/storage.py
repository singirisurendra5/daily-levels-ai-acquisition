import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

SCHEMA='''
CREATE TABLE IF NOT EXISTS signals (
 signal_id TEXT PRIMARY KEY, platform TEXT, url TEXT, text TEXT, date TEXT, source TEXT, ingested_at TEXT, interest_score INTEGER DEFAULT 0,
 intent_score INTEGER DEFAULT 0, customer_fit_score INTEGER DEFAULT 0, category TEXT, market TEXT, problem TEXT,
 daily_levels_solution TEXT, recommended_action TEXT, matched_terms TEXT, signal_explanation TEXT,
 spam_probability REAL DEFAULT 0, confidence REAL DEFAULT 0, signal_type TEXT DEFAULT 'User-intent signal',
 explicit_need INTEGER DEFAULT 0, quality_flags TEXT, status TEXT DEFAULT 'New', first_seen_at TEXT, last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS source_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, source_type TEXT, source_name TEXT, rows_fetched INTEGER, new_rows INTEGER DEFAULT 0, error TEXT);
CREATE TABLE IF NOT EXISTS conversions (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, signal_id TEXT, event TEXT, platform TEXT, market TEXT, problem TEXT, content_type TEXT, notes TEXT);
'''

class Store:
 def __init__(self,path):
  self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True); self._init()
 def _conn(self): return sqlite3.connect(self.path)
 def _init(self):
  with self._conn() as con:
   con.executescript(SCHEMA)
   existing={r[1] for r in con.execute('PRAGMA table_info(signals)')}
   additions={'interest_score':'INTEGER DEFAULT 0','daily_levels_solution':'TEXT','matched_terms':'TEXT','signal_explanation':'TEXT','spam_probability':'REAL DEFAULT 0','confidence':'REAL DEFAULT 0','signal_type':"TEXT DEFAULT 'User-intent signal'",'explicit_need':'INTEGER DEFAULT 0','quality_flags':'TEXT','relevance_score':'INTEGER DEFAULT 0','buying_intent_score':'INTEGER DEFAULT 0','product_fit_score':'INTEGER DEFAULT 0','priority_score':'INTEGER DEFAULT 0','competition_detected':'INTEGER DEFAULT 0','qualification_version':"TEXT DEFAULT 'legacy'",'sales_ready':'INTEGER DEFAULT 0','buyer_stage':"TEXT DEFAULT 'Not a lead'",'lead_reason':'TEXT','content_angle':'TEXT','unmet_need':'INTEGER DEFAULT 0','evidence_type':"TEXT DEFAULT 'Context-only'",'evidence_strength':"TEXT DEFAULT 'Weak'",'evidence_sentence':'TEXT'}
   for col,typ in additions.items():
    if col not in existing: con.execute(f'ALTER TABLE signals ADD COLUMN {col} {typ}')
 def upsert_signals(self,df):
  if df.empty:return 0
  now=datetime.now(timezone.utc).isoformat(); new=0
  cols=['platform','url','text','date','source','ingested_at','interest_score','intent_score','customer_fit_score','category','market','problem','daily_levels_solution','recommended_action','matched_terms','signal_explanation','spam_probability','confidence','signal_type','explicit_need','quality_flags','relevance_score','buying_intent_score','product_fit_score','priority_score','competition_detected','qualification_version','sales_ready','buyer_stage','lead_reason','content_angle','unmet_need','evidence_type','evidence_strength','evidence_sentence']
  def safe_text(v):
   return '' if pd.isna(v) else str(v)
  def safe_float(v,default=0):
   try:
    return default if pd.isna(v) else float(v)
   except Exception:return default
  with self._conn() as con:
   for _,r in df.iterrows():
    sid=safe_text(r.get('signal_id','')).strip()
    if not sid: continue
    vals=[safe_text(r.get(c,'')) for c in cols]
    for c in ['interest_score','intent_score','customer_fit_score','relevance_score','buying_intent_score','product_fit_score','priority_score']:
     vals[cols.index(c)]=int(safe_float(r.get(c,0)))
    vals[cols.index('spam_probability')]=safe_float(r.get('spam_probability',0))
    vals[cols.index('confidence')]=safe_float(r.get('confidence',0))
    vals[cols.index('explicit_need')]=int(bool(r.get('explicit_need',False)))
    vals[cols.index('competition_detected')]=int(bool(r.get('competition_detected',False)))
    vals[cols.index('quality_flags')] = safe_text(r.get('quality_flags',''))
    vals[cols.index('qualification_version')] = safe_text(r.get('qualification_version','3.6.4')) or '3.6.4'
    vals[cols.index('sales_ready')] = int(bool(r.get('sales_ready',False)))
    vals[cols.index('unmet_need')] = int(bool(r.get('unmet_need',False)))
    exists=con.execute('SELECT 1 FROM signals WHERE signal_id=?',(sid,)).fetchone()
    if exists:
     sets=','.join(f'{c}=?' for c in cols)
     con.execute(f'UPDATE signals SET {sets}, last_seen_at=? WHERE signal_id=?',vals+[now,sid])
    else:
     names=cols+['status','first_seen_at','last_seen_at','signal_id']; placeholders=','.join('?'*len(names))
     con.execute(f'INSERT INTO signals({",".join(names)}) VALUES({placeholders})',vals+['New',now,now,sid]); new+=1
  return new
 def signals(self):
  with self._conn() as con:return pd.read_sql_query('SELECT * FROM signals ORDER BY priority_score DESC,buying_intent_score DESC,product_fit_score DESC,first_seen_at DESC',con)
 def update_status(self,sid,status):
  with self._conn() as con:con.execute('UPDATE signals SET status=? WHERE signal_id=?',(status,sid))
 def log_run(self,source_type,source_name,rows,new_rows=0,error=''):
  with self._conn() as con:con.execute('INSERT INTO source_runs(run_at,source_type,source_name,rows_fetched,new_rows,error) VALUES(?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),source_type,source_name,int(rows),int(new_rows),str(error)))
 def runs(self):
  with self._conn() as con:return pd.read_sql_query('SELECT * FROM source_runs ORDER BY id DESC LIMIT 100',con)
 def add_conversion(self,*args):
  sid=''; event=''; platform=''; market=''; problem=''; content_type=''; notes=''
  if len(args)>=1:sid=args[0]
  if len(args)>=2:event=args[1]
  if len(args)>=3:platform=args[2]
  if len(args)>=4:market=args[3]
  if len(args)>=5:problem=args[4]
  if len(args)>=6:content_type=args[5]
  if len(args)>=7:notes=args[6]
  with self._conn() as con:con.execute('INSERT INTO conversions(created_at,signal_id,event,platform,market,problem,content_type,notes) VALUES(?,?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),sid,event,platform,market,problem,content_type,notes))
 def conversions(self):
  with self._conn() as con:return pd.read_sql_query('SELECT * FROM conversions ORDER BY id DESC',con)

import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from services.intelligence import analyze, signal_id, VERSION
from services.dedupe import deduplicate_signals
from services.ingestion import fetch_rss, fetch_reddit_rss, fetch_youtube_channel, combine_frames
from services.storage import Store

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / 'data' / 'sources.json'
RECOMMENDED_PATH = ROOT / 'data' / 'recommended_sources.json'
DB_PATH = ROOT / 'data' / 'daily_levels.db'
LANDING_PAGE = 'https://dailylevels-app.vercel.app/'

st.set_page_config(page_title='Daily Levels — Trader Finder', page_icon='📈', layout='wide')
st.title('Daily Levels — Automatic Trader Finder')
st.caption('V4.0 • Public trader discovery → market identification → landing-page opportunity')

store = Store(DB_PATH)


def clean(x): return '' if pd.isna(x) else str(x).strip()

def load_json(path, fallback):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return fallback.copy()

def save_sources(cfg):
    SOURCES_PATH.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

def enabled(item): return item.get('enabled', True) is not False

def configured_sources(cfg):
    result=[]
    for x in cfg.get('rss_feeds',[]):
        if enabled(x): result.append(('RSS',x))
    for x in cfg.get('reddit',[]):
        if enabled(x): result.append(('Reddit',x))
    for x in cfg.get('youtube_channels',[]):
        if enabled(x): result.append(('YouTube',x))
    return result

def source_label(kind,item):
    if kind=='RSS': return item.get('platform','RSS')
    if kind=='Reddit': return f"Reddit r/{item.get('subreddit','')} {item.get('query','')}".strip()
    return f"YouTube {item.get('channel_id','')[:18]}"

def fetch_one(kind,item):
    if kind=='RSS': return fetch_rss(item['url'], item.get('platform','RSS'))
    if kind=='Reddit': return fetch_reddit_rss(item['subreddit'], item.get('query',''), item.get('sort','new'), item.get('limit',25))
    return fetch_youtube_channel(item['channel_id'], item.get('limit',15))

def score_frame(raw):
    if raw.empty: return raw.copy()
    work=raw.copy()
    for c in ['platform','url','text']:
        if c not in work: work[c]=''
        work[c]=work[c].map(clean)
    for c in ['date','source']:
        if c not in work: work[c]=''
    work['ingested_at']=datetime.now(timezone.utc).isoformat()
    analysis=work['text'].apply(lambda x: pd.Series(analyze(x)))
    result=pd.concat([work.reset_index(drop=True),analysis.reset_index(drop=True)],axis=1)
    result['signal_id']=[signal_id(p,u,t) for p,u,t in zip(result.platform,result.url,result.text)]
    return result

def fetch_live():
    cfg=load_json(SOURCES_PATH, {})
    frames=[]
    for kind,item in configured_sources(cfg):
        name=source_label(kind,item)
        try:
            df=fetch_one(kind,item)
            frames.append(df)
            # Store run count now; new count is calculated after dedupe/upsert below.
            store.log_run(kind,name,len(df),0,'')
        except Exception as e:
            store.log_run(kind,name,0,0,str(e))
    if not frames: return pd.DataFrame()
    raw=combine_frames(frames)
    raw=deduplicate_signals(raw)
    scored=score_frame(raw)
    new_count=store.upsert_signals(scored)
    return scored

def current_signals():
    df=store.signals()
    return df if not df.empty else pd.DataFrame()

# Automatic acquisition: first page load fetches public sources once per browser session.
if 'v4_started' not in st.session_state:
    st.session_state.v4_started=True
    with st.spinner('Finding public traders automatically…'):
        try: fetch_live()
        except Exception as e: st.warning(f'Automatic scan had an issue: {e}')

if st.button('🔄 Scan public sources now', type='primary'):
    with st.spinner('Scanning public sources and identifying traders…'):
        fetch_live()
    st.rerun()

signals=current_signals()
if signals.empty:
    st.info('No public signals yet. Add permitted public sources in Source Manager below.')
else:
    # Backward-compatible fields: older V3/V4 SQLite databases may not have
    # the new simple trader-finder columns yet. Derive them safely instead of
    # crashing the dashboard.
    if 'interest_score' not in signals.columns:
        if 'priority_score' in signals.columns:
            signals['interest_score'] = pd.to_numeric(signals['priority_score'], errors='coerce').fillna(0).astype(int)
        elif 'intent_score' in signals.columns:
            signals['interest_score'] = pd.to_numeric(signals['intent_score'], errors='coerce').fillna(0).astype(int)
        else:
            signals['interest_score'] = 0
    if 'interest_level' not in signals.columns:
        signals['interest_level'] = signals['interest_score'].apply(lambda x: 'HIGH' if x >= 80 else ('MEDIUM' if x >= 50 else 'LOW'))
    for c in ['market','platform','evidence_type','evidence_sentence','reason','recommended_action','landing_page']:
        if c not in signals: signals[c]=''

    f1,f2,f3=st.columns(3)
    f_platform=f1.multiselect('Platform',sorted(signals.platform.dropna().unique()))
    f_market=f2.multiselect('Market',sorted(signals.market.dropna().unique()))
    f_level=f3.multiselect('Trader level',['HIGH','MEDIUM','LOW'])
    filtered=signals.copy()
    if f_platform: filtered=filtered[filtered.platform.isin(f_platform)]
    if f_market: filtered=filtered[filtered.market.isin(f_market)]
    if f_level: filtered=filtered[filtered.interest_level.isin(f_level)]

    c=st.columns(5)
    c[0].metric('Public signals',len(filtered))
    c[1].metric('HIGH traders',int((filtered.interest_level=='HIGH').sum()))
    c[2].metric('MEDIUM traders',int((filtered.interest_level=='MEDIUM').sum()))
    c[3].metric('LOW',int((filtered.interest_level=='LOW').sum()))
    c[4].metric('Landing-page opportunities',int(filtered.interest_level.isin(['HIGH','MEDIUM']).sum()))

    st.subheader('🎯 Traders to review and share the landing page with')
    opp=filtered[filtered.interest_level.isin(['HIGH','MEDIUM'])].copy()
    if opp.empty:
        st.info('No HIGH/MEDIUM public traders found in the current scan.')
    else:
        opp=opp.sort_values(['interest_score','date'],ascending=[False,False])
        display_cols=['platform','market','interest_level','interest_score','evidence_sentence','reason','recommended_action','url']
        st.dataframe(opp[display_cols],use_container_width=True,hide_index=True)

        options=list(opp.signal_id.astype(str))
        selected=st.selectbox('Select trader',options,format_func=lambda sid: str(opp.loc[opp.signal_id==sid,'platform'].iloc[0])+' • '+str(opp.loc[opp.signal_id==sid,'market'].iloc[0])+' • '+str(opp.loc[opp.signal_id==sid,'interest_level'].iloc[0]))
        row=opp[opp.signal_id==selected].iloc[0]
        st.markdown('### Trader signal')
        st.write(f"**Market:** {row.market}  •  **Level:** {row.interest_level}  •  **Score:** {row.interest_score}")
        if row.evidence_sentence: st.write(f"**Evidence:** {row.evidence_sentence}")
        st.write(f"**Why found:** {row.reason}")
        st.write(f"**Source:** {row.url}")
        st.success(f'Action: {row.recommended_action}')
        st.code(LANDING_PAGE,language=None)
        st.markdown(f'**Daily Levels landing page:** {LANDING_PAGE}')

    st.subheader('All public trader signals')
    cols=['platform','market','interest_level','interest_score','evidence_type','reason','url']
    st.dataframe(filtered[cols].sort_values('interest_score',ascending=False),use_container_width=True,hide_index=True)

st.subheader('⚙️ Public source manager')
cfg=load_json(SOURCES_PATH,{})
rec=load_json(RECOMMENDED_PATH,{})

# V4 should work automatically out of the box. If the user has not configured
# any sources yet, seed the recommended public feeds once. This does not send
# messages or access private data; it only enables the permitted public feeds.
if not configured_sources(cfg) and configured_sources(rec):
    cfg=rec
    save_sources(cfg)
    st.caption('Recommended public sources are enabled automatically for discovery.')

col1,col2=st.columns(2)
with col1:
    st.write('Enabled sources')
    rows=[]
    for kind,item in configured_sources(cfg):
        rows.append({'type':kind,'source':source_label(kind,item),'enabled':True})
    if rows:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.info('No enabled sources.')
with col2:
    if st.button('Load recommended public sources'):
        merged=load_json(RECOMMENDED_PATH,{})
        cfg=merged
        save_sources(cfg)
        st.success('Recommended public sources loaded. Click Scan public sources now.')

st.subheader('📊 Acquisition summary')
if not signals.empty:
    m=signals.groupby('market').agg(traders=('signal_id','count'),high=('interest_level',lambda s:int((s=='HIGH').sum())),medium=('interest_level',lambda s:int((s=='MEDIUM').sum()))).reset_index().sort_values(['high','medium'],ascending=False)
    st.dataframe(m,use_container_width=True,hide_index=True)
    st.download_button('Download trader opportunities CSV',signals.to_csv(index=False).encode('utf-8'),'daily_levels_trader_opportunities.csv','text/csv')

st.caption('Automatic discovery uses permitted public feeds only. Actual outreach remains a human/platform-compliant action; the app does not access private data or send unsolicited automated messages.')

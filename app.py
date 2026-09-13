import json
import re
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from services.intelligence import analyze, signal_id
from services.dedupe import deduplicate_signals
from services.ingestion import fetch_rss, fetch_reddit_rss, fetch_youtube_channel, combine_frames
from services.storage import Store

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / 'data' / 'sources.json'
RECOMMENDED_PATH = ROOT / 'data' / 'recommended_sources.json'
SAMPLE_PATH = ROOT / 'data' / 'sample_signals.csv'
DB_PATH = ROOT / 'data' / 'daily_levels.db'

st.set_page_config(page_title='Daily Levels — AI Customer Acquisition', page_icon='📈', layout='wide')
st.title('Daily Levels — AI Customer Acquisition')
st.caption('MVP V3.6.3 • Accuracy fix • True-need sales qualification • Public-signal acquisition • Human-in-the-loop')

store = Store(DB_PATH)

STATUS_OPTIONS = ['New','Reviewed','Content planned','Educational reply','Invited to learn','Converted','Do not contact']
EVENT_OPTIONS = ['Content published','Educational reply','Website visit','Signup','Trial/start','Purchase']

def clean(x):
    return '' if pd.isna(x) else str(x).strip()


def validate(df):
    missing = {'platform','url','text'} - set(df.columns)
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(sorted(missing)))


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return fallback.copy()


def save_sources(cfg):
    SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_PATH.write_text(json.dumps(cfg, indent=2), encoding='utf-8')


def source_key(item, kind):
    if kind == 'rss':
        return f"rss|{item.get('url','')}"
    if kind == 'reddit':
        return f"reddit|{item.get('subreddit','')}|{item.get('query','')}"
    return f"youtube|{item.get('channel_id','')}"


def enabled(item):
    return item.get('enabled', True) is not False


def score_frame(raw):
    if raw.empty:
        return raw.copy()
    work = raw.copy()
    for c in ['platform','url','text']:
        if c not in work:
            work[c] = ''
        work[c] = work[c].map(clean)
    if 'date' not in work:
        work['date'] = ''
    if 'source' not in work:
        work['source'] = ''
    if 'ingested_at' not in work:
        work['ingested_at'] = datetime.now(timezone.utc).isoformat()
    analysis = work['text'].apply(lambda x: pd.Series(analyze(x)))
    result = pd.concat([work.reset_index(drop=True), analysis.reset_index(drop=True)], axis=1)
    result['signal_id'] = [signal_id(p,u,t) for p,u,t in zip(result.platform,result.url,result.text)]
    return result


def requalify_stored_signals():
    existing = store.signals()
    if existing.empty:
        return 0
    base_cols = ['platform','url','text','date','source','ingested_at']
    refreshed = score_frame(existing[[c for c in base_cols if c in existing.columns]].copy())
    status_map = existing.set_index('signal_id')['status'].to_dict() if 'status' in existing.columns else {}
    refreshed['status'] = refreshed['signal_id'].map(status_map).fillna('New')
    return store.upsert_signals(refreshed)


def needs_requalification(df):
    return (not df.empty and ('qualification_version' not in df.columns or df.qualification_version.fillna('legacy').astype(str).ne('3.6.3').any()))


def fetch_one(kind, item):
    if kind == 'rss':
        return fetch_rss(item['url'], item.get('platform','RSS'))
    if kind == 'reddit':
        return fetch_reddit_rss(item['subreddit'], item.get('query',''), item.get('sort','new'), item.get('limit',25))
    return fetch_youtube_channel(item['channel_id'], item.get('limit',15))


def configured_sources(cfg):
    result = []
    for item in cfg.get('rss_feeds',[]):
        if enabled(item): result.append(('RSS', item))
    for item in cfg.get('reddit',[]):
        if enabled(item): result.append(('Reddit', item))
    for item in cfg.get('youtube_channels',[]):
        if enabled(item): result.append(('YouTube', item))
    return result


def source_label(kind, item):
    if kind == 'RSS': return item.get('platform','RSS')
    if kind == 'Reddit': return f"Reddit r/{item.get('subreddit','')} {item.get('query','')}".strip()
    return f"YouTube {item.get('channel_id','')[:18]}"


def run_configured_sources(cfg):
    frames, errors, run_meta = [], [], []
    existing = set(store.signals().signal_id.tolist())
    for kind, item in configured_sources(cfg):
        label = source_label(kind, item)
        try:
            df = fetch_one(kind.lower(), item)
            df = combine_frames([df])
            scored = score_frame(df)
            new_rows = int((~scored.signal_id.isin(existing)).sum()) if not scored.empty else 0
            if not scored.empty:
                store.upsert_signals(scored)
                existing.update(scored.signal_id.tolist())
            store.log_run(kind, label, len(df), new_rows, '')
            run_meta.append((kind, label, len(df), new_rows, 'OK'))
            frames.append(df)
        except Exception as e:
            msg = str(e)[:300]
            errors.append(f'{label}: {msg}')
            store.log_run(kind, label, 0, 0, msg)
            run_meta.append((kind, label, 0, 0, 'ERROR'))
    return combine_frames(frames), errors, run_meta


cfg = load_json(SOURCES_PATH, {'rss_feeds':[], 'reddit':[], 'youtube_channels':[]})
recommended = load_json(RECOMMENDED_PATH, {'rss_feeds':[], 'reddit':[], 'youtube_channels':[]})

# One-time migration: existing V3.5/older rows may still contain legacy HOT labels
# while the new qualification columns are zero/default. Re-score every stored row
# so the dashboard, queue, and detail view all use the same qualification engine.
existing_now = store.signals()
if needs_requalification(existing_now):
    requalify_stored_signals()
    existing_now = store.signals()

# On a fresh deployment, keep the app immediately usable: seed the recommended
# public sources in memory. The user still explicitly starts fetching.
if not any(cfg.get(k, []) for k in ['rss_feeds', 'reddit', 'youtube_channels']):
    cfg = {k: [dict(x) for x in recommended.get(k, [])] for k in ['rss_feeds', 'reddit', 'youtube_channels']}
    for k in cfg:
        for item in cfg[k]:
            item['enabled'] = True
    save_sources(cfg)

st.sidebar.header('Qualification')
if st.sidebar.button('Re-qualify all stored signals'):
    count = requalify_stored_signals()
    st.sidebar.success(f'Re-qualified {count} stored signals.')
    st.rerun()

with st.expander('⚙️ Source Manager', expanded=True):
    st.caption('Only add public sources you are permitted to access. The app does not message users or access private data.')
    actions = st.columns(3)
    with actions[0]:
        if st.button('✨ Reset to recommended public sources', use_container_width=True):
            for key in ['rss_feeds','reddit','youtube_channels']:
                existing_keys = {source_key(x, 'rss' if key=='rss_feeds' else 'reddit' if key=='reddit' else 'youtube') for x in cfg.get(key,[])}
                for item in recommended.get(key,[]):
                    kind = 'rss' if key=='rss_feeds' else 'reddit' if key=='reddit' else 'youtube'
                    if source_key(item, kind) not in existing_keys:
                        cfg.setdefault(key, []).append(item)
            save_sources(cfg)
            st.success('Recommended public sources loaded.')
            st.rerun()
    with actions[1]:
        if st.button('🧹 Remove all configured sources', use_container_width=True):
            save_sources({'rss_feeds':[], 'reddit':[], 'youtube_channels':[]})
            st.rerun()
    with actions[2]:
        if st.button('🚀 Start live acquisition', type='primary', use_container_width=True):
            if not configured_sources(cfg):
                st.error('No enabled public sources are configured. Use the reset button or add a permitted source.')
            else:
                with st.spinner('Fetching configured public sources…'):
                    _, errors, meta = run_configured_sources(cfg)
                st.session_state['last_errors'] = errors
                st.session_state['last_fetch'] = datetime.now(timezone.utc).isoformat()
                st.session_state['last_fetch_meta'] = meta
                st.rerun()

    tabs = st.tabs(['RSS / Atom','Reddit public feed','YouTube public feed'])
    with tabs[0]:
        for i, item in enumerate(cfg.get('rss_feeds',[])):
            c1,c2,c3,c4 = st.columns([1.7,4.3,1,1])
            c1.write(item.get('platform','RSS'))
            c2.write(item.get('url',''))
            enabled_now = c3.checkbox('On', value=enabled(item), key=f'rss_on_{i}')
            if enabled_now != enabled(item):
                cfg['rss_feeds'][i]['enabled'] = enabled_now; save_sources(cfg); st.rerun()
            if c4.button('Remove', key=f'rm_rss_{i}'):
                cfg['rss_feeds'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_rss'):
            a,b,c = st.columns([2,4,1]); platform=a.text_input('Platform'); url=b.text_input('Feed URL'); add=c.form_submit_button('Add')
            if add and platform.strip() and url.strip():
                cfg['rss_feeds'].append({'platform':platform.strip(),'url':url.strip(),'enabled':True}); save_sources(cfg); st.rerun()
    with tabs[1]:
        for i, item in enumerate(cfg.get('reddit',[])):
            c1,c2,c3,c4 = st.columns([1.4,2,2.5,1])
            c1.write('Reddit'); c2.write('r/'+item.get('subreddit','')); c3.write(item.get('query',''))
            if c4.button('Remove', key=f'rm_red_{i}'):
                cfg['reddit'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_reddit'):
            a,b,c,d = st.columns([1.2,2,1,1]); sub=a.text_input('Subreddit'); query=b.text_input('Search query'); limit=c.number_input('Limit',1,100,25); add=d.form_submit_button('Add')
            if add and sub.strip():
                cfg['reddit'].append({'subreddit':sub.strip(),'query':query.strip(),'sort':'new','limit':int(limit),'enabled':True}); save_sources(cfg); st.rerun()
    with tabs[2]:
        for i, item in enumerate(cfg.get('youtube_channels',[])):
            c1,c2,c3 = st.columns([4.5,1,1])
            c1.write(item.get('channel_id',''))
            enabled_now=c2.checkbox('On', value=enabled(item), key=f'yt_on_{i}')
            if enabled_now != enabled(item):
                cfg['youtube_channels'][i]['enabled']=enabled_now; save_sources(cfg); st.rerun()
            if c3.button('Remove', key=f'rm_yt_{i}'):
                cfg['youtube_channels'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_yt'):
            a,b,c=st.columns([4,1,1]); cid=a.text_input('YouTube Channel ID'); limit=b.number_input('Limit',1,50,15); add=c.form_submit_button('Add')
            if add and cid.strip():
                cfg['youtube_channels'].append({'channel_id':cid.strip(),'limit':int(limit),'enabled':True}); save_sources(cfg); st.rerun()

configured_total = sum(len(cfg.get(k,[])) for k in ['rss_feeds','reddit','youtube_channels'])
enabled_total = len(configured_sources(cfg))
metrics = st.columns(4)
runs_df = store.runs()
if not runs_df.empty:
    latest_run = runs_df.iloc[0]['run_at']
    latest_rows = runs_df[runs_df['run_at'] == latest_run]
    persistent_new = int(latest_rows['new_rows'].sum())
    persistent_last = str(latest_run)
else:
    persistent_new = sum(x[3] for x in st.session_state.get('last_fetch_meta', []))
    persistent_last = st.session_state.get('last_fetch')
metrics[0].metric('Configured sources', configured_total)
metrics[1].metric('Enabled sources', enabled_total)
metrics[2].metric('New on last fetch', persistent_new)
metrics[3].metric('Last fetch', (persistent_last or 'Not yet').replace('T',' ')[:19])

if st.session_state.get('last_errors'):
    with st.expander('Ingestion warnings'):
        for e in st.session_state['last_errors']:
            st.warning(e)

st.subheader('1. Signal sources')
mode = st.radio('Dataset mode', ['Live opportunities only','Live + uploaded CSV','Demo + live + uploaded CSV'], horizontal=True)
uploaded = st.file_uploader('Optional public-signal CSV', type=['csv'])
if uploaded:
    try:
        manual = pd.read_csv(uploaded); validate(manual); manual = score_frame(manual); dups,_ = deduplicate_signals(manual); store.upsert_signals(dups[~dups['is_duplicate']])
        st.success(f'Loaded {len(manual)} CSV signals.')
    except Exception as e:
        st.error(str(e)); st.stop()

live_results = store.signals()
try: sample = pd.read_csv(SAMPLE_PATH)
except Exception: sample = pd.DataFrame(columns=['platform','url','text','date'])
if mode.startswith('Demo'):
    demo = score_frame(sample); demo,_ = deduplicate_signals(demo)
    live_results = pd.concat([live_results, demo], ignore_index=True).drop_duplicates(subset=['signal_id'])

st.subheader('2. Normalize + duplicate detection')
runs = store.runs()
last_run = runs.iloc[0] if not runs.empty else None
st.caption(f'Persistent signals: {len(live_results)} • Configured sources: {configured_total} • Last run: {last_run.run_at if last_run is not None else "Not yet fetched"}')

st.sidebar.header('Opportunity filters')
platform_options=['All']+sorted(live_results.platform.dropna().unique().tolist()) if not live_results.empty else ['All']
market_options=['All']+sorted(live_results.market.dropna().unique().tolist()) if not live_results.empty else ['All']
problem_options=['All']+sorted(live_results.problem.dropna().unique().tolist()) if not live_results.empty else ['All']
status_options=['All']+STATUS_OPTIONS
platform=st.sidebar.selectbox('Platform',platform_options)
market=st.sidebar.selectbox('Market',market_options)
problem=st.sidebar.selectbox('Problem',problem_options)
status=st.sidebar.selectbox('Status',status_options)
min_score=st.sidebar.slider('Minimum intent',0,100,0)
min_fit=st.sidebar.slider('Minimum fit',0,100,0)
keyword=st.sidebar.text_input('Keyword contains','')

filtered=live_results.copy()
if not filtered.empty:
    if platform!='All': filtered=filtered[filtered.platform==platform]
    if market!='All': filtered=filtered[filtered.market.str.contains(re.escape(market),case=False,na=False)]
    if problem!='All': filtered=filtered[filtered.problem==problem]
    if status!='All': filtered=filtered[filtered.status==status]
    filtered=filtered[(filtered.priority_score>=min_score)&(filtered.product_fit_score>=min_fit)]
    if keyword.strip(): filtered=filtered[filtered.text.str.contains(re.escape(keyword.strip()),case=False,na=False)]
    filtered=filtered.sort_values(['priority_score','buying_intent_score','product_fit_score'],ascending=False)

st.subheader('3. Acquisition dashboard')
vals=[len(filtered),int((filtered.category=='HOT').sum()),int((filtered.category=='WARM').sum()),int((filtered.category=='POSSIBLE').sum()),int((filtered.category=='LOW').sum()),int((filtered.product_fit_score>=75).sum()),int((filtered.buying_intent_score>=70).sum()) if 'buying_intent_score' in filtered else 0]
cols=st.columns(7)
for c,l,v in zip(cols,['Signals','HOT','WARM','POSSIBLE','LOW','High-fit','High-intent'],vals): c.metric(l,v)
if not filtered.empty:
    a,b,c=st.columns(3)
    for box, title, counts in [(a,'Top platforms',filtered.platform.value_counts().head(5)),(b,'Top markets',filtered.market.value_counts().head(5)),(c,'Top problems',filtered.problem.value_counts().head(5))]:
        box.write(f'**{title}**')
        for label, count in counts.items():
            box.write(f'{label} — **{int(count)}**')
else:
    st.info('No opportunities match the current filters. Add a source and fetch live signals, or select Demo mode to preview the workflow.')

st.subheader('4. Opportunity queue')
st.caption(f'Showing {len(filtered)} opportunities • User-intent: {int((filtered.get("signal_type", pd.Series(dtype=str))=="User-intent signal").sum()) if not filtered.empty else 0}')
queue_cols=['platform','text','market','evidence_type','evidence_strength','relevance_score','buying_intent_score','product_fit_score','priority_score','category','sales_ready','buyer_stage','competition_detected','problem','recommended_action','status','url']
if filtered.empty:
    st.info('Opportunity queue is empty.')
else:
    table = filtered[queue_cols].copy()
    st.dataframe(table, use_container_width=True, hide_index=True, column_config={
        'url': st.column_config.LinkColumn('Source', display_text='Open'),
        'intent_score': st.column_config.NumberColumn('Intent', min_value=0, max_value=100, format='%d'),
        'customer_fit_score': st.column_config.NumberColumn('Fit', min_value=0, max_value=100, format='%d')
    })

st.subheader('5. Human review + action tracking')
if not filtered.empty:
    selected = st.selectbox('Select opportunity', filtered.signal_id.tolist(), format_func=lambda x: f"{x} — {filtered.loc[filtered.signal_id==x,'category'].iloc[0]} — {filtered.loc[filtered.signal_id==x,'text'].iloc[0][:90]}")
    row = filtered[filtered.signal_id==selected].iloc[0]
    a,b,c,d,e,f=st.columns(6); a.metric('Relevance',int(row.get('relevance_score',0) or 0)); b.metric('Buying intent',int(row.get('buying_intent_score',0) or 0)); c.metric('Product fit',int(row.get('product_fit_score',0) or 0)); d.metric('Priority',f"{int(row.get('priority_score',0) or 0)} — {row.category}"); e.metric('Confidence',f"{float(row.get('confidence',0.5) or 0.5):.0%}"); f.metric('Sales-ready','YES' if bool(row.get('sales_ready',False)) else 'NO')
    st.write(f"**Buyer stage:** {clean(row.get('buyer_stage','Not a lead'))}")
    st.write(f"**Lead reason:** {clean(row.get('lead_reason',''))}")
    st.write(f"**Lead evidence:** {clean(row.get('evidence_type','Context-only'))} • **Strength:** {clean(row.get('evidence_strength','Weak'))}")
    evidence_sentence = clean(row.get('evidence_sentence',''))
    if evidence_sentence: st.info(f"Evidence sentence: {evidence_sentence}")
    st.write(f"**Content angle:** {clean(row.get('content_angle',''))}")
    st.write(f"**Problem:** {row.problem}")
    st.write(f"**Suggested Daily Levels solution:** {row.daily_levels_solution}")
    st.write(f"**Recommended action:** {row.recommended_action}")
    st.caption('Priority is a qualification score combining relevance, buying intent, and product fit; it is not proof of purchase intent.')
    explicit_need = bool(row.get('explicit_need',False)) and not pd.isna(row.get('explicit_need',False))
    competition = bool(row.get('competition_detected',False)) and not pd.isna(row.get('competition_detected',False))
    st.write(f"**Signal type:** {clean(row.get('signal_type','User-intent signal')) or 'User-intent signal'} • **Explicit need:** {'Yes' if explicit_need else 'No'} • **Competition detected:** {'Yes' if competition else 'No'}")
    quality_flags = clean(row.get('quality_flags',''))
    if quality_flags and quality_flags.lower() != 'nan': st.warning(f"Quality flags: {quality_flags}")
    st.write(f"**Signal:** {row.text}")
    st.write(f"**Source:** {row.url}")
    x,y=st.columns(2)
    current_status = clean(row.get('status','New')) if clean(row.get('status','New')) in STATUS_OPTIONS else 'New'
    new_status=x.selectbox('Review status',STATUS_OPTIONS,index=STATUS_OPTIONS.index(current_status))
    if x.button('Save review status'): store.update_status(selected,new_status); st.rerun()
    event=y.selectbox('Record conversion event',EVENT_OPTIONS)
    if y.button('Record event'):
        store.add_conversion(selected,event,row.platform,row.market,row.problem,'','Human-recorded'); st.success('Event recorded.')
else:
    st.info('Select an opportunity after live signals are loaded.')

st.subheader('6. Conversion intelligence')
conv=store.conversions()
if conv.empty:
    st.info('No conversion events recorded yet. Record events from reviewed opportunities to build acquisition analytics.')
else:
    m=st.columns(5)
    m[0].metric('Events',len(conv)); m[1].metric('Website visits',int((conv.event=='Website visit').sum())); m[2].metric('Signups',int((conv.event=='Signup').sum())); m[3].metric('Trials',int((conv.event=='Trial/start').sum())); m[4].metric('Purchases',int((conv.event=='Purchase').sum()))
    st.dataframe(conv,use_container_width=True,hide_index=True)

st.subheader('7. Qualification intelligence')
if not filtered.empty and 'buying_intent_score' in filtered:
    q1,q2,q3,q4,q5=st.columns(5)
    q1.metric('Relevant (45+)', int((filtered.relevance_score>=45).sum()))
    q2.metric('High intent (70+)', int((filtered.buying_intent_score>=70).sum()))
    q3.metric('High fit (75+)', int((filtered.product_fit_score>=75).sum()))
    q4.metric('Alternative source detected', int(filtered.competition_detected.sum()))
    q5.metric('Sales-ready', int(filtered.sales_ready.sum()) if 'sales_ready' in filtered else 0)
    st.write('**Evidence audit:** ' + ' • '.join([f"{k}: {int(v)}" for k,v in filtered.evidence_type.value_counts().items()]))
    if 'evidence_strength' in filtered:
        st.write('**Evidence strength:** ' + ' • '.join([f"{k}: {int(v)}" for k,v in filtered.evidence_strength.value_counts().items()]))
    st.write('**Target funnel:** Raw signals → Evidence-qualified → Problem-aware / Direct request → Sales-ready → Human review → Sale.')
    st.dataframe(filtered.groupby('market').agg(signals=('signal_id','count'), relevant=('relevance_score',lambda s:int((s>=45).sum())), high_intent=('buying_intent_score',lambda s:int((s>=70).sum())), high_fit=('product_fit_score',lambda s:int((s>=75).sum()))).reset_index().sort_values(['high_intent','high_fit'],ascending=False),use_container_width=True,hide_index=True)
else:
    st.info('Qualification metrics will appear after signals are loaded.')

st.subheader('8. Source health')
if runs.empty:
    st.info('No source runs yet. Load recommended sources or add a permitted public source, then click Fetch live signals now.')
else:
    health = runs.copy()
    health['status'] = health.error.fillna('').map(lambda x: 'ERROR' if str(x).strip() else 'OK')
    st.dataframe(health[['run_at','source_type','source_name','rows_fetched','new_rows','status','error']],use_container_width=True,hide_index=True)

st.subheader('9. Export')
st.download_button('Download opportunities CSV',live_results.to_csv(index=False).encode('utf-8'),'daily_levels_opportunities.csv','text/csv')
if not conv.empty:
    st.download_button('Download conversion events CSV',conv.to_csv(index=False).encode('utf-8'),'daily_levels_conversion_events.csv','text/csv')

st.subheader('10. Complete acquisition workflow')
st.markdown('''**Public source → Fetch → Normalize → Deduplicate → Lead evidence → Relevance → True unmet need → Buying intent → Product fit → Sales-ready gate → HOT/WARM/POSSIBLE/LOW → Opportunity queue → Human review → Content/educational action → Website visit → Signup → Purchase → Conversion analytics**\n\nNo private data, automated outreach, scraping behind access controls, or bypassing platform restrictions.''')

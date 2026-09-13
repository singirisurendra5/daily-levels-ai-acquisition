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
SAMPLE_PATH = ROOT / 'data' / 'sample_signals.csv'
DB_PATH = ROOT / 'data' / 'daily_levels.db'

st.set_page_config(page_title='Daily Levels — AI Customer Acquisition', page_icon='📈', layout='wide')
st.title('Daily Levels — AI Customer Acquisition')
st.caption('MVP V3.2 • Live public-signal ingestion • Persistent opportunity workflow • Human-in-the-loop')

store = Store(DB_PATH)

def clean(x): return '' if pd.isna(x) else str(x).strip()

def validate(df):
    missing = {'platform','url','text'} - set(df.columns)
    if missing: raise ValueError('Missing required columns: ' + ', '.join(sorted(missing)))

def load_sources():
    try: return json.loads(SOURCES_PATH.read_text(encoding='utf-8'))
    except Exception: return {'rss_feeds': [], 'reddit': [], 'youtube_channels': []}

def save_sources(cfg):
    SOURCES_PATH.parent.mkdir(exist_ok=True)
    SOURCES_PATH.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

def score_frame(raw):
    if raw.empty: return raw.copy()
    work = raw.copy()
    for c in ['platform','url','text']:
        if c not in work: work[c] = ''
        work[c] = work[c].map(clean)
    if 'date' not in work: work['date'] = ''
    analysis = work['text'].apply(lambda x: pd.Series(analyze(x)))
    result = pd.concat([work.reset_index(drop=True), analysis.reset_index(drop=True)], axis=1)
    result['signal_id'] = [signal_id(p,u,t) for p,u,t in zip(result.platform,result.url,result.text)]
    return result

def run_configured_sources(cfg):
    frames=[]; errors=[]; run_rows=[]
    for item in cfg.get('rss_feeds',[]):
        name=item.get('platform','RSS')
        try:
            df=fetch_rss(item['url'], name); frames.append(df); run_rows.append(('RSS',name,len(df),'')); store.log_run('RSS',name,len(df))
        except Exception as e:
            errors.append(f'RSS {name}: {e}'); store.log_run('RSS',name,0,str(e))
    for item in cfg.get('reddit',[]):
        name=f"Reddit r/{item.get('subreddit','')}"
        try:
            df=fetch_reddit_rss(item['subreddit'],item.get('query',''),item.get('sort','new'),item.get('limit',25)); frames.append(df); run_rows.append(('Reddit',name,len(df),'')); store.log_run('Reddit',name,len(df))
        except Exception as e:
            errors.append(f'{name}: {e}'); store.log_run('Reddit',name,0,str(e))
    for item in cfg.get('youtube_channels',[]):
        name=f"YouTube {item.get('channel_id','')[:12]}"
        try:
            df=fetch_youtube_channel(item['channel_id'],item.get('limit',15)); frames.append(df); run_rows.append(('YouTube',name,len(df),'')); store.log_run('YouTube',name,len(df))
        except Exception as e:
            errors.append(f'{name}: {e}'); store.log_run('YouTube',name,0,str(e))
    return combine_frames(frames), errors, run_rows

cfg=load_sources()
with st.expander('⚙️ Source Manager', expanded=True):
    st.caption('Only add public sources you are permitted to access. This app does not message users or access private data.')
    tabs=st.tabs(['RSS / Atom','Reddit public feed','YouTube public feed'])
    with tabs[0]:
        for i,item in enumerate(cfg.get('rss_feeds',[])):
            c1,c2,c3=st.columns([2,4,1]); c1.write(item.get('platform','RSS')); c2.write(item.get('url','')); 
            if c3.button('Remove', key=f'rm_rss_{i}'):
                cfg['rss_feeds'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_rss'):
            a,b,c=st.columns([2,4,1]); platform=a.text_input('Platform'); url=b.text_input('Feed URL'); add=c.form_submit_button('Add')
            if add and platform.strip() and url.strip(): cfg['rss_feeds'].append({'platform':platform.strip(),'url':url.strip()}); save_sources(cfg); st.rerun()
    with tabs[1]:
        for i,item in enumerate(cfg.get('reddit',[])):
            c1,c2,c3,c4=st.columns([1,2,2,1]); c1.write('Reddit'); c2.write('r/'+item.get('subreddit','')); c3.write(item.get('query','')); 
            if c4.button('Remove', key=f'rm_red_{i}'):
                cfg['reddit'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_reddit'):
            a,b,c,d=st.columns([1.3,2,2,1]); sub=a.text_input('Subreddit'); query=b.text_input('Search query'); limit=c.number_input('Limit',1,100,25); add=d.form_submit_button('Add')
            if add and sub.strip(): cfg['reddit'].append({'subreddit':sub.strip(),'query':query.strip(),'sort':'new','limit':int(limit)}); save_sources(cfg); st.rerun()
    with tabs[2]:
        for i,item in enumerate(cfg.get('youtube_channels',[])):
            c1,c2=st.columns([5,1]); c1.write(item.get('channel_id','')); 
            if c2.button('Remove', key=f'rm_yt_{i}'):
                cfg['youtube_channels'].pop(i); save_sources(cfg); st.rerun()
        with st.form('add_yt'):
            a,b=st.columns([4,1]); cid=a.text_input('YouTube Channel ID'); limit=b.number_input('Limit',1,50,15); add=b.form_submit_button('Add')
            if add and cid.strip(): cfg['youtube_channels'].append({'channel_id':cid.strip(),'limit':int(limit)}); save_sources(cfg); st.rerun()

configured=sum(len(cfg.get(k,[])) for k in ['rss_feeds','reddit','youtube_channels'])
col1,col2,col3=st.columns(3)
with col1:
    if st.button('🔄 Fetch live signals now', type='primary', use_container_width=True):
        with st.spinner('Fetching configured public sources…'):
            live,errors,runs=run_configured_sources(cfg)
            scored=score_frame(live)
            deduped,_=deduplicate_signals(scored)
            new_count=store.upsert_signals(deduped[~deduped['is_duplicate']])
        st.session_state['last_fetch']=datetime.now(timezone.utc).isoformat(); st.session_state['last_errors']=errors; st.session_state['new_count']=new_count; st.rerun()
with col2: st.metric('Configured sources', configured)
with col3: st.metric('New on last fetch', st.session_state.get('new_count',0))
if st.session_state.get('last_errors'):
    with st.expander('Ingestion warnings'):
        for e in st.session_state['last_errors']: st.warning(e)

# Input mode
st.subheader('1. Signal sources')
mode=st.radio('Dataset mode', ['Live opportunities only','Live + uploaded CSV','Demo + live + uploaded CSV'], horizontal=True)
uploaded=st.file_uploader('Optional public-signal CSV', type=['csv'])
manual=pd.DataFrame()
if uploaded:
    try: manual=pd.read_csv(uploaded); validate(manual); manual=score_frame(manual); dups,_=deduplicate_signals(manual); store.upsert_signals(dups[~dups['is_duplicate']])
    except Exception as e: st.error(str(e)); st.stop()

live_results=store.signals()
try: sample=pd.read_csv(SAMPLE_PATH)
except Exception: sample=pd.DataFrame(columns=['platform','url','text','date'])
if mode.startswith('Demo'): 
    demo=score_frame(sample); demo,_=deduplicate_signals(demo); live_results=pd.concat([live_results,demo],ignore_index=True).drop_duplicates(subset=['signal_id'])

st.subheader('2. Normalize + duplicate detection')
runs=store.runs(); last_run=runs.iloc[0] if not runs.empty else None
st.caption(f'Persistent signals: {len(live_results)} • Configured sources: {configured} • Last run: {last_run.run_at if last_run is not None else "Not yet fetched"}')

# Filters
st.sidebar.header('Opportunity filters')
platform_options=['All']+sorted(live_results.platform.dropna().unique().tolist()) if not live_results.empty else ['All']
market_options=['All']+sorted(live_results.market.dropna().unique().tolist()) if not live_results.empty else ['All']
problem_options=['All']+sorted(live_results.problem.dropna().unique().tolist()) if not live_results.empty else ['All']
status_options=['All','New','Reviewed','Content planned','Educational reply','Invited to learn','Converted','Do not contact']
platform=st.sidebar.selectbox('Platform',platform_options); market=st.sidebar.selectbox('Market',market_options); problem=st.sidebar.selectbox('Problem',problem_options); status=st.sidebar.selectbox('Status',status_options); min_score=st.sidebar.slider('Minimum intent',0,100,0); min_fit=st.sidebar.slider('Minimum fit',0,100,0); keyword=st.sidebar.text_input('Keyword contains','')
filtered=live_results.copy()
if platform!='All': filtered=filtered[filtered.platform==platform]
if market!='All': filtered=filtered[filtered.market.str.contains(re.escape(market),case=False,na=False)]
if problem!='All': filtered=filtered[filtered.problem==problem]
if status!='All': filtered=filtered[filtered.status==status]
filtered=filtered[(filtered.intent_score>=min_score)&(filtered.customer_fit_score>=min_fit)]
if keyword.strip(): filtered=filtered[filtered.text.str.contains(re.escape(keyword.strip()),case=False,na=False)]
filtered=filtered.sort_values(['customer_fit_score','intent_score'],ascending=False)

st.subheader('3. Acquisition dashboard')
vals=[len(filtered),int((filtered.category=='HOT').sum()),int((filtered.category=='WARM').sum()),int((filtered.category=='POSSIBLE').sum()),int((filtered.category=='LOW').sum()),int((filtered.customer_fit_score>=80).sum())]
cols=st.columns(6)
for c,l,v in zip(cols,['Signals','HOT','WARM','POSSIBLE','LOW','High-fit'],vals): c.metric(l,v)
if not filtered.empty:
    a,b,c=st.columns(3)
    a.dataframe(filtered.platform.value_counts().head(5).rename('signals'),use_container_width=True)
    b.dataframe(filtered.market.value_counts().head(5).rename('signals'),use_container_width=True)
    c.dataframe(filtered.problem.value_counts().head(5).rename('signals'),use_container_width=True)

st.subheader('4. Opportunity queue')
st.caption(f'Showing {len(filtered)} opportunities')
queue_cols=['platform','text','market','intent_score','customer_fit_score','category','problem','recommended_action','status','url']
st.dataframe(filtered[queue_cols],use_container_width=True,hide_index=True,column_config={'url':st.column_config.LinkColumn('Source',display_text='Open'),'intent_score':st.column_config.NumberColumn('Intent', min_value=0, max_value=100, format='%d'),'customer_fit_score':st.column_config.NumberColumn('Fit', min_value=0, max_value=100, format='%d')})

st.subheader('5. Human review + action tracking')
if not filtered.empty:
    selected=st.selectbox('Select opportunity',filtered.signal_id.tolist(),format_func=lambda x: f"{x} — {filtered.loc[filtered.signal_id==x,'category'].iloc[0]} — {filtered.loc[filtered.signal_id==x,'text'].iloc[0][:90]}")
    row=filtered[filtered.signal_id==selected].iloc[0]
    a,b,c,d=st.columns(4); a.metric('Intent',int(row.intent_score)); b.metric('Fit',int(row.customer_fit_score)); c.metric('Priority',row.category); d.metric('Confidence',f"{float(row.get('confidence',0.5)):.0%}")
    st.write(f"**Problem:** {row.problem}"); st.write(f"**Solution:** {row.daily_levels_solution}"); st.write(f"**Recommended action:** {row.recommended_action}"); st.write(f"**Signal:** {row.text}"); st.write(f"**Source:** {row.url}")
    x,y=st.columns(2)
    new_status=x.selectbox('Review status',['New','Reviewed','Content planned','Educational reply','Invited to learn','Converted','Do not contact'],index=['New','Reviewed','Content planned','Educational reply','Invited to learn','Converted','Do not contact'].index(row.status) if row.status in ['New','Reviewed','Content planned','Educational reply','Invited to learn','Converted','Do not contact'] else 0)
    if x.button('Save review status'): store.update_status(selected,new_status); st.rerun()
    event=y.selectbox('Record conversion event',['Content published','Educational reply','Website visit','Signup','Trial/start','Purchase'])
    if y.button('Record event'):
        store.add_conversion(selected,event,row.platform,row.market,row.problem,'','Human-recorded'); st.success('Event recorded.')

st.subheader('6. Conversion intelligence')
conv=store.conversions()
if conv.empty: st.info('No conversion events recorded yet. Record events from reviewed opportunities to build acquisition analytics.')
else:
    m=st.columns(4); m[0].metric('Events',len(conv)); m[1].metric('Website visits',int((conv.event=='Website visit').sum())); m[2].metric('Signups',int((conv.event=='Signup').sum())); m[3].metric('Purchases',int((conv.event=='Purchase').sum()))
    st.dataframe(conv,use_container_width=True,hide_index=True)

st.subheader('7. Source health')
if runs.empty: st.info('No source runs yet. Add at least one public source and click Fetch live signals now.')
else: st.dataframe(runs,use_container_width=True,hide_index=True)

st.subheader('8. Export')
st.download_button('Download opportunities CSV',live_results.to_csv(index=False).encode('utf-8'),'daily_levels_opportunities.csv','text/csv')
if not conv.empty: st.download_button('Download conversion events CSV',conv.to_csv(index=False).encode('utf-8'),'daily_levels_conversion_events.csv','text/csv')

st.subheader('9. Complete acquisition workflow')
st.markdown('''**Public source → Fetch → Normalize → Deduplicate → Intent + market detection → Daily Levels fit → HOT/WARM/POSSIBLE/LOW → Opportunity queue → Human review → Content/educational action → Website visit → Signup → Purchase → Conversion analytics**\n\nNo private data, automated outreach, scraping behind access controls, or bypassing platform restrictions.''')

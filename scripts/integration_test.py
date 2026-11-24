"""Real TCP/WebSocket test. TEST actors are automation, never editorial approval."""
import asyncio,hashlib,json,os,secrets,subprocess,sys,time,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
import httpx,websockets
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs';OUT.mkdir(exist_ok=True)
(ROOT/'build').mkdir(exist_ok=True)
RUN=Path(tempfile.mkdtemp(prefix='integration-',dir=ROOT/'build'))
env=dict(os.environ,DATA_DIR=str(RUN/'data'),NEWS_DIR=str(RUN/'news'),UPSTREAM_URL='http://127.0.0.1:18101',DATA_INTERVAL='0.5',ALLOW_DEMO_FALLBACK='1')
news=RUN/'news';news.mkdir(exist_ok=True)
tokens={n:secrets.token_urlsafe(24) for n in ['TEST-writer','TEST-editor']}
(news/'users.json').write_text(json.dumps([dict(name=n,role=n.split('-')[1],token_hash=hashlib.sha256(t.encode()).hexdigest()) for n,t in tokens.items()]))
processes=[];checks=[]
def check(name,condition,detail=''):
    checks.append(dict(name=name,passed=bool(condition),detail=detail))
    if not condition:raise AssertionError(name+': '+detail)
def wait(url):
    for _ in range(80):
        try:
            r=httpx.get(url,timeout=1)
            if r.status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.2)
    raise RuntimeError('server not ready '+url)
def call(path,body=None,actor='TEST-writer'):
    return httpx.request('GET' if body is None else 'POST','http://127.0.0.1:18102'+path,json=body,headers={'Authorization':'Bearer '+tokens[actor]},timeout=10)
async def sockets():
    async with websockets.connect('ws://127.0.0.1:18102/ws') as ws:
        first=json.loads(await asyncio.wait_for(ws.recv(),5))
        for _ in range(12):
            nxt=json.loads(await asyncio.wait_for(ws.recv(),5))
            if nxt.get('snapshot_id')!=first.get('snapshot_id'):
                check('WebSocket receives new snapshot',True);return
        check('WebSocket receives new snapshot',False)
try:
    for directory,port in [('election-data-server',18101),('election-news-server',18102)]:
        log=(RUN/f'{port}.log').open('w',encoding='utf-8')
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--app-dir',str(ROOT/directory),'--port',str(port),'--host','127.0.0.1'],env=env,stdout=log,stderr=log))
        wait(f'http://127.0.0.1:{port}/health')
    for _ in range(30):
        snap=call('/api/snapshot').json()
        if snap.get('rows'):break
        time.sleep(.2)
    check('Cross-server receive',bool(snap.get('rows')))
    asyncio.run(sockets())
    check('No token cannot generate',httpx.post('http://127.0.0.1:18102/api/articles',json={'region':'계양구을'}).status_code==401)
    a=call('/api/articles',{'region':'계양구을'}).json();aid=a['id']
    v=call(f'/api/articles/{aid}/validate',{}).json()
    check('Normal validation',v['validation']['rule']=='PASS')
    check('Writer cannot approve',call(f'/api/articles/{aid}/approve',dict(reason='시험용 확인 사유',evidence_checked=True,ai_unavailable_ack=True)).status_code==403)
    ap=call(f'/api/articles/{aid}/approve',dict(reason='TEST 자동시험 전용 원문 일치 확인. 실제 사람 승인이 아님.',evidence_checked=True,ai_unavailable_ack=True),'TEST-editor')
    check('Test editor approval',ap.status_code==200)
    ex=call(f'/api/articles/{aid}/export',actor='TEST-editor').json()
    check('Export uses pinned snapshot',ex['snapshot_id']==a['snapshot_id'])
    (OUT/'test_approved_bundle.json').write_text(json.dumps(ex,ensure_ascii=False,indent=2),encoding='utf-8')
    bad=json.loads(json.dumps(a['sentences']));bad[0]['values']['region_name']='부산'
    rev=call(f'/api/articles/{aid}/revisions',dict(title=a['title'],sentences=bad,reason='TEST 지역 불일치 주입')).json()
    check('Revision drops approval',rev['status']=='DRAFT' and 'approved_at' not in rev)
    fail=call(f"/api/articles/{rev['id']}/validate",{}).json()
    check('Wrong region fails',fail['validation']['rule']=='FAIL')
    blocked=call(f"/api/articles/{rev['id']}/approve",dict(reason='TEST 차단 확인 사유',evidence_checked=True,ai_unavailable_ack=True),'TEST-editor')
    check('Failed article cannot be approved',blocked.status_code==409)
    check('Failed article cannot export',call(f"/api/articles/{rev['id']}/export",actor='TEST-editor').status_code==409)
    (OUT/'test_blocked_article.json').write_text(json.dumps(fail,ensure_ascii=False,indent=2),encoding='utf-8')
    processes[0].terminate();processes[0].wait(timeout=8)
    for _ in range(40):
        health=call('/health').json()
        if health['connection']['state']=='DISCONNECTED':break
        time.sleep(.25)
    check('Upstream failure displayed',health['connection']['state']=='DISCONNECTED')
    check('Fallback remains demo',call('/api/snapshot').json()['mode']=='demo')
    audits=call('/api/audit',actor='TEST-editor').json()
    (OUT/'test_audit_log.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
    for p in processes:
        if p.poll() is None:p.terminate();p.wait(timeout=8)
    result=dict(at=datetime.now(timezone(timedelta(hours=9))).isoformat(),test_actors_only=True,checks=checks,total=len(checks),passed=sum(c['passed'] for c in checks))
    (OUT/'integration_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

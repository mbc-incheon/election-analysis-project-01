import hashlib
import json
import re
import sqlite3
import secrets
import threading
from functools import wraps
from datetime import datetime,timezone,timedelta
from pathlib import Path

def now(): return datetime.now(timezone(timedelta(hours=9))).isoformat()
def canonical(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def sha(v): return hashlib.sha256(canonical(v).encode()).hexdigest()

def locked(fn):
    @wraps(fn)
    def call(self,*args,**kwargs):
        with self.lock:return fn(self,*args,**kwargs)
    return call

class Newsroom:
    def __init__(self,root):
        self.lock=threading.RLock()
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/'news.sqlite',check_same_thread=False)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
        self.db.commit()

    @locked
    def audit(self,kind,actor,details):
        last=self.db.execute('SELECT hash FROM audit ORDER BY id DESC LIMIT 1').fetchone()
        prev=last[0] if last else '0'*64
        payload=dict(at=now(),kind=kind,actor=actor,details=details)
        self.db.execute('INSERT INTO audit(previous_hash,hash,payload) VALUES(?,?,?)',(prev,sha([prev,payload]),canonical(payload)))
        self.db.commit()

    @locked
    def receive(self,event):
        eid=sha(event)
        if self.db.execute('SELECT 1 FROM snapshot WHERE id=?',(eid,)).fetchone(): return False
        self.db.execute('INSERT INTO snapshot VALUES(?,?,?,?,?)',(eid,event['sequence'],event['mode'],canonical(event),now()))
        self.db.commit(); self.audit('snapshot','receiver',dict(id=eid,sequence=event['sequence'],mode=event['mode']))
        return True

    @locked
    def latest(self):
        row=self.db.execute('SELECT id,payload FROM snapshot ORDER BY rowid DESC LIMIT 1').fetchone()
        return dict(snapshot_id=row[0],**json.loads(row[1])) if row else dict(rows=[],mode='unavailable')

    @locked
    def add_document(self,doc,actor):
        required=['title','publisher','url','published_at','collected_at','document_type','election_id','region_name','candidate_id','text','is_demo','rights']
        if any(k not in doc for k in required): raise ValueError('document metadata incomplete')
        if not doc['text'].strip(): raise ValueError('empty document')
        if not doc['is_demo'] and not doc['url'].startswith('https://'): raise ValueError('official document URL required')
        if doc['document_type']=='campaign' and not doc['is_demo'] and not doc.get('human_verified'):
            raise ValueError('candidate document requires original verification')
        docid=sha(doc)[:20]
        raw=self.root/'raw_documents';raw.mkdir(exist_ok=True)
        p=raw/f'{docid}.json'
        if not p.exists():
            p.write_text(canonical(doc),encoding='utf-8'); p.chmod(0o444)
        paragraphs=[p.strip() for p in doc['text'].split('\n\n') if p.strip()]
        ids=[]
        for index,text in enumerate(paragraphs):
            cid=f'{docid}-p{index+1}'
            chunk={k:v for k,v in doc.items() if k!='text'}
            chunk.update(id=cid,document_id=docid,text=text,location=f'문단 {index+1}',sha256=sha(text))
            self.db.execute('INSERT OR IGNORE INTO chunk VALUES(?,?,1)',(cid,canonical(chunk)));ids.append(cid)
        self.db.commit();self.audit('document',actor,dict(document_id=docid,chunks=ids))
        return ids

    @locked
    def search(self,query,region,candidate,election='KR-20240410-NA22',demo=True):
        tokens=set(re.findall(r'[가-힣A-Za-z0-9]+',query))
        results=[]
        for cid,payload in self.db.execute('SELECT id,payload FROM chunk WHERE active=1'):
            c=json.loads(payload)
            if (c['election_id'],c['region_name'],c['candidate_id'],c['is_demo'])!=(election,region,candidate,demo):continue
            score=sum(t in c['text'] for t in tokens)
            if score: results.append(dict(score=score,**c))
        return sorted(results,key=lambda c:(-c['score'],c['id']))[:5]

    @locked
    def draft(self,region,author):
        snap=self.latest();rows=[r for r in snap['rows'] if r['region_name']==region]
        if not rows: raise ValueError('region not available')
        sentences=[]
        for r in rows:
            text=f"{r['region_name']} {r['baseline_at']} 기준 {r['candidate_name']}의 득표수는 {r['votes']:,}표, 득표율은 {r['vote_share']:.2f}%다."
            sentences.append(dict(kind='result',text=text,row_ids=[r['row_id']],values={k:r[k] for k in ['region_name','candidate_id','candidate_name','baseline_at','votes','vote_share','count_rate']}))
            hits=self.search('교통 주거 지역경제',region,r['candidate_id'],demo=r['is_demo'])
            if hits:
                c=hits[0]; sentences.append(dict(kind='pledge',text=f"{r['candidate_name']}의 공약 자료에는 다음 내용이 제시돼 있다: {c['text']}",candidate_id=r['candidate_id'],region_name=region,evidence_ids=[c['id']],evidence_hashes=[c['sha256']]))
        a=dict(id=secrets.token_hex(8),revision=1,author=author,created_at=now(),snapshot_id=snap['snapshot_id'],mode=snap['mode'],region_name=region,
               title=f'{region} 개표와 공약 확인',sentences=sentences,ai_review=dict(verdict='UNAVAILABLE',model=None),status='DRAFT')
        self.save(a);self.audit('draft',author,dict(article_id=a['id'],snapshot_id=a['snapshot_id']))
        return a

    @locked
    def save(self,a):
        self.db.execute('INSERT OR REPLACE INTO article VALUES(?,?,?)',(a['id'],canonical(a),a['status']));self.db.commit()
    @locked
    def get(self,aid):
        r=self.db.execute('SELECT payload FROM article WHERE id=?',(aid,)).fetchone()
        if not r: raise ValueError('article not found')
        return json.loads(r[0])

    @locked
    def validate(self,a,actor='validator'):
        errors=[]
        src=self.db.execute('SELECT payload FROM snapshot WHERE id=?',(a['snapshot_id'],)).fetchone()
        snap=json.loads(src[0]) if src else dict(rows=[])
        rows={r['row_id']:r for r in snap['rows']}
        if not a['sentences']: errors.append('EMPTY_ARTICLE')
        if re.search('압승|필승|지지하|무능|당선 확실|당선 예상',a['title']+' '.join(s['text'] for s in a['sentences'])): errors.append('NEUTRALITY')
        for i,s in enumerate(a['sentences']):
            prefix=f'S{i+1}:'
            if s['kind']=='result':
                rr=[rows[x] for x in s.get('row_ids',[]) if x in rows]
                if len(rr)!=1: errors.append(prefix+'ROW_NOT_FOUND');continue
                r=rr[0]
                if set(s.get('values',{}))!={'region_name','candidate_id','candidate_name','baseline_at','votes','vote_share','count_rate'}:errors.append(prefix+'MISSING_FIELDS')
                if not r.get('source_url'):errors.append(prefix+'SOURCE_MISSING')
                for k,v in s.get('values',{}).items():
                    if r.get(k)!=v: errors.append(prefix+k.upper()+'_MISMATCH')
                expected=f"{r['region_name']} {r['baseline_at']} 기준 {r['candidate_name']}의 득표수는 {r['votes']:,}표, 득표율은 {r['vote_share']:.2f}%다."
                if s['text']!=expected: errors.append(prefix+'TEXT_MISMATCH')
                if r['region_name']!=a['region_name']:errors.append(prefix+'REGION_MISMATCH')
                if r['valid_votes']<=0 or abs(r['votes']/r['valid_votes']*100-r['vote_share'])>0.011:errors.append(prefix+'ARITHMETIC')
                try:
                    dt=datetime.fromisoformat(r['baseline_at'])
                    if dt.tzinfo is None or dt.year!=2024:raise ValueError()
                except ValueError:errors.append(prefix+'DATE')
            elif s['kind']=='pledge':
                ids=s.get('evidence_ids',[])
                if len(ids)!=1:errors.append(prefix+'NO_EVIDENCE');continue
                cr=self.db.execute('SELECT payload,active FROM chunk WHERE id=?',(ids[0],)).fetchone()
                if not cr or not cr[1]:errors.append(prefix+'EVIDENCE_RETIRED');continue
                c=json.loads(cr[0])
                if c['sha256'] not in s.get('evidence_hashes',[]):errors.append(prefix+'EVIDENCE_VERSION')
                if c['candidate_id']!=s['candidate_id'] or c['region_name']!=a['region_name']:errors.append(prefix+'EVIDENCE_SCOPE')
                if not c.get('url'):errors.append(prefix+'SOURCE_MISSING')
                candidate=next((r['candidate_name'] for r in rows.values() if r['candidate_id']==c['candidate_id']),None)
                if s['text']!=f"{candidate}의 공약 자료에는 다음 내용이 제시돼 있다: {c['text']}":errors.append(prefix+'UNSUPPORTED_TEXT')
                if c['is_demo']!=(a['mode']=='demo'):errors.append(prefix+'MODE_MISMATCH')
            else:errors.append(prefix+'UNSUPPORTED_CLAIM')
        if not any(s['kind']=='pledge' for s in a['sentences']):errors.append('NO_PLEDGE_EVIDENCE')
        rule='FAIL' if errors else 'PASS'
        ai=a['ai_review']['verdict']
        disagreement=ai in ['PASS','FAIL'] and ai!=rule
        a['validation']=dict(rule=rule,errors=errors,ai=ai,disagreement=disagreement,at=now())
        a['status']='REVIEW_REQUIRED' if errors or disagreement else 'PENDING_HUMAN'
        self.save(a);self.audit('validation',actor,dict(article_id=a['id'],**a['validation']))
        return a

    @locked
    def approve(self,aid,actor,reason,evidence_checked,ai_unavailable_ack=False):
        a=self.validate(self.get(aid),actor)
        if a['validation']['rule']!='PASS' or a['validation']['disagreement']:raise ValueError('approval blocked: failed or disputed')
        if actor==a['author']:raise ValueError('independent reviewer required')
        if not reason.strip() or not evidence_checked:raise ValueError('review reason and evidence confirmation required')
        if a['ai_review']['verdict']=='UNAVAILABLE' and not ai_unavailable_ack:raise ValueError('acknowledge unavailable AI and review manually')
        a.update(status='APPROVED',approved_by=actor,approved_at=now(),approval_reason=reason)
        self.save(a)
        self.db.execute('INSERT INTO approval(article_id,reviewer,reason,created_at) VALUES(?,?,?,?)',(aid,actor,reason,now()));self.db.commit()
        self.audit('approval',actor,dict(article_id=aid,reason=reason,manual_evidence_check=evidence_checked,ai_unavailable_ack=ai_unavailable_ack))
        return a

    @locked
    def retire(self,cid,actor):
        self.db.execute('UPDATE chunk SET active=0 WHERE id=?',(cid,))
        for aid,payload in self.db.execute('SELECT id,payload FROM article').fetchall():
            a=json.loads(payload)
            if any(cid in s.get('evidence_ids',[]) for s in a['sentences']):
                a['status']='REVIEW_REQUIRED';a['withdrawn_at']=now();self.save(a)
        self.db.commit();self.audit('retire',actor,dict(chunk_id=cid))

    @locked
    def export(self,aid):
        a=self.get(aid)
        if a['status']!='APPROVED':raise ValueError('only approved article may be exported')
        # Revalidate on a copy. It must not erase a valid existing human approval.
        check=self.validate(dict(a),'export-validator')
        if check['validation']['rule']!='PASS' or check['validation']['disagreement']:raise ValueError('approval invalidated')
        self.save(a)
        return dict(article=a,script='\n'.join(s['text'] for s in a['sentences']),disclosure='시뮬레이션 데이터' if a['mode']=='demo' else '2024년 선거 과거 자료',ai_disclosure='규칙 기반 초안 생성. 생성형 AI 미연결. 사람 검토 후 승인.',snapshot_id=a['snapshot_id'])

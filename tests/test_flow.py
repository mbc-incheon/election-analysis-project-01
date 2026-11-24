import copy,hashlib,importlib.util,json,os,sqlite3,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'election-news-server'))
from core import Newsroom,sha

@pytest.fixture
def room(tmp_path):
    n=Newsroom(tmp_path)
    event=json.loads((ROOT/'fixtures'/'fallback_snapshot.json').read_text(encoding='utf-8'))
    n.receive(event)
    for r in event['rows']:
        n.add_document(dict(title='시뮬레이션 공약',publisher='가상 자료',url='demo://pledges',published_at='2024-04-01',collected_at='2026-11-20T12:00:00+09:00',document_type='campaign',election_id=r['election_id'],region_name=r['region_name'],candidate_id=r['candidate_id'],text='교통 개선을 검토하겠다는 가상 공약이다. 재원은 명시하지 않았다.',is_demo=True,rights='교육용'), 'TEST-writer')
    yield n
    n.db.close()

def make(room):return room.draft('계양구을','TEST-writer')
def test_success_export(room):
    a=make(room);assert room.validate(a)['status']=='PENDING_HUMAN'
    approved=room.approve(a['id'],'TEST-editor','자동 통합시험 전용 승인',True,True)
    assert approved['status']=='APPROVED'
    export=room.export(a['id']);assert export['snapshot_id']==a['snapshot_id']
    assert all(s['text'] in export['script'] for s in a['sentences'])
    assert export['disclosure']=='시뮬레이션 데이터'

@pytest.mark.parametrize('field,value',[('votes',123),('candidate_name','다른후보'),('candidate_id','WRONG'),('region_name','부산'),('baseline_at','2025-01-01'),('vote_share',99),('count_rate',99)])
def test_mismatched_fields_block(room,field,value):
    a=make(room);a['sentences'][0]['values'][field]=value;room.save(a)
    assert room.validate(a)['status']=='REVIEW_REQUIRED'
    with pytest.raises(ValueError):room.approve(a['id'],'TEST-editor','확인했습니다',True,True)

def test_text_number_tamper(room):
    a=make(room);a['sentences'][0]['text']='A 후보가 2.1%p 앞섰다';assert room.validate(a)['validation']['rule']=='FAIL'
def test_no_evidence(room):
    a=make(room);a['sentences']=[s for s in a['sentences'] if s['kind']=='result'];assert 'NO_PLEDGE_EVIDENCE' in room.validate(a)['validation']['errors']
def test_wrong_evidence_scope(room):
    a=make(room);a['sentences'][1]['candidate_id']='other';assert room.validate(a)['validation']['rule']=='FAIL'
def test_ai_disagreement(room):
    a=make(room);a['ai_review']={'verdict':'FAIL','model':'TEST-fixture-not-real-AI'};room.save(a)
    assert room.validate(a)['validation']['disagreement']
    with pytest.raises(ValueError):room.approve(a['id'],'TEST-editor','자동시험',True,True)
def test_independent_approval(room):
    a=make(room)
    with pytest.raises(ValueError):room.approve(a['id'],'TEST-writer','자기 승인',True,True)
def test_manual_ack_required(room):
    a=make(room)
    with pytest.raises(ValueError):room.approve(a['id'],'TEST-editor','원문 확인',True)
def test_reason_required(room):
    a=make(room)
    with pytest.raises(ValueError):room.approve(a['id'],'TEST-editor','',True,True)
def test_unapproved_export(room):
    with pytest.raises(ValueError):room.export(make(room)['id'])
def test_correction_revokes(room):
    a=make(room);room.approve(a['id'],'TEST-editor','자동시험',True,True)
    room.retire(a['sentences'][1]['evidence_ids'][0],'TEST-editor')
    assert room.get(a['id'])['status']=='REVIEW_REQUIRED'
    with pytest.raises(ValueError):room.export(a['id'])
def test_duplicate_receive(room):
    e=room.latest();e.pop('snapshot_id');assert room.receive(e) is False
def test_search_scope(room):
    assert room.search('교통','계양구을','DEMO-0-0')
    assert room.search('교통','부산','DEMO-0-0')==[]
    assert room.search('교통','계양구을','DEMO-0-0',demo=False)==[]
def test_audit_chain(room):
    make(room);prev='0'*64
    for _,p,h,raw in room.db.execute('SELECT * FROM audit ORDER BY id'):
        assert p==prev;assert h==sha([p,json.loads(raw)]);prev=h
    with pytest.raises(sqlite3.IntegrityError):room.db.execute('DELETE FROM audit')
def test_snapshot_pinned(room):
    a=make(room);e=room.latest();e.pop('snapshot_id');e['sequence']=999;e['rows'][0]['votes']=1;room.receive(e)
    assert room.validate(a)['validation']['rule']=='PASS'
def test_neutrality(room):
    a=make(room);a['title']='A 후보 필승';assert 'NEUTRALITY' in room.validate(a)['validation']['errors']
def test_durability(room):
    a=make(room);n=Newsroom(room.root);assert n.get(a['id'])==a;n.db.close()

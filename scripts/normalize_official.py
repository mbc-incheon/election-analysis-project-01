"""Aggregate leaf polling records only, preserving every raw row index."""
import csv,hashlib,json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/'data'/'official_raw'/'NEC_NA22_20240410.csv'
allrows=list(csv.DictReader(raw.read_text(encoding='cp949').splitlines()))
rows=[dict(original_row_number=i+2,**r) for i,r in enumerate(allrows) if r['시도명']=='인천광역시']
out=ROOT/'data'/'clean';out.mkdir(exist_ok=True)
with (out/'incheon_polling_rows.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
special={'선거인수','투표수','무효 투표수','기권자수'}
districts=defaultdict(list)
for r in rows:districts[r['선거구명']].append(r)
results=[];checks=[]
for district,rr in sorted(districts.items()):
    counts=defaultdict(int);lineage=defaultdict(list)
    seen=set(); repeated_keys=[]
    for r in rr:
        key=(r['법정읍면동명'],r['투표구명'],r['후보자'])
        if key in seen:repeated_keys.append(key)
        seen.add(key)
        counts[r['후보자']]+=int(r['득표수'].replace(',',''));lineage[r['후보자']].append(r['original_row_number'])
    valid=sum(v for c,v in counts.items() if c not in special)
    assert valid+counts['무효 투표수']==counts['투표수'],district
    # A national election turnout denominator may include exceptional adjustments.
    # We report the exact arithmetic check rather than inventing official turnout.
    checks.append(dict(region=district,votes_balanced=True,eligible=counts['선거인수'],ballots=counts['투표수'],invalid=counts['무효 투표수'],valid=valid,abstention=counts['기권자수'],eligible_balance=counts['선거인수']==counts['투표수']+counts['기권자수'],repeated_composite_keys=len(repeated_keys),review_required=True))
    for label,votes in sorted(counts.items()):
        if label in special:continue
        party,name=label.rsplit(' ',1)
        cid='IC24-'+hashlib.sha256((district+'|'+label).encode()).hexdigest()[:10]
        results.append(dict(row_id=cid+'-final',election_id='KR-20240410-NA22',province='인천',original_province='인천광역시',region_id='IC24-'+hashlib.sha256(district.encode()).hexdigest()[:8],region_name=district,candidate_id=cid,candidate_name=name,party=party,votes=votes,valid_votes=valid,vote_share=round(votes/valid*100,2),count_rate=None,turnout=None,election_date='2024-04-10',baseline_at=None,stage='FINAL_FILE_AGGREGATION',review_status='REVIEW_REQUIRED',is_demo=False,source_url='https://www.data.go.kr/data/15025527/fileData.do',source_file=raw.name,source_rows=lineage[label]))
(out/'incheon_final_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
resource=ROOT/'election-news-server'/'reference_data';resource.mkdir(exist_ok=True)
(resource/'incheon_final_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
csvrows=[{k:v for k,v in r.items() if k!='source_rows'} for r in results]
with (out/'incheon_final_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
(out/'normalization_log.json').write_text(json.dumps(dict(encoding='cp949 to UTF-8',source_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),source_count=len(allrows),incheon_count=len(rows),district_count=len(districts),candidate_count=len(results),rules=['retain source row numbers','exclude four summary labels from candidate counts','do not fabricate result timestamp or official turnout','vote share denominator is sum of valid candidate votes','same polling label may recur with different values, retain all occurrences and require human cross-check before publication'],checks=checks),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(polling_rows=len(rows),districts=len(districts),candidates=len(results),all_vote_balances=all(c['votes_balanced'] for c in checks)),ensure_ascii=False))

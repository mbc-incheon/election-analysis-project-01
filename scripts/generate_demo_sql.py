"""Generate reproducible INSERT statements using the application's own contracts.

All data and timestamps are fixtures. No editorial approval is created.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'election-news-server'))
import core


def main():
    core.now = lambda: '2026-11-24T00:00:00+09:00'
    core.secrets.token_hex = lambda n: 'SQL-DEMO-ARTICLE-001'
    with tempfile.TemporaryDirectory() as folder:
        room = core.Newsroom(folder)
        try:
            event = json.loads((ROOT / 'fixtures/fallback_snapshot.json').read_text(encoding='utf-8'))
            event['collected_at'] = core.now()
            room.receive(event)
            for row in event['rows']:
                room.add_document(dict(
                    title=row['region_name'] + ' 가상 공약 SQL 예제',
                    publisher='VR 선거보도 시스템 가상 자료실', url='demo://sql/pledges',
                    published_at='2024-04-01', collected_at=core.now(), document_type='campaign',
                    election_id=row['election_id'], region_name=row['region_name'],
                    candidate_id=row['candidate_id'], text='교통 개선을 검토하겠다는 가상 공약이다. 재원과 일정은 명시하지 않았다.',
                    is_demo=True, rights='프로젝트 제작 가상 자료'), 'SQL-demo-seed')
            article = room.draft('계양구을', 'SQL-demo-writer')
            assert article['status'] == 'DRAFT'
            assert room.db.execute('SELECT COUNT(*) FROM approval').fetchone()[0] == 0
            # iterdump correctly escapes Korean strings, apostrophes and JSON.
            inserts = [line for line in room.db.iterdump() if line.startswith('INSERT INTO')]
            text = '\n'.join([
                '-- VR 선거보도 시스템: 시뮬레이션 전용 INSERT 예제',
                '-- Generated with scripts/generate_demo_sql.py; dates are fixed fixture values.',
                '-- Apply only to an empty database. No people or editorial approvals are invented.',
                'PRAGMA foreign_keys=ON;', 'BEGIN TRANSACTION;', *inserts, 'COMMIT;', ''])
            (ROOT / 'db/002_demo_seed.sql').write_text(text, encoding='utf-8')
        finally:
            room.db.close()
    print('Generated db/002_demo_seed.sql (DRAFT only, approval rows = 0)')


if __name__ == '__main__':
    main()

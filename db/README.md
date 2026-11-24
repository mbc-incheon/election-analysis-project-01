# DB 스크립트

실제 보도 서버의 SQLite 스키마와 동일한 5개 테이블을 생성합니다. 정규화 확장안의 테이블은 포함하지 않습니다.

| 파일 | 용도 |
| --- | --- |
| [001_schema.sql](001_schema.sql) | CREATE TABLE 5개, 승인 외래키, 감사 로그 수정·삭제 방지 트리거 |
| [002_demo_seed.sql](002_demo_seed.sql) | 가상 스냅샷·문서 청크·DRAFT 기사·초기 감사 로그 INSERT |
| [003_inspection.sql](003_inspection.sql) | 무결성·외래키·행 수·기사·근거·승인 조회 |

## 실행

프로젝트 루트에서 설치한 Python을 사용합니다. 별도 sqlite3 실행 파일은 필요하지 않습니다.

```powershell
# 빈 운영 DB 생성: start.ps1도 첫 실행 시 같은 스키마를 생성합니다.
.venv/Scripts/python.exe scripts/init_db.py

# SQL 실습·검수용 별도 DB 생성: 기존 데이터가 있으면 입력을 거부합니다.
.venv/Scripts/python.exe scripts/init_db.py --path runtime/sql-demo/news.sqlite --demo
```

sqlite3 CLI가 있는 경우 빈 DB에 `001_schema.sql` → `002_demo_seed.sql` → `003_inspection.sql` 순서로 적용할 수도 있습니다. 초기화 도구는 비어 있지 않은 DB에 예제를 넣지 않지만, SQL을 직접 실행할 때는 사용자가 대상 DB를 확인해야 합니다. 삭제·초기화 명령은 제공하지 않습니다.

`approval` 테이블은 **0건**으로 시작합니다. 사람이 승인한 것처럼 INSERT하지 않으며, 실제 서비스의 editor API에서 원문 확인·다른 작성자·검증 통과·승인 사유 조건을 확인한 뒤 저장합니다. 예제의 작성자와 기록 시각은 가상 값입니다.

`002_demo_seed.sql`은 앱의 `Newsroom` 계약으로 생성합니다. 재생성은 `python scripts/generate_demo_sql.py`입니다. 생성 파일은 스냅샷 1건, 청크 6건, 기사 1건과 해시 연결된 감사 기록을 담습니다. 원문 메타데이터와 본문은 예제 청크 JSON에 포함하며 실제 수집 원본을 대신하지 않습니다.

원본 파일과 사용자 토큰 해시는 파일로 관리합니다. `users.json`·실행 DB·토큰은 커밋하지 않습니다. SQL과 `election-news-server/schema.sql`이 일치하는지, 예제 기사를 앱에서 검증할 수 있는지 테스트합니다.

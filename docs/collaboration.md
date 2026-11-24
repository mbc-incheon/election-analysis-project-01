# 형상관리와 협업 기록

이 문서는 실제 Git 기록과 앞으로 적용할 협업 절차를 구분합니다. 참여자·승인자·PR 리뷰를 소급 작성하지 않습니다.

## 실제 변경 기록

- [저장소 커밋 기록](https://github.com/mbc-incheon/election-analysis-project-01/commits/main/)
- [산출물 7종과 README 등록 커밋 76498fb](https://github.com/mbc-incheon/election-analysis-project-01/commit/76498fb)
- [실행 서비스와 SQL 검증 통합 커밋 961bf1a](https://github.com/mbc-incheon/election-analysis-project-01/commit/961bf1a)
- [기존 실행 코드 기준 커밋 3e54981](https://github.com/mbc-incheon/Real-time-Election-News/commit/3e549811f715f8839001f5cd9f5dac65b25ed437)
- 2026-11-24 통합은 위 실행 코드의 로컬 후속 수정본을 가져오고, SQL·테스트·실행 안내·최신 산출물과 디자인을 추가합니다. 실제 통합 커밋은 위 커밋 기록에서 확인합니다.

원래 `Real-time-Election-News` 작업 폴더의 미커밋 수정은 보존했습니다. 이 저장소에 통합한 파일의 해시와 출처는 `outputs/implementation_manifest.json`으로 확인합니다. 실사용 토큰·로컬 DB·실행 중 데이터는 형상관리에서 제외합니다.

## 협업 절차

1. 작업을 요구사항 ID와 WBS ID로 연결합니다. 역할 실명은 팀이 배정합니다.
2. `feature/<작업명>` 또는 `fix/<작업명>` 브랜치에서 변경합니다.
3. 단위·SQL·통합 시험 결과와 실패 대응을 PR에 기록합니다.
4. 작성자와 다른 검토자가 코드를 확인한 뒤 병합합니다. 현재 직접 커밋을 과거 PR 리뷰로 표시하지 않습니다.
5. 기사 승인과 코드 리뷰는 별개입니다. editor는 실제 원문을 확인한 기사에만 승인 사유를 남깁니다.

PR 템플릿과 GitHub Actions 시험 설정을 추가했습니다. 설정 파일이 있다는 사실은 실제 CI 성공 또는 사람 리뷰 완료의 증빙이 아닙니다. 실행 상태는 [Actions](https://github.com/mbc-incheon/election-analysis-project-01/actions)에서 확인합니다.

## 기록 구분

| 기록 | 확인 위치 | 한계 |
| --- | --- | --- |
| 소스 버전과 변경자 | Git 커밋과 파일 diff | Git author는 실제 역할 분담이나 기사 승인 증거가 아님 |
| 자동 시험 | outputs/unit_results.xml, integration_results.json | TEST 계정 승인은 사람 편집 승인이 아님 |
| 검증·수정·승인 이력 | 실행 DB audit·approval, editor 감사 조회 | 자동 시험 기록과 실제 운영 기록을 분리 |
| 사람 역할·검토 | WBS와 실제 PR/편집 승인 기록 | 미배정·미실행 항목은 미확정으로 유지 |

기존 2026-11-20 발표·영상·시험 자료는 `outputs/archive/20261120`에 보존합니다. 최신 실행 결과는 아카이브 밖에 기록합니다.

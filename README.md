# ER Data Collector

Eternal Return 데이터를 수집하고 가공해 버전별 통계와 유저 리포트를 만드는 Docker 기반 worker 프로젝트입니다.

## Worker Roles

- `collect_raw_now`: 최신 버전 raw 매치 데이터 수집
- `collect_raw_before`: 직전 버전 raw 매치 데이터 수집
- `collect_game_info`: 게임 정보, 패치 관련 데이터, l10n 동기화
- `generate_stats_now`: 최신 버전 통계 생성
- `generate_stats_before`: 직전 버전 통계 생성
- `generate_user_report`: 유저 리포트 view 생성
- `er_db_sync_worker`: 선택된 view 컬렉션을 외부 MongoDB로 동기화

## Run

1. `app.env.example`를 복사해 `app.env`를 만듭니다.
2. `app.env`에 필요한 값을 채웁니다.
3. 프로젝트 루트에서 `docker compose up -d`를 실행합니다.

PowerShell 예시:

```powershell
Copy-Item app.env.example app.env
docker compose up -d
```

이 프로젝트의 `docker-compose.yml`은 각 서비스에서 `env_file: ./app.env`를 사용하므로, 로컬에 `app.env`만 준비되어 있으면 기존과 같은 방식으로 실행할 수 있습니다.

## Environment Variables

- 필수 값은 `app.env.example`에 주석과 placeholder로 정리되어 있습니다.
- 공개 저장소에는 `app.env.example`만 포함하고, 실제 운영용 `app.env`는 커밋하지 않습니다.
- 서비스 공통 설정은 `API_KEY`, `MONGO_INTERNAL_URI`, `MONGO_EXTERNAL_URI`를 중심으로 사용합니다.
- 일부 서비스는 `WORKER_RULE`, `DISCORD_WEBHOOK_URL`, `INGEST_API_KEY`, report 관련 변수들을 추가로 사용합니다.
- 모든 서비스를 함께 올릴 경우 `er_db_sync_worker`와 `generate_user_report`까지 동작할 수 있도록 관련 필수값도 채워야 합니다.

## Notes

- 이 저장소에는 실제 credential, webhook, 운영 DB 정보, 운영 데이터는 포함하지 않습니다.
- 현재 워킹트리는 공개용 정리에 가깝게 맞췄지만, 과거 git history에는 정리가 필요한 민감정보 흔적이 남아 있습니다.
- 공개 전에는 `HISTORY_AUDIT.md`와 `HISTORY_REWRITE_PLAN.md`를 확인해 history rewrite 또는 새 public repo 분리 여부를 결정해야 합니다.

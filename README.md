# ER Data Collector

Docker-based workers for collecting Eternal Return data, generating statistics, and building user reports.

## Active Workers

- `collect_raw_now`
- `collect_raw_before`
- `collect_game_info`
- `generate_stats_now`
- `generate_stats_before`
- `generate_user_report`

`data_sync_agent` is no longer part of the active runtime and has been moved to `archive/`.

## Run

1. Copy `.env.example` to `.env`
2. Fill in the required values
3. Run `docker compose up -d` from the repository root

PowerShell example:

```powershell
Copy-Item .env.example .env
docker compose up -d
```

All active services use `.env` through `docker-compose.yml`.

## Environment

- Keep `.env` local only
- Commit `.env.example` only
- `MONGO_URI` is used by all active workers
- logical database names are still separated even though the connection URI is unified

## Notes

- Archived or experimental modules should stay out of active deploy targets
- Review old Git history separately before publishing this repository publicly

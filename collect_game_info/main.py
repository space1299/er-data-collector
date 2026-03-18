from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Set

from common.db.client import get_client
from common.db.init import ensure_indexes
from common.logger import setup_logger
from common.webhook import send_discord_webhook
from job.collect_l10n import sync_l10n_once
from job.collect_game_info import fetch_hash_map, find_changed_hash_keys, sync_game_info_keys

import time

logger = setup_logger("collect_data_raw_main")


def _utc_now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def build_cycle_embed(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    title = f"[ER-Collector] 변경사항 {len(changes)}건"
    lines: List[str] = []

    for c in changes:
        key = c.get("key", "?")
        diff = c.get("diff", {}) or {}
        summary = diff.get("summary", "")
        dtype = diff.get("type", "")
        lines.append(f"- {key} ({dtype}) {summary}")

    text = "\n".join(lines)
    if len(text) > 1800:
        text = text[:1800] + "\n...(truncated)"

    embeds = [{
        "title": title,
        "description": f"```text\n{text}\n```",
        "color": 0x5555FF,
    }]
    return embeds


def send_cycle_webhook_if_changed(changes: List[Dict[str, Any]]) -> None:
    if not changes:
        return
    embeds = build_cycle_embed(changes)
    send_discord_webhook("", embeds=embeds)


class PeriodicJob:
    def __init__(self, name: str, interval_sec: int, fn: Callable[[], None]):
        self.name = name
        self.interval_sec = int(interval_sec)
        self.fn = fn
        self.next_run_ts = _utc_now_ts()  # 시작하자마자 1회 실행

    def maybe_run(self) -> None:
        now = _utc_now_ts()
        if now < self.next_run_ts:
            return

        start = time.time()
        try:
            self.fn()
            elapsed = time.time() - start
            self.next_run_ts = now + self.interval_sec
            logger.info(f"{self.name}: OK ({elapsed:.2f}s) next in {self.interval_sec}s")
        except Exception as e:
            elapsed = time.time() - start
            backoff = min(60, max(5, self.interval_sec // 12))
            self.next_run_ts = now + backoff
            logger.exception(f"{self.name}: FAIL ({elapsed:.2f}s) err={e} retry in {backoff}s")


class PendingKeyQueue:
    def __init__(self) -> None:
        self._queue: Deque[str] = deque()
        self._set: Set[str] = set()

    def add(self, key: str) -> None:
        if not key or key in self._set:
            return
        self._queue.append(key)
        self._set.add(key)

    def add_many(self, keys: List[str]) -> None:
        for key in keys:
            self.add(key)

    def drain(self) -> List[str]:
        if not self._queue:
            return []
        items = list(self._queue)
        self._queue.clear()
        self._set.clear()
        return items

    def __len__(self) -> int:
        return len(self._queue)


class GameInfoSyncState:
    def __init__(self) -> None:
        self.last_hash_map: Optional[Dict[str, Any]] = None
        self.pending = PendingKeyQueue()
        self.short_ticks = 0


def run_scheduler_loop(
    *,
    tick_sec: int,
    jobs: List[PeriodicJob],
    stop_on_keyboard_interrupt: bool = True,
) -> None:
    while True:
        try:
            for job in jobs:
                job.maybe_run()
            time.sleep(tick_sec)
        except KeyboardInterrupt:
            if stop_on_keyboard_interrupt:
                logger.info("KeyboardInterrupt 감지, 스케줄러 종료")
                break
            raise


def main() -> None:
    from config import DB_URL

    while True:
        try:
            client = get_client(db_url=DB_URL)
            ensure_indexes(client)

            SHORT_HASH_SEC = 5 * 60       # 5분 -> hash check + pending
            FULL_CHECK_EVERY = 30         # 30 * 5min = 150min
            L10N_SEC = 12 * 60 * 60       # 12시간
            TICK_SEC = 10                 # 10초마다 스케줄 체크

            logger.info(
                f"start scheduler: short_hash={SHORT_HASH_SEC}s, full_every={FULL_CHECK_EVERY} ticks, "
                f"l10n={L10N_SEC}s, tick={TICK_SEC}s"
            )

            state = GameInfoSyncState()

            def run_full_check() -> None:
                hash_map = fetch_hash_map(client)
                if not hash_map:
                    return
                state.last_hash_map = hash_map
                keys = list(hash_map.keys())
                changes, failed = sync_game_info_keys(client, keys, hash_map)
                if changes:
                    send_cycle_webhook_if_changed(changes)
                state.pending.add_many(failed)

            def run_short_hash_job() -> None:
                hash_map = fetch_hash_map(client)
                if not hash_map:
                    return
                changed_keys = find_changed_hash_keys(state.last_hash_map, hash_map)
                state.last_hash_map = hash_map
                state.pending.add_many(changed_keys)

                pending_keys = state.pending.drain()
                if pending_keys:
                    changes, failed = sync_game_info_keys(client, pending_keys, hash_map)
                    if changes:
                        send_cycle_webhook_if_changed(changes)
                    state.pending.add_many(failed)

                state.short_ticks += 1
                if state.short_ticks >= FULL_CHECK_EVERY:
                    run_full_check()
                    state.short_ticks = 0

            def run_l10n_job() -> None:
                sync_l10n_once(client)

            jobs = [
                PeriodicJob("sync_game_info_short_hash", SHORT_HASH_SEC, run_short_hash_job),
                PeriodicJob("sync_l10n_once", L10N_SEC, run_l10n_job),
            ]

            run_scheduler_loop(tick_sec=TICK_SEC, jobs=jobs)
            break
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt 감지, 스케줄러 종료")
            break
        except Exception as e:
            logger.exception(f"[main] DB 연결 실패 또는 스케줄러 오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

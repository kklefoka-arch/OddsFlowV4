"""Emit picks by calling the local /picks endpoint and recording to system_health.

Run after fetch_upcoming.py so odds are fresh before emission.

Modes (Session 23d Bundle 2):
  ``--mode emit``    (default) Morning emit. system_health metric=emit_picks.
                     Part of the chain: fetch_upcoming -> emit_picks ->
                     fetch_results -> settle.
  ``--mode reemit``  Intraday re-emit chained after refresh_odds.py at 14:30
                     SAST. Same endpoint, same idempotency — supersede logic
                     in write_emit_log() handles fixtures whose classification
                     changed since the morning run. system_health metric=
                     emit_picks_reemit so the runbook can track both windows
                     separately.
"""
import argparse
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB  = r"C:\OddsFlowV4\data\oddsflow_v4.db"
URL = "http://localhost:8083/picks?days=3"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("emit", "reemit"),
        default="emit",
        help="emit = morning run; reemit = post-refresh_odds re-run",
    )
    args = parser.parse_args()
    metric = "emit_picks_reemit" if args.mode == "reemit" else "emit_picks"

    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        resp = urllib.request.urlopen(URL, timeout=30)
        data = json.loads(resp.read())
        count   = data.get("count", 0)
        emit    = data.get("emit_log", {})
        new_n   = emit.get("new", 0)
        skip_n  = emit.get("skip", 0)
        invalid = emit.get("partition_invalid", 0)
        msg = (
            f"ok: mode={args.mode} picks={count} new={new_n} "
            f"skip={skip_n} partition_invalid={invalid} ts={now_ts}"
        )
        print(
            f"Picks ({args.mode}): {count}  new={new_n}  skip={skip_n}  "
            f"partition_invalid={invalid}"
        )
    except Exception as exc:
        msg = f"error: mode={args.mode} {exc} ts={now_ts}"
        print(f"ERROR calling /picks ({args.mode}): {exc}")

    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO system_health (metric, value) VALUES (?, ?)",
        (metric, msg),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()

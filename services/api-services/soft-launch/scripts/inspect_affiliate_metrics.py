import time
import csv
import requests
import argparse
from datetime import datetime

AFF = "http://localhost:8510"


def fetch_standings():
    r = requests.get(f"{AFF}/pool/standings", timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_snapshot(affiliate_id: str, epoch_id: str):
    r = requests.get(f"{AFF}/affiliates/{affiliate_id}/metrics/snapshot/{epoch_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def inspect_snapshots(epoch_id: str, affiliate_ids: list[str], out_csv: str | None = None):
    rows = []
    for aid in affiliate_ids:
        try:
            snap = fetch_snapshot(aid, epoch_id)
        except Exception as e:
            print(f"snapshot fetch error for {aid}:", e)
            continue

        row = {
            "sample_time": datetime.utcnow().isoformat() + "Z",
            "affiliate_id": aid,
            "sales_volume": snap.get("sales_volume", 0.0),
            "unique_buyers": snap.get("unique_buyers", 0),
            "msme_referrals": snap.get("msme_referrals", 0),
            "session_cycles": snap.get("session_cycles", 0),
            "weighted_score": snap.get("weighted_score", 0.0),
            "projected_payout_zmw": snap.get("projected_payout_zmw", 0.0),
        }
        rows.append(row)
        print(f"fetched snapshot for {aid}")

    if out_csv and rows:
        keys = ["sample_time", "affiliate_id", "sales_volume", "unique_buyers", "msme_referrals", "session_cycles", "weighted_score", "projected_payout_zmw"]
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, keys)
            w.writeheader()
            w.writerows(rows)
        print("wrote", out_csv)

    return rows


def parse_args():
    p = argparse.ArgumentParser(description="Inspect affiliate weighted metrics and snapshots")
    p.add_argument("--samples", type=int, default=1, help="number of snapshot samples (ignored)")
    p.add_argument("--epoch-id", type=str, default=None, help="Epoch id to query snapshots for")
    p.add_argument("--affiliate-ids", type=str, default=None, help="Comma-separated affiliate ids to query")
    p.add_argument("--out-csv", type=str, default=None, help="CSV file to write results to")
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # determine epoch id
    epoch_id = args.epoch_id
    standings = None
    if not epoch_id:
        try:
            data = fetch_standings()
            epoch = data.get("epoch")
            epoch_id = epoch.get("id") if epoch else None
            standings = data.get("standings", [])
        except Exception as e:
            print("failed to fetch standings to obtain epoch id:", e)

    if not epoch_id:
        print("No epoch id available. Provide --epoch-id or ensure /pool/standings is reachable.")
        raise SystemExit(1)

    # determine affiliate ids to query
    affiliate_ids = []
    if args.affiliate_ids:
        affiliate_ids = [a.strip() for a in args.affiliate_ids.split(",") if a.strip()]
    elif standings is not None and len(standings) > 0:
        affiliate_ids = [s.get("affiliate_id") for s in standings]
    else:
        print("No affiliate ids provided and /pool/standings returned no entries. Provide --affiliate-ids to query specific affiliates.")
        raise SystemExit(1)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = args.out_csv or f"artifacts/affiliate_snapshots_{ts}.csv"
    rows = inspect_snapshots(epoch_id, affiliate_ids, out_csv=out)

    if not rows:
        print("No snapshots fetched — check epoch id and affiliate ids")
    else:
        for r in rows:
            print(r["affiliate_id"], "-> sales", r["sales_volume"], "buyers", r["unique_buyers"], "referrals", r["msme_referrals"], "cycles", r["session_cycles"], "score", r["weighted_score"])

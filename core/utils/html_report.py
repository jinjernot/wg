import glob, json, os, calendar, pytz
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from collections import defaultdict


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_trades(trade_history_dir):
    pattern = os.path.join(trade_history_dir, "*_noones_normalized_trades_*.json")
    newest = {}
    for f in glob.glob(pattern):
        parts = os.path.basename(f).split("_normalized_trades_")
        if len(parts) == 2:
            key, date_str = parts[0], parts[1].replace(".json", "")
            if key not in newest or date_str > newest[key][1]:
                newest[key] = (f, date_str)
    trades = []
    for key, (fp, _) in newest.items():
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
            for r in rows:
                r["_src"] = key
            trades.extend(rows)
        except Exception:
            pass
    return trades


def _parse_dt(s, tz):
    try:
        dt = isoparse(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.utc)
        return dt.astimezone(tz)
    except Exception:
        return None


def _fmt_k(v):
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


# ── main compute ─────────────────────────────────────────────────────────────

def compute_report_data(trade_history_dir):
    mxtz = pytz.timezone("America/Mexico_City")
    now  = datetime.now(mxtz)
    raw  = _load_trades(trade_history_dir)

    ok = []
    for t in raw:
        if t.get("status") != "successful":
            continue
        dt = _parse_dt(t.get("completed_at"), mxtz)
        if dt is None:
            continue
        t["_dt"] = dt
        ok.append(t)

    ok.sort(key=lambda t: t["_dt"])
    mxn = [t for t in ok if (t.get("fiat_currency_code") or "").upper() == "MXN"]

    # KPIs
    total_vol  = sum(float(t.get("fiat_amount_requested") or 0) for t in mxn)
    total_cnt  = len(ok)
    avg_size   = total_vol / len(mxn) if mxn else 0
    uniq_buyers= len(set(t.get("buyer") for t in ok if t.get("buyer")))
    max_trade  = max((float(t.get("fiat_amount_requested") or 0) for t in mxn), default=0)

    # Duration (minutes)
    durations = []
    for t in ok:
        s = _parse_dt(t.get("started_at"), mxtz)
        e = _parse_dt(t.get("ended_at"), mxtz)
        if s and e and e > s:
            durations.append((e - s).total_seconds() / 60)
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    # Daily (last 90 days)
    cutoff = now - timedelta(days=90)
    d_vol, d_cnt = defaultdict(float), defaultdict(int)
    for t in mxn:
        if t["_dt"] >= cutoff:
            day = t["_dt"].strftime("%Y-%m-%d")
            d_vol[day] += float(t.get("fiat_amount_requested") or 0)
            d_cnt[day] += 1

    sorted_days = sorted(d_vol)
    daily_labels = [d[5:] for d in sorted_days]          # MM-DD
    daily_vols   = [round(d_vol[d], 2) for d in sorted_days]
    daily_counts = [d_cnt[d] for d in sorted_days]

    # 7-day MA
    ma7 = []
    for i in range(len(daily_vols)):
        w = daily_vols[max(0, i-6): i+1]
        ma7.append(round(sum(w)/len(w), 2))

    # Monthly
    monthly = defaultdict(lambda: {"v": 0.0, "c": 0})
    for t in mxn:
        mk = t["_dt"].strftime("%Y-%m")
        monthly[mk]["v"] += float(t.get("fiat_amount_requested") or 0)
        monthly[mk]["c"] += 1

    m_sorted = sorted(monthly)
    monthly_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in m_sorted]
    monthly_vols   = [round(monthly[m]["v"], 2) for m in m_sorted]
    monthly_counts = [monthly[m]["c"] for m in m_sorted]

    # Account comparison
    acc = defaultdict(lambda: {"v": 0.0, "c": 0})
    for t in mxn:
        name = t.get("account_name") or t.get("_src") or "Unknown"
        name = name.replace("_", " ").strip()
        acc[name]["v"] += float(t.get("fiat_amount_requested") or 0)
        acc[name]["c"] += 1
    acc_labels   = list(acc)
    acc_vols_data= [round(acc[a]["v"], 2) for a in acc_labels]
    acc_cnts_data= [acc[a]["c"] for a in acc_labels]

    # Top buyers
    b_vol, b_cnt = defaultdict(float), defaultdict(int)
    for t in mxn:
        b = t.get("buyer") or "Unknown"
        b_vol[b] += float(t.get("fiat_amount_requested") or 0)
        b_cnt[b] += 1
    top_buyers = sorted(b_vol.items(), key=lambda x: x[1], reverse=True)[:12]
    tb_labels = [b[0] for b in top_buyers]
    tb_vols   = [round(b[1], 2) for b in top_buyers]
    tb_cnts   = [b_cnt[b[0]] for b in top_buyers]
    tb_avgs   = [round(b[1]/b_cnt[b[0]], 0) for b in top_buyers]

    # Payment methods
    pm_vol, pm_cnt = defaultdict(float), defaultdict(int)
    for t in mxn:
        pm = t.get("payment_method_name") or "Unknown"
        pm_vol[pm] += float(t.get("fiat_amount_requested") or 0)
        pm_cnt[pm] += 1
    pm_sorted = sorted(pm_vol.items(), key=lambda x: x[1], reverse=True)[:8]
    pm_labels  = [p[0] for p in pm_sorted]
    pm_vols_d  = [round(p[1], 2) for p in pm_sorted]
    pm_cnts_d  = [pm_cnt[p[0]] for p in pm_sorted]

    # Crypto split
    crypto_vol = defaultdict(float)
    for t in ok:
        c = (t.get("crypto_currency_code") or "Other").upper()
        crypto_vol[c] += float(t.get("fiat_amount_requested") or 0)
    crypto_labels = list(crypto_vol)
    crypto_vols_d = [round(crypto_vol[c], 2) for c in crypto_labels]

    # Hour of day
    h_cnt, h_vol = defaultdict(int), defaultdict(float)
    for t in mxn:
        h = t["_dt"].hour
        h_cnt[h] += 1
        h_vol[h] += float(t.get("fiat_amount_requested") or 0)
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    hour_counts = [h_cnt[h] for h in range(24)]
    hour_vols_h = [round(h_vol[h], 2) for h in range(24)]

    # Day of week
    dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    dow_cnt, dow_vol2 = defaultdict(int), defaultdict(float)
    for t in mxn:
        d = t["_dt"].weekday()
        dow_cnt[d] += 1
        dow_vol2[d] += float(t.get("fiat_amount_requested") or 0)
    dow_counts = [dow_cnt[i] for i in range(7)]
    dow_vols_d = [round(dow_vol2[i], 2) for i in range(7)]

    # Trade size histogram
    buckets = [(0,500),(500,1000),(1000,2000),(2000,5000),(5000,10000),(10000,20000),(20000,1e18)]
    blabels = ["<$500","$500-1K","$1K-2K","$2K-5K","$5K-10K","$10K-20K",">$20K"]
    amounts = [float(t.get("fiat_amount_requested") or 0) for t in mxn]
    bucket_counts = [sum(1 for a in amounts if lo <= a < hi) for lo, hi in buckets]

    # Recent 25 trades
    recent25 = sorted(ok, key=lambda t: t["_dt"], reverse=True)[:25]
    recent_rows = []
    for t in recent25:
        recent_rows.append({
            "date": t["_dt"].strftime("%b %d %H:%M"),
            "buyer": t.get("buyer") or "—",
            "method": t.get("payment_method_name") or "—",
            "amount": f'${float(t.get("fiat_amount_requested") or 0):,.0f}',
            "crypto": (t.get("crypto_currency_code") or "—").upper(),
            "account": (t.get("account_name") or t.get("_src") or "—").replace("_"," "),
        })

    period_str = f"{ok[0]['_dt'].strftime('%b %d, %Y')} – {ok[-1]['_dt'].strftime('%b %d, %Y')}" if ok else "N/A"

    return {
        "meta": {
            "generated": now.strftime("%B %d, %Y at %I:%M %p"),
            "period": period_str,
            "total_trades": total_cnt,
            "total_vol": total_vol,
            "avg_size": avg_size,
            "max_trade": max_trade,
            "uniq_buyers": uniq_buyers,
            "avg_duration": avg_duration,
            "total_vol_fmt": _fmt_k(total_vol),
            "avg_size_fmt": _fmt_k(avg_size),
            "max_trade_fmt": _fmt_k(max_trade),
        },
        "daily_labels": daily_labels, "daily_vols": daily_vols,
        "daily_counts": daily_counts, "ma7": ma7,
        "monthly_labels": monthly_labels, "monthly_vols": monthly_vols,
        "monthly_counts": monthly_counts,
        "acc_labels": acc_labels, "acc_vols": acc_vols_data, "acc_cnts": acc_cnts_data,
        "tb_labels": tb_labels, "tb_vols": tb_vols, "tb_cnts": tb_cnts, "tb_avgs": tb_avgs,
        "pm_labels": pm_labels, "pm_vols": pm_vols_d, "pm_cnts": pm_cnts_d,
        "crypto_labels": crypto_labels, "crypto_vols": crypto_vols_d,
        "hour_labels": hour_labels, "hour_counts": hour_counts, "hour_vols": hour_vols_h,
        "dow_names": dow_names, "dow_counts": dow_counts, "dow_vols": dow_vols_d,
        "bucket_labels": blabels, "bucket_counts": bucket_counts,
        "recent_rows": recent_rows,
    }

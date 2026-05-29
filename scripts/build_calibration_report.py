#!/usr/bin/env python3
"""V2 分档校准分析报告生成器。输出 HTML 到 docs/calibration_report.html"""

import json
import csv
import numpy as np
from scipy import stats
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def load_data():
    with open(PROJECT_ROOT / "data/output/v2_scoring.json") as f:
        v2 = json.load(f)
    with open(PROJECT_ROOT / "data/output/dashboard_view.json") as f:
        dv = json.load(f)

    bucket_stats = dv.get("scoreBucketStats", [])
    date_index = dv.get("dateIndex", {})

    actual_by_date = {}
    for r in v2.get("dailyResults", []):
        d = r.get("date", "")
        actual_by_date[d] = {"next1dExcess": r.get("next1dExcess"), "next1dAbs": r.get("next1dAbs")}

    actual_3d, actual_5d = {}, {}
    with open(PROJECT_ROOT / "data/output/history_summary.csv") as f:
        for row in csv.DictReader(f):
            d = row.get("date", "")
            if row.get("next_3d_return"):
                actual_3d[d] = float(row["next_3d_return"])
            if row.get("next_5d_return"):
                actual_5d[d] = float(row["next_5d_return"])

    return bucket_stats, date_index, actual_by_date, actual_3d, actual_5d


def build_rows(bucket_stats, date_index, actual_by_date, actual_3d, actual_5d):
    rows = []
    for bs in bucket_stats:
        d = bs.get("date", "")
        t1 = bs.get("t1", {})
        sw1 = bs.get("stateWeightedT1", {})
        act = actual_by_date.get(d)
        if not act or act.get("next1dExcess") is None:
            continue

        pred_excess = (sw1 or t1).get("avgExcess")
        pred_abs = (sw1 or t1).get("avgAbsReturn")
        pred_excess_wr = (sw1 or t1).get("excessPosRate")
        pred_abs_wr = (sw1 or t1).get("absPosRate")

        de = date_index.get(d, {})
        ws = de.get("windowStats", [])
        path_avgRet = ws[0].get("avgReturn") if len(ws) > 0 else None
        path_wr = ws[0].get("winRate") if len(ws) > 0 else None

        cases = de.get("similarCases", [])
        case_1d = [c.get("next1dReturn") for c in cases if c.get("next1dReturn") is not None]
        case_3d = [c.get("next3dReturn") for c in cases if c.get("next3dReturn") is not None]
        case_5d = [c.get("next5dReturn") for c in cases if c.get("next5dReturn") is not None]

        rows.append({
            "date": d, "score": bs.get("score"), "bucket": bs.get("bucketLabel"),
            "sample_n": bs.get("sampleSize"), "n_cases": len(cases),
            "pred_excess": pred_excess, "pred_abs": pred_abs,
            "pred_excess_wr": pred_excess_wr, "pred_abs_wr": pred_abs_wr,
            "path_avgRet": path_avgRet, "path_wr": path_wr,
            "case_avg_1d": np.mean(case_1d) if case_1d else None,
            "case_avg_3d": np.mean(case_3d) if case_3d else None,
            "case_avg_5d": np.mean(case_5d) if case_5d else None,
            "case_1d_pos": sum(1 for r in case_1d if r > 0) / len(case_1d) if case_1d else None,
            "actual_1d_exc": act["next1dExcess"], "actual_1d_abs": act["next1dAbs"],
            "actual_3d_abs": actual_3d.get(d), "actual_5d_abs": actual_5d.get(d),
        })
    return [r for r in rows if abs(r["actual_1d_exc"]) < 10 and abs(r["actual_1d_abs"]) < 10]


def do_regression(pred, actual):
    mask = np.array([p is not None for p in pred]) & np.array([a is not None for a in actual])
    p = np.array(pred)[mask].astype(float)
    a = np.array(actual)[mask].astype(float)
    if len(p) < 5:
        return None
    slope, intercept, r_val, p_val, se = stats.linregress(p, a)
    ic, ic_p = stats.spearmanr(p, a)
    rmse = np.sqrt(np.mean((a - p) ** 2))
    dir_acc = np.mean((p > 0) == (a > 0))
    return {"slope": slope, "intercept": intercept, "r2": r_val**2, "p": p_val,
            "ic": ic, "ic_p": ic_p, "rmse": rmse, "dir_acc": dir_acc, "n": len(p)}


def winrate_calibration(clean, pred_wr_key, actual_key):
    valid = [r for r in clean if r.get(pred_wr_key) is not None and r.get(actual_key) is not None]
    pred_wr = np.array([r[pred_wr_key] for r in valid])
    actual_arr = np.array([r[actual_key] for r in valid])
    if len(pred_wr) < 10:
        return []
    pcts = np.percentile(pred_wr, [20, 40, 60, 80])
    bounds = [0] + list(pcts) + [1.01]
    bands = []
    for i in range(5):
        m = (pred_wr >= bounds[i]) & (pred_wr < bounds[i+1])
        n = m.sum()
        if n == 0:
            continue
        avg_pred = pred_wr[m].mean() * 100
        actual_wr = (actual_arr[m] > 0).sum() / n * 100
        bands.append({"pred_wr": round(avg_pred, 0), "actual_wr": round(actual_wr, 0), "n": int(n), "bias": round(actual_wr - avg_pred, 0)})
    return bands


def magnitude_calibration(clean, pred_key, actual_key, bands_def):
    valid = [r for r in clean if r.get(pred_key) is not None and r.get(actual_key) is not None]
    pred = np.array([r[pred_key] for r in valid])
    actual = np.array([r[actual_key] for r in valid])
    result = []
    for label, lo, hi in bands_def:
        m = (pred >= lo) & (pred < hi)
        n = m.sum()
        if n == 0:
            result.append({"label": label, "n": 0})
            continue
        avg_p = pred[m].mean()
        avg_a = actual[m].mean()
        pos = (actual[m] > 0).sum() / n * 100
        same_dir = np.mean((pred[m] > 0) == (actual[m] > 0)) * 100
        cal = round(avg_a / avg_p, 2) if abs(avg_p) > 0.01 and np.sign(avg_p) == np.sign(avg_a) else None
        result.append({"label": label, "n": int(n), "pred_avg": round(avg_p, 2), "actual_avg": round(avg_a, 2),
                        "pos_rate": round(pos, 0), "same_dir": round(same_dir, 0), "cal": cal})
    return result


def build_score_groups(clean):
    score_groups = []
    for label, cond in [
        ("≤-8", lambda s: s <= -8), ("-7~-5", lambda s: -7 <= s <= -5),
        ("-4~-2", lambda s: -4 <= s <= -2), ("-1~0", lambda s: -1 <= s <= 0),
        ("+1~+2", lambda s: 1 <= s <= 2), ("+3~+5", lambda s: 3 <= s <= 5),
        ("≥+6", lambda s: s >= 6),
    ]:
        items = [r for r in clean if cond(r["score"])]
        if not items:
            continue
        n = len(items)
        ae = np.mean([r["actual_1d_exc"] for r in items])
        aa = np.mean([r["actual_1d_abs"] for r in items])
        score_groups.append({"label": label, "n": n, "avg_exc": round(ae, 2), "avg_abs": round(aa, 2),
                              "exc_pos": round(sum(1 for r in items if r["actual_1d_exc"] > 0) / n * 100, 0),
                              "abs_pos": round(sum(1 for r in items if r["actual_1d_abs"] > 0) / n * 100, 0)})
    return score_groups


def generate_html(clean, reg_excess, reg_rows, wr_cal_excess, mag_excess, mag_abs, score_groups, daily_data_js):
    # --- core metrics ---
    r2_color = "#ef4444" if reg_excess["r2"] < 0.1 else "#22c55e"
    ic_color = "#ef4444" if reg_excess["ic"] < 0.2 else "#22c55e"
    dir_color = "#ef4444" if reg_excess["dir_acc"] < 0.55 else "#22c55e"
    beta_color = "#ef4444" if reg_excess["slope"] < 0.5 else "#22c55e"

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>V2 分档校准分析</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #e0e0e0; max-width: 1100px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #f59e0b; font-size: 20px; }}
h2 {{ color: #3b82f6; font-size: 16px; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }}
th {{ background: #16213e; color: #f59e0b; padding: 8px 12px; text-align: left; }}
td {{ padding: 6px 12px; border-bottom: 1px solid #222; }}
tr:hover {{ background: #1f2937; }}
.pos {{ color: #ef4444; }} .neg {{ color: #22c55e; }} .muted {{ color: #888; }}
.bad {{ background: rgba(239,68,68,0.15); }} .good {{ background: rgba(34,197,94,0.15); }}
.card {{ background: #16213e; border-radius: 8px; padding: 16px; margin: 12px 0; }}
.metric {{ display: inline-block; margin: 8px 20px; }}
.metric .value {{ font-size: 24px; font-weight: bold; }}
.metric .label {{ font-size: 12px; color: #888; }}
canvas {{ margin: 12px 0; }}
.note {{ font-size: 12px; color: #888; margin: 8px 0; line-height: 1.6; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
<h1>V2 分档校准分析 — 铂力特 (688333.SH)</h1>
<p class="note">样本: {len(clean)} 个交易日（去极值 &plusmn;10%） | 数据来源: scoreBucketStats 分档统计 + v2_scoring 实际收益</p>

<h2>1. 核心结论</h2>
<div class="card">
<div class="metric"><div class="value" style="color:{r2_color}">{reg_excess['r2']:.3f}</div><div class="label">分档超额 R&sup2;</div></div>
<div class="metric"><div class="value" style="color:{ic_color}">{reg_excess['ic']:.3f}</div><div class="label">Spearman IC</div></div>
<div class="metric"><div class="value" style="color:{dir_color}">{reg_excess['dir_acc']*100:.0f}%</div><div class="label">方向准确率</div></div>
<div class="metric"><div class="value" style="color:{beta_color}">&beta;={reg_excess['slope']:.2f}</div><div class="label">幅度校准(1.0=完美)</div></div>
</div>
<p class="note">
<b>&beta;={reg_excess['slope']:.2f}</b>: 分档预测每1%超额，实际只对应{reg_excess['slope']:.2f}%，预测幅度严重偏大。<br>
<b>R&sup2;={reg_excess['r2']:.3f}</b>: 分档预测对实际超额的解释力不到1%。<br>
<b>方向准确率{reg_excess['dir_acc']*100:.0f}%</b>: 和抛硬币差不多。
</p>

<h2>2. 回归校准</h2>
<table>
<tr><th>预测源</th><th>N</th><th>&beta;</th><th>&alpha;</th><th>R&sup2;</th><th>IC</th><th>IC p</th><th>方向</th><th>RMSE</th></tr>
""")

    for name, rg in reg_rows:
        if rg is None:
            continue
        color = "good" if rg["ic"] > 0.2 and rg["ic_p"] < 0.05 else "bad" if rg["ic"] < 0 else ""
        parts.append(f'<tr class="{color}"><td>{name}</td><td>{rg["n"]}</td><td>{rg["slope"]:.2f}</td><td>{rg["intercept"]:+.2f}%</td><td>{rg["r2"]:.3f}</td><td>{rg["ic"]:.3f}</td><td>{rg["ic_p"]:.3f}</td><td>{rg["dir_acc"]*100:.0f}%</td><td>{rg["rmse"]:.2f}%</td></tr>\n')

    parts.append("""</table>

<h2>3. 胜率校准 — 预测超额正率 vs 实际正率</h2>
<p class="note">完美校准: 预测正率X%，实际也约X%。反向 = 预测高正率的档，实际正率反而低。</p>
<table>
<tr><th>预测超额正率档</th><th>N</th><th>预测正率</th><th>实际正率</th><th>偏差</th></tr>
""")

    for b in wr_cal_excess:
        color = "good" if abs(b["bias"]) < 10 else "bad"
        bias_cls = "pos" if b["bias"] > 0 else "neg"
        parts.append(f'<tr class="{color}"><td>{b["pred_wr"]:.0f}%档</td><td>{b["n"]}</td><td>{b["pred_wr"]:.0f}%</td><td>{b["actual_wr"]:.0f}%</td><td class="{bias_cls}">{b["bias"]:+.0f}%</td></tr>\n')

    parts.append("""</table>
<canvas id="wrChart" height="200"></canvas>

<h2>4. 量级校准 — 预测超额幅度 vs 实际幅度</h2>
<table>
<tr><th>量级带</th><th>N</th><th>预测超额</th><th>实际超额</th><th>校准度</th><th>实际正率</th><th>方向一致</th></tr>
""")

    for b in mag_excess:
        cal_str = f'{b["cal"]}x' if b.get("cal") is not None else ("方向错" if b.get("n", 0) > 0 else "--")
        color = "good" if b.get("cal") is not None and 0.7 <= b["cal"] <= 1.3 else "bad" if b.get("n", 0) > 0 else ""
        pred_cls = "neg" if b.get("pred_avg", 0) < 0 else "pos"
        act_cls = "neg" if b.get("actual_avg", 0) < 0 else "pos"
        if b.get("n", 0) > 0:
            parts.append(f'<tr class="{color}"><td>{b["label"]}</td><td>{b["n"]}</td><td class="{pred_cls}">{b["pred_avg"]:+.2f}%</td><td class="{act_cls}">{b["actual_avg"]:+.2f}%</td><td>{cal_str}</td><td>{b["pos_rate"]:.0f}%</td><td>{b["same_dir"]:.0f}%</td></tr>\n')
        else:
            parts.append(f'<tr><td>{b["label"]}</td><td>0</td><td colspan="6">--</td></tr>\n')

    parts.append("""</table>

<h2>5. 量级校准 — 预测个股幅度 vs 实际个股幅度</h2>
<table>
<tr><th>量级带</th><th>N</th><th>预测个股</th><th>实际个股</th><th>校准度</th><th>实际正率</th><th>方向一致</th></tr>
""")

    for b in mag_abs:
        cal_str = f'{b["cal"]}x' if b.get("cal") is not None else ("方向错" if b.get("n", 0) > 0 else "--")
        color = "good" if b.get("cal") is not None and 0.7 <= b["cal"] <= 1.3 else "bad" if b.get("n", 0) > 0 else ""
        pred_cls = "neg" if b.get("pred_avg", 0) < 0 else "pos"
        act_cls = "neg" if b.get("actual_avg", 0) < 0 else "pos"
        if b.get("n", 0) > 0:
            parts.append(f'<tr class="{color}"><td>{b["label"]}</td><td>{b["n"]}</td><td class="{pred_cls}">{b["pred_avg"]:+.2f}%</td><td class="{act_cls}">{b["actual_avg"]:+.2f}%</td><td>{cal_str}</td><td>{b["pos_rate"]:.0f}%</td><td>{b["same_dir"]:.0f}%</td></tr>\n')
        else:
            parts.append(f'<tr><td>{b["label"]}</td><td>0</td><td colspan="6">--</td></tr>\n')

    parts.append("""</table>

<h2>6. 按评分分组 — 实际收益</h2>
<table>
<tr><th>评分</th><th>N</th><th>实际超额</th><th>实际个股</th><th>超额正率</th><th>个股正率</th></tr>
""")

    for g in score_groups:
        exc_cls = "pos" if g["avg_exc"] > 0 else "neg"
        abs_cls = "pos" if g["avg_abs"] > 0 else "neg"
        parts.append(f'<tr><td>{g["label"]}</td><td>{g["n"]}</td><td class="{exc_cls}">{g["avg_exc"]:+.2f}%</td><td class="{abs_cls}">{g["avg_abs"]:+.2f}%</td><td>{g["exc_pos"]:.0f}%</td><td>{g["abs_pos"]:.0f}%</td></tr>\n')

    parts.append("""</table>

<h2>7. 散点图 — 预测超额 vs 实际超额</h2>
<canvas id="scatterChart" height="350"></canvas>

<h2>8. 逐日校准明细</h2>
<div style="max-height:500px;overflow:auto">
<table>
<tr><th>日期</th><th>评分</th><th>预测超额</th><th>实际超额</th><th>误差</th><th>预测个股</th><th>实际个股</th><th>误差</th><th>超额&check;</th><th>个股&check;</th></tr>
""")

    for r in sorted(clean, key=lambda x: x["date"]):
        exc_err = round(r["actual_1d_exc"] - (r["pred_excess"] or 0), 2) if r["pred_excess"] is not None else None
        abs_err = round(r["actual_1d_abs"] - (r["pred_abs"] or 0), 2) if r["pred_abs"] is not None else None
        exc_hit = "✓" if r["pred_excess"] is not None and ((r["pred_excess"] > 0 and r["actual_1d_exc"] > 0) or (r["pred_excess"] <= 0 and r["actual_1d_exc"] <= 0)) else "✗"
        abs_hit = "✓" if r["pred_abs"] is not None and ((r["pred_abs"] > 0 and r["actual_1d_abs"] > 0) or (r["pred_abs"] <= 0 and r["actual_1d_abs"] <= 0)) else "✗"
        pe = f'{r["pred_excess"]:+.2f}%' if r["pred_excess"] is not None else "--"
        pa = f'{r["pred_abs"]:+.2f}%' if r["pred_abs"] is not None else "--"
        exc_cls = "pos" if r["actual_1d_exc"] > 0 else "neg"
        abs_cls = "pos" if r["actual_1d_abs"] > 0 else "neg"
        parts.append(f'<tr><td>{r["date"]}</td><td>{r["score"]}</td><td>{pe}</td><td class="{exc_cls}">{r["actual_1d_exc"]:+.2f}%</td><td>{exc_err:+.2f}%</td><td>{pa}</td><td class="{abs_cls}">{r["actual_1d_abs"]:+.2f}%</td><td>{abs_err:+.2f}%</td><td>{exc_hit}</td><td>{abs_hit}</td></tr>\n')

    parts.append(f"""</table></div>

<script>
const daily = {daily_data_js};
const scatterData = daily.filter(d => d.pred_excess !== null).map(d => ({{x: d.pred_excess, y: d.actual_exc}}));

new Chart(document.getElementById('scatterChart').getContext('2d'), {{
  type: 'scatter',
  data: {{ datasets: [
    {{ label: '预测vs实际', data: scatterData, backgroundColor: 'rgba(59,130,246,0.6)', pointRadius: 4 }},
  ]}},
  options: {{
    plugins: {{ annotation: {{ annotations: {{
      diag: {{ type: 'line', xMin: -4, xMax: 4, yMin: -4, yMax: 4, borderColor: '#22c55e', borderWidth: 1, borderDash: [5,5] }}
    }}}}}},
    scales: {{
      x: {{ title: {{ display: true, text: '预测超额(%)', color: '#888' }}, grid: {{ color: '#222' }}, ticks: {{ color: '#888' }} }},
      y: {{ title: {{ display: true, text: '实际超额(%)', color: '#888' }}, grid: {{ color: '#222' }}, ticks: {{ color: '#888' }} }}
    }}
  }}
}});

const wrData = {json.dumps(wr_cal_excess)};
new Chart(document.getElementById('wrChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: wrData.map(d => d.pred_wr + '%'),
    datasets: [
      {{ label: '预测正率', data: wrData.map(d => d.pred_wr), backgroundColor: 'rgba(59,130,246,0.6)' }},
      {{ label: '实际正率', data: wrData.map(d => d.actual_wr), backgroundColor: 'rgba(245,158,11,0.6)' }},
    ]
  }},
  options: {{
    scales: {{
      x: {{ grid: {{ color: '#222' }}, ticks: {{ color: '#888' }} }},
      y: {{ grid: {{ color: '#222' }}, ticks: {{ color: '#888' }}, title: {{ display: true, text: '正率(%)', color: '#888' }} }}
    }}
  }}
}});
</script>
</body>
</html>""")

    return "".join(parts)


def main():
    bucket_stats, date_index, actual_by_date, actual_3d, actual_5d = load_data()
    clean = build_rows(bucket_stats, date_index, actual_by_date, actual_3d, actual_5d)

    reg_excess = do_regression([r["pred_excess"] for r in clean], [r["actual_1d_exc"] for r in clean])
    reg_abs = do_regression([r["pred_abs"] for r in clean if r["pred_abs"] is not None], [r["actual_1d_abs"] for r in clean if r["pred_abs"] is not None])
    reg_case1d = do_regression([r["case_avg_1d"] for r in clean if r["case_avg_1d"] is not None], [r["actual_1d_abs"] for r in clean if r["case_avg_1d"] is not None])
    reg_case3d = do_regression([r["case_avg_3d"] for r in clean if r["case_avg_3d"] is not None], [r["actual_3d_abs"] for r in clean if r["case_avg_3d"] is not None])
    reg_case5d = do_regression([r["case_avg_5d"] for r in clean if r["case_avg_5d"] is not None], [r["actual_5d_abs"] for r in clean if r["case_avg_5d"] is not None])
    reg_score_exc = do_regression([r["score"] for r in clean], [r["actual_1d_exc"] for r in clean])
    reg_score_abs = do_regression([r["score"] for r in clean], [r["actual_1d_abs"] for r in clean])

    reg_rows = [
        ("分档→超额", reg_excess), ("分档→个股", reg_abs),
        ("相似案例T+1", reg_case1d), ("相似案例T+3", reg_case3d), ("相似案例T+5", reg_case5d),
        ("评分→超额", reg_score_exc), ("评分→个股", reg_score_abs),
    ]

    wr_cal_excess = winrate_calibration(clean, "pred_excess_wr", "actual_1d_exc")

    mag_excess = magnitude_calibration(clean, "pred_excess", "actual_1d_exc", [
        ("强烈看空(<-2%)", -999, -2), ("温和看空(-2%~0.5%)", -2, -0.5),
        ("中性(-0.5%~+0.5%)", -0.5, 0.5), ("温和看多(+0.5%~+2%)", 0.5, 2),
        ("强烈看多(>+2%)", 2, 999)])

    mag_abs = magnitude_calibration(clean, "pred_abs", "actual_1d_abs", [
        ("预测大跌(<-2%)", -999, -2), ("预测中跌(-2%~-0.5%)", -2, -0.5),
        ("预测微跌(-0.5%~0%)", -0.5, 0), ("预测微红(0%~+1%)", 0, 1),
        ("预测小红(+1%~+3%)", 1, 3), ("预测大红(>+3%)", 3, 999)])

    score_groups = build_score_groups(clean)

    daily_data_js = json.dumps([{
        "date": r["date"], "score": r["score"],
        "pred_excess": round(r["pred_excess"], 2) if r["pred_excess"] is not None else None,
        "pred_abs": round(r["pred_abs"], 2) if r["pred_abs"] is not None else None,
        "actual_exc": round(r["actual_1d_exc"], 2), "actual_abs": round(r["actual_1d_abs"], 2),
    } for r in sorted(clean, key=lambda x: x["date"])])

    html = generate_html(clean, reg_excess, reg_rows, wr_cal_excess, mag_excess, mag_abs, score_groups, daily_data_js)

    out = PROJECT_ROOT / "docs" / "calibration_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK] 报告已生成: {out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()

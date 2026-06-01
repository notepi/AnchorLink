"""
超额收益分档回测 — 数据生成（v2: Q×G 二维网格）
================================================
将 5日超额、10日超额、当日超额按百分位分 Q 档（位置）和 G 档（方向），
对每个交易日计算未来 20 天最高/最低价收益，
输出每日数据 CSV 和分档阈值 JSON。

注：20日内最高/最低价退出为理论上界，实际收益会更低。

输入（只读）：
  - data/price/normalized/market_data_normalized.parquet
  - data/output/history_rolling_metrics.csv
  - data/output/history_summary.csv

输出：
  - data/output/excess_grade_daily.csv
  - data/output/excess_grade_thresholds.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
PRICE_PARQUET = ROOT / "data/price/normalized/market_data_normalized.parquet"
ROLLING_CSV = ROOT / "data/output/history_rolling_metrics.csv"
SUMMARY_CSV = ROOT / "data/output/history_summary.csv"
DAILY_CSV = ROOT / "docs/excess_backtest/excess_grade_daily.csv"
THRESHOLDS_JSON = ROOT / "docs/excess_backtest/excess_grade_thresholds.json"

ANCHOR_CODE = "688333.SH"
MAX_HOLD = 20

# Q 维度：5 档（位置）
Q_DEFS = [
    (1, "极冷", 0, 20),
    (2, "偏冷", 20, 40),
    (3, "中性", 40, 60),
    (4, "偏热", 60, 80),
    (5, "极热", 80, 100),
]

# G 维度：5 档（方向）
G_DEFS = [
    (1, "大降", 0, 20),
    (2, "小降", 20, 40),
    (3, "稳定", 40, 60),
    (4, "小升", 60, 80),
    (5, "大升", 80, 100),
]

Q_LABEL = {g: lbl for g, lbl, _, _ in Q_DEFS}
G_LABEL = {g: lbl for g, lbl, _, _ in G_DEFS}

INDICATORS = {
    "excess_5d": {"label": "5日超额"},
    "excess_10d": {"label": "10日超额"},
    "daily_excess": {"label": "当日超额"},
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def pct_threshold(series: pd.Series, p: float) -> float:
    vals = series.dropna().sort_values()
    if vals.empty:
        return 0.0
    return float(vals.iloc[int(len(vals) * p / 100)])


# ── 数据加载与合并 ────────────────────────────────────────────────────────────

def load_and_merge() -> pd.DataFrame:
    price_df = pd.read_parquet(PRICE_PARQUET)
    blt = price_df[price_df["ts_code"] == ANCHOR_CODE].copy()
    blt = blt.sort_values("trade_date").reset_index(drop=True)
    blt["date_str"] = blt["trade_date"].dt.strftime("%Y%m%d")
    blt.set_index("trade_date", inplace=True)

    rolling = pd.read_csv(ROLLING_CSV)
    rolling["date_str"] = rolling["date"].astype(str)

    summary = pd.read_csv(SUMMARY_CSV)
    summary["date_str"] = summary["date"].astype(str)

    df = blt.copy()
    df["excess_5d"] = df["date_str"].map(
        dict(zip(rolling["date_str"], rolling["excess_5d"]))
    )
    df["excess_10d"] = df["date_str"].map(
        dict(zip(rolling["date_str"], rolling["excess_10d"]))
    )
    df["daily_excess"] = df["date_str"].map(
        dict(zip(summary["date_str"], summary["relative_strength_vs_industry_chain"]))
    )

    return df


# ── 前向指标预计算 ────────────────────────────────────────────────────────────

def compute_forward_metrics(df: pd.DataFrame) -> pd.DataFrame:
    highs = df["high"].values.astype(float)
    lows = df["low"].values.astype(float)
    closes = df["close"].values.astype(float)
    n = len(df)

    fwd_max_ret = [None] * n
    fwd_min_ret = [None] * n
    fwd_median_ret = [None] * n
    fwd_peak_day = [None] * n
    fwd_trough_day = [None] * n
    fwd_median_day = [None] * n
    fwd_retention = [None] * n
    tradeable = [0.0] * n

    for i in range(n - MAX_HOLD):
        window_highs = highs[i + 1 : i + MAX_HOLD + 1]
        window_lows = lows[i + 1 : i + MAX_HOLD + 1]
        window_closes = closes[i + 1 : i + MAX_HOLD + 1]
        fwd_max_ret[i] = round((float(np.max(window_highs)) / closes[i] - 1) * 100, 4)
        fwd_min_ret[i] = round((float(np.min(window_lows)) / closes[i] - 1) * 100, 4)
        fwd_peak_day[i] = int(np.argmax(window_highs)) + 1
        fwd_trough_day[i] = int(np.argmin(window_lows)) + 1
        median_price = float(np.median(window_closes))
        median_ret = round((median_price / closes[i] - 1) * 100, 4)
        fwd_median_ret[i] = median_ret
        # 最接近中位数价格的实际交易日（从后往前找，取最近的）
        price_diffs = np.abs(window_closes - median_price)
        median_idx = int(len(price_diffs) - 1 - np.argmin(price_diffs[::-1]))
        fwd_median_day[i] = median_idx + 1
        # 留存率 = 中位数收益 / 最大收益，截尾 [-2, 2]，极小分母置 None
        if fwd_max_ret[i] and fwd_max_ret[i] > 1.0:
            ret_val = round(median_ret / fwd_max_ret[i], 4)
            fwd_retention[i] = max(-2.0, min(2.0, ret_val))
        else:
            fwd_retention[i] = None
        tradeable[i] = 1.0

    df["fwd_20d_max_return"] = fwd_max_ret
    df["fwd_20d_min_return"] = fwd_min_ret
    df["fwd_20d_median_return"] = fwd_median_ret
    df["fwd_20d_peak_day"] = fwd_peak_day
    df["fwd_20d_trough_day"] = fwd_trough_day
    df["fwd_20d_median_day"] = fwd_median_day
    df["fwd_20d_retention"] = fwd_retention
    df["tradeable"] = tradeable
    return df


# ── Q 维度分档（位置） ────────────────────────────────────────────────────────

def assign_q_grades(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    thresholds = {}
    for ind_key in INDICATORS:
        series = df[ind_key] if ind_key in df.columns else pd.Series(dtype=float)
        vals = series.dropna()
        pcts = {}
        for _, _, lo, _ in Q_DEFS:
            if lo > 0:
                pcts[f"P{lo}"] = pct_threshold(vals, lo)
        thresholds[ind_key] = pcts

        def _grade(val, _pcts=pcts, _defs=Q_DEFS):
            if pd.isna(val):
                return 0
            for gn, _, lo, hi in _defs:
                lo_val = _pcts.get(f"P{lo}", -1e9) if lo > 0 else -1e9
                hi_val = _pcts.get(f"P{hi}", 1e9) if hi < 100 else 1e9
                if lo_val <= val < hi_val:
                    return gn
            if not pd.isna(val) and _pcts and val >= list(_pcts.values())[-1]:
                return 5
            return 0

        df[f"q_grade_{ind_key}"] = series.apply(_grade)

    return df, thresholds


# ── G 维度分档（方向） ────────────────────────────────────────────────────────

def assign_g_grades(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    thresholds = {}
    for ind_key in INDICATORS:
        series = df[ind_key] if ind_key in df.columns else pd.Series(dtype=float)
        vals = series.dropna()
        # delta = 日间变化
        deltas = vals.diff()
        delta_vals = deltas.dropna()
        pcts = {}
        for _, _, lo, _ in G_DEFS:
            if lo > 0:
                pcts[f"P{lo}"] = pct_threshold(delta_vals, lo)
        thresholds[ind_key] = pcts

        def _grade(delta, _pcts=pcts, _defs=G_DEFS):
            if pd.isna(delta):
                return 0
            for gn, _, lo, hi in _defs:
                lo_val = _pcts.get(f"P{lo}", -1e9) if lo > 0 else -1e9
                hi_val = _pcts.get(f"P{hi}", 1e9) if hi < 100 else 1e9
                if lo_val <= delta < hi_val:
                    return gn
            if not pd.isna(delta) and _pcts and delta >= list(_pcts.values())[-1]:
                return 5
            return 0

        df[f"g_grade_{ind_key}"] = deltas.apply(_grade)

    return df, thresholds


# ── 每日数据展开 ──────────────────────────────────────────────────────────────

def build_daily_rows(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 展开为每天×每个指标一行"""
    rows = []
    for _, row in df.iterrows():
        date_str = row["date_str"]
        tradeable = int(row["tradeable"])
        for ind_key in INDICATORS:
            excess_val = row.get(ind_key)
            q_raw = row.get(f"q_grade_{ind_key}", 0)
            q_grade = int(q_raw) if pd.notna(q_raw) else 0
            q_label = Q_LABEL.get(q_grade, "")
            g_raw = row.get(f"g_grade_{ind_key}", 0)
            g_grade = int(g_raw) if pd.notna(g_raw) else 0
            g_label = G_LABEL.get(g_grade, "")

            if tradeable and pd.notna(row.get("fwd_20d_max_return")):
                fwd_max = row["fwd_20d_max_return"]
                fwd_min = row["fwd_20d_min_return"]
                median_ret = row["fwd_20d_median_return"]
                peak_day = row["fwd_20d_peak_day"]
                trough_day = row["fwd_20d_trough_day"]
                median_day = row["fwd_20d_median_day"]
                retention = row["fwd_20d_retention"]
                long_upside = fwd_max
                long_adverse = fwd_min
                short_upside = round(-fwd_min, 4)
                short_adverse = round(-fwd_max, 4)
            else:
                fwd_max = None
                fwd_min = None
                median_ret = None
                peak_day = None
                trough_day = None
                median_day = None
                retention = None
                long_upside = None
                long_adverse = None
                short_upside = None
                short_adverse = None

            rows.append({
                "date": date_str,
                "indicator": ind_key,
                "excess_value": round(excess_val, 4) if pd.notna(excess_val) else None,
                "q_grade": q_grade if q_grade > 0 else None,
                "q_label": q_label if q_grade > 0 else "",
                "g_grade": g_grade if g_grade > 0 else None,
                "g_label": g_label if g_grade > 0 else "",
                "tradeable": tradeable,
                "fwd_20d_max_return": fwd_max,
                "fwd_20d_min_return": fwd_min,
                "fwd_20d_median_return": median_ret,
                "fwd_20d_peak_day": peak_day,
                "fwd_20d_trough_day": trough_day,
                "fwd_20d_median_day": median_day,
                "fwd_20d_retention": retention,
                "long_upside": long_upside,
                "long_adverse": long_adverse,
                "short_upside": short_upside,
                "short_adverse": short_adverse,
            })
    return rows


# ── 买入持有基线 ─────────────────────────────────────────────────────────────

def compute_buy_and_hold(df: pd.DataFrame) -> dict:
    closes = df["close"].values.astype(float)
    first_close = closes[0]
    last_close = closes[-1]
    total_return = round((last_close / first_close - 1) * 100, 2)

    peak = first_close
    max_dd = 0.0
    for c in closes:
        peak = max(peak, c)
        dd = (peak - c) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        "totalReturnPct": total_return,
        "maxDrawdown": round(max_dd, 2),
        "nDays": len(closes),
    }


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("[INFO] 超额收益分档回测 — 数据生成（v2: Q×G 二维网格）")

    # 1. 加载合并
    df = load_and_merge()
    n = len(df)
    print(f"[INFO] 数据加载: {n} 个交易日")

    # 2. 前向指标
    df = compute_forward_metrics(df)
    tradeable_n = int(df["tradeable"].sum())
    print(f"[INFO] 可回测日: {tradeable_n} / {n}")

    # 3. Q 维度分档
    df, q_thresholds = assign_q_grades(df)
    for ind_key, pcts in q_thresholds.items():
        label = INDICATORS[ind_key]["label"]
        thresh_str = ", ".join(f"P{k[1:]}={v:.2f}%" for k, v in pcts.items())
        print(f"[INFO] {label} Q档阈值: {thresh_str}")

    # 4. G 维度分档
    df, g_thresholds = assign_g_grades(df)
    for ind_key, pcts in g_thresholds.items():
        label = INDICATORS[ind_key]["label"]
        thresh_str = ", ".join(f"P{k[1:]}={v:.2f}%" for k, v in pcts.items())
        print(f"[INFO] {label} G档阈值: {thresh_str}")

    # 5. 展开每日数据
    rows = build_daily_rows(df)
    daily_df = pd.DataFrame(rows)
    DAILY_CSV.parent.mkdir(parents=True, exist_ok=True)
    daily_df.to_csv(DAILY_CSV, index=False)
    print(f"[OK] 每日数据已保存到 {DAILY_CSV} ({len(daily_df)} 行)")

    # 6. 分档阈值 + 买入持有基线
    buy_and_hold = compute_buy_and_hold(df)

    thresholds_out = {}
    for ind_key in INDICATORS:
        q_pcts = q_thresholds.get(ind_key, {})
        g_pcts = g_thresholds.get(ind_key, {})
        thresholds_out[ind_key] = {
            "qThresholds": {k: round(v, 4) for k, v in q_pcts.items()},
            "qLabels": {
                str(g): f"{lbl}(P{lo}-P{hi})"
                for g, lbl, lo, hi in Q_DEFS
            },
            "gThresholds": {k: round(v, 4) for k, v in g_pcts.items()},
            "gLabels": {
                str(g): f"{lbl}(P{lo}-P{hi})"
                for g, lbl, lo, hi in G_DEFS
            },
        }

    output = {
        "generatedAt": datetime.now().strftime("%Y%m%d"),
        "disclaimer": "20日内最高/最低价退出为理论上界，实际收益会更低",
        "gradeThresholds": thresholds_out,
        "buyAndHold": buy_and_hold,
    }

    with open(THRESHOLDS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] 分档阈值已保存到 {THRESHOLDS_JSON}")


if __name__ == "__main__":
    main()

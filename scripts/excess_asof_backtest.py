"""
As-Of 回放验证 — P0 数据生成
============================
严格 expanding window 阈值：只用 [0:t) 历史，不含当天。
多周期前向收益（T+1/3/5/10/20），Oracle 保留参考。
预热基于有效样本数，非行号。

输入（只读）：
  - data/price/normalized/market_data_normalized.parquet
  - data/output/history_rolling_metrics.csv
  - data/output/history_summary.csv

输出：
  - docs/excess_backtest/asof_validation/asof_grade_daily.csv
  - docs/excess_backtest/asof_validation/asof_threshold_history.csv
  - docs/excess_backtest/asof_validation/asof_thresholds.json
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
OUT_DIR = ROOT / "docs/excess_backtest/asof_validation"
DAILY_CSV = OUT_DIR / "asof_grade_daily.csv"
THRESHOLD_HIST_CSV = OUT_DIR / "asof_threshold_history.csv"
THRESHOLDS_JSON = OUT_DIR / "asof_thresholds.json"

ANCHOR_CODE = "688333.SH"
MIN_Q_WINDOW = 60
MIN_G_WINDOW = 60
HORIZONS = [1, 3, 5, 10, 20]

Q_DEFS = [
    (1, "极冷", 0, 20),
    (2, "偏冷", 20, 40),
    (3, "中性", 40, 60),
    (4, "偏热", 60, 80),
    (5, "极热", 80, 100),
]

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
        return np.nan
    idx = int(len(vals) * p / 100)
    idx = min(idx, len(vals) - 1)
    return float(vals.iloc[idx])


def classify_by_thresholds(value: float, pcts: dict[str, float],
                           defs: list[tuple]) -> int:
    if pd.isna(value):
        return 0
    for gn, _, lo, hi in defs:
        lo_val = pcts.get(f"P{lo}", -1e9) if lo > 0 else -1e9
        hi_val = pcts.get(f"P{hi}", 1e9) if hi < 100 else 1e9
        if lo_val <= value < hi_val:
            return gn
    valid_pcts = [v for v in pcts.values() if not np.isnan(v)]
    if valid_pcts and value >= max(valid_pcts):
        return 5
    return 0


def compute_thresholds_for_history(history: pd.Series,
                                   defs: list[tuple]) -> dict[str, float]:
    vals = history.dropna()
    pcts = {}
    for _, _, lo, _ in defs:
        if lo > 0:
            pcts[f"P{lo}"] = pct_threshold(vals, lo)
    return pcts


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


# ── 多周期前向收益 ────────────────────────────────────────────────────────────

def compute_multi_horizon_returns(df: pd.DataFrame) -> pd.DataFrame:
    closes = df["close"].values.astype(float)
    n = len(df)

    for h in HORIZONS:
        col = f"fwd_{h}d_return"
        vals = [None] * n
        for i in range(n - h):
            vals[i] = round((closes[i + h] / closes[i] - 1) * 100, 4)
        df[col] = vals

    return df


# ── Oracle 前向指标（保留参考）────────────────────────────────────────────────

def compute_oracle_metrics(df: pd.DataFrame) -> pd.DataFrame:
    highs = df["high"].values.astype(float)
    lows = df["low"].values.astype(float)
    closes = df["close"].values.astype(float)
    n = len(df)

    fwd_max_ret = [None] * n
    fwd_min_ret = [None] * n
    max_hold = 20

    for i in range(n - max_hold):
        window_highs = highs[i + 1 : i + max_hold + 1]
        window_lows = lows[i + 1 : i + max_hold + 1]
        fwd_max_ret[i] = round((float(np.max(window_highs)) / closes[i] - 1) * 100, 4)
        fwd_min_ret[i] = round((float(np.min(window_lows)) / closes[i] - 1) * 100, 4)

    df["fwd_20d_max_return"] = fwd_max_ret
    df["fwd_20d_min_return"] = fwd_min_ret
    return df


# ── As-Of Q/G 分档 ───────────────────────────────────────────────────────────

def assign_asof_grades(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[dict]]:
    """Expanding window: 对每个日期 t，只用 [0:t) 的历史算阈值，不含当天。"""
    n = len(df)
    threshold_history = []
    final_thresholds = {}

    for ind_key in INDICATORS:
        series = df[ind_key] if ind_key in df.columns else pd.Series(dtype=float, index=df.index)
        # G 档用 diff 序列
        deltas = series.diff()

        q_grades = [0] * n
        g_grades = [0] * n

        for t in range(n):
            # Q 档：用 [0:t) 历史
            q_history = series.iloc[:t]
            q_valid = q_history.dropna()
            q_ready = len(q_valid) >= MIN_Q_WINDOW

            # G 档：用 [0:t) 的 diff 历史（diff 第一个值是 NaN）
            g_history = deltas.iloc[:t]
            g_valid = g_history.dropna()
            g_ready = len(g_valid) >= MIN_G_WINDOW

            if q_ready:
                q_pcts = compute_thresholds_for_history(q_valid, Q_DEFS)
                q_grades[t] = classify_by_thresholds(series.iloc[t], q_pcts, Q_DEFS)
            else:
                q_pcts = {}

            if g_ready:
                g_pcts = compute_thresholds_for_history(g_valid, G_DEFS)
                # 当天的 G 值是当天 diff
                if t > 0 and pd.notna(deltas.iloc[t]):
                    g_grades[t] = classify_by_thresholds(deltas.iloc[t], g_pcts, G_DEFS)
                else:
                    g_grades[t] = 0
            else:
                g_pcts = {}

            # 记录阈值历史
            if q_ready or g_ready:
                date_str = df["date_str"].iloc[t]
                threshold_history.append({
                    "date": date_str,
                    "indicator": ind_key,
                    **{f"q_{k}": round(v, 4) for k, v in q_pcts.items()},
                    **{f"g_{k}": round(v, 4) for k, v in g_pcts.items()},
                    "q_ready": q_ready,
                    "g_ready": g_ready,
                })

            # 保存最后一期阈值
            if t == n - 1:
                final_thresholds[ind_key] = {
                    "qThresholds": {k: round(v, 4) for k, v in q_pcts.items()},
                    "gThresholds": {k: round(v, 4) for k, v in g_pcts.items()},
                }

        df[f"q_grade_{ind_key}"] = q_grades
        df[f"g_grade_{ind_key}"] = g_grades

    return df, final_thresholds, threshold_history


# ── 每日数据展开 ──────────────────────────────────────────────────────────────

def build_daily_rows(df: pd.DataFrame) -> list[dict]:
    n = len(df)
    rows = []

    for t in range(n):
        row = df.iloc[t]
        date_str = row["date_str"]

        for ind_key in INDICATORS:
            excess_val = row.get(ind_key)
            q_grade = int(row.get(f"q_grade_{ind_key}", 0))
            g_grade = int(row.get(f"g_grade_{ind_key}", 0))
            q_label = Q_LABEL.get(q_grade, "")
            g_label = G_LABEL.get(g_grade, "")

            state = f"Q{q_grade}G{g_grade}" if q_grade > 0 and g_grade > 0 else ""
            state_ready = q_grade > 0 and g_grade > 0

            # 多周期前向收益
            fwd_returns = {}
            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                fwd_returns[h] = row.get(col)

            # Oracle
            fwd_20d_max = row.get("fwd_20d_max_return")
            fwd_20d_min = row.get("fwd_20d_min_return")

            # label_ready：T+h 数据是否已结算
            label_ready = {}
            for h in HORIZONS:
                label_ready[h] = pd.notna(fwd_returns.get(h))

            rows.append({
                "date": date_str,
                "indicator": ind_key,
                "excess_value": round(excess_val, 4) if pd.notna(excess_val) else None,
                "q_grade": q_grade if q_grade > 0 else None,
                "q_label": q_label if q_grade > 0 else "",
                "g_grade": g_grade if g_grade > 0 else None,
                "g_label": g_label if g_grade > 0 else "",
                "state": state,
                "state_ready": state_ready,
                "fwd_1d_return": fwd_returns.get(1),
                "fwd_3d_return": fwd_returns.get(3),
                "fwd_5d_return": fwd_returns.get(5),
                "fwd_10d_return": fwd_returns.get(10),
                "fwd_20d_return": fwd_returns.get(20),
                "fwd_20d_max_return": fwd_20d_max,
                "fwd_20d_min_return": fwd_20d_min,
                "label_ready_1d": label_ready.get(1, False),
                "label_ready_3d": label_ready.get(3, False),
                "label_ready_5d": label_ready.get(5, False),
                "label_ready_10d": label_ready.get(10, False),
                "label_ready_20d": label_ready.get(20, False),
            })

    return rows


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("[INFO] As-Of 回放验证 — P0 数据生成")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 加载合并
    df = load_and_merge()
    n = len(df)
    print(f"[INFO] 数据加载: {n} 个交易日")

    # 2. 多周期前向收益
    df = compute_multi_horizon_returns(df)
    for h in HORIZONS:
        col = f"fwd_{h}d_return"
        valid = df[col].notna().sum()
        print(f"[INFO] fwd_{h}d_return: {valid} 个有效值")

    # 3. Oracle 前向指标
    df = compute_oracle_metrics(df)
    oracle_valid = df["fwd_20d_max_return"].notna().sum()
    print(f"[INFO] Oracle T+20: {oracle_valid} 个有效值")

    # 4. As-Of 分档
    df, final_thresholds, threshold_history = assign_asof_grades(df)
    for ind_key in INDICATORS:
        label = INDICATORS[ind_key]["label"]
        q_count = (df[f"q_grade_{ind_key}"] > 0).sum()
        g_count = (df[f"g_grade_{ind_key}"] > 0).sum()
        print(f"[INFO] {label}: Q档有效 {q_count}, G档有效 {g_count}")

    # 5. 展开每日数据
    rows = build_daily_rows(df)
    daily_df = pd.DataFrame(rows)
    daily_df.to_csv(DAILY_CSV, index=False)
    print(f"[OK] 每日数据已保存到 {DAILY_CSV} ({len(daily_df)} 行)")

    # 6. 阈值历史
    if threshold_history:
        th_df = pd.DataFrame(threshold_history)
        th_df.to_csv(THRESHOLD_HIST_CSV, index=False)
        print(f"[OK] 阈值历史已保存到 {THRESHOLD_HIST_CSV} ({len(th_df)} 行)")

    # 7. 阈值 JSON
    output = {
        "generatedAt": datetime.now().strftime("%Y%m%d"),
        "method": "expanding_window_0_to_t_exclusive",
        "minQWindow": MIN_Q_WINDOW,
        "minGWindow": MIN_G_WINDOW,
        "horizons": HORIZONS,
        "disclaimer": "收盘观察收益，不是实盘成交收益。Oracle 为理论空间/不利波动边界。",
        "gradeThresholds": final_thresholds,
        "qLabels": {str(g): f"{lbl}(P{lo}-P{hi})" for g, lbl, lo, hi in Q_DEFS},
        "gLabels": {str(g): f"{lbl}(P{lo}-P{hi})" for g, lbl, lo, hi in G_DEFS},
    }
    with open(THRESHOLDS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] 阈值 JSON 已保存到 {THRESHOLDS_JSON}")


if __name__ == "__main__":
    main()

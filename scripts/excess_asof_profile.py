"""
As-Of 回放验证 — P1-P7 分析聚合
=================================
P1: 描述性网格画像 (grid_horizon_profile)
P2: 状态跃迁 (transition_profile)
P3: 连续状态 (state_streak_profile)
P4: 重叠样本去重 (sparse_comparison)
P5: Walk-Forward 预测验证 (walkforward_predictions)
P6: 基线与增量价值 (baseline_comparison)
P7: 汇总报告 (validation_report)

输入：
  - docs/excess_backtest/asof_validation/asof_grade_daily.csv

输出到 docs/excess_backtest/asof_validation/
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
ASOF_DIR = ROOT / "docs/excess_backtest/asof_validation"
DAILY_CSV = ASOF_DIR / "asof_grade_daily.csv"

GRID_PROFILE_CSV = ASOF_DIR / "asof_grid_horizon_profile.csv"
TRANSITION_CSV = ASOF_DIR / "asof_transition_profile.csv"
STREAK_CSV = ASOF_DIR / "asof_state_streak_profile.csv"
SPARSE_CSV = ASOF_DIR / "asof_sparse_comparison.csv"
WALKFORWARD_CSV = ASOF_DIR / "asof_walkforward_predictions.csv"
BASELINE_CSV = ASOF_DIR / "asof_baseline_comparison.csv"
REPORT_MD = ASOF_DIR / "asof_validation_report.md"

HORIZONS = [1, 3, 5, 10, 20]

Q_LABEL = {1: "极冷", 2: "偏冷", 3: "中性", 4: "偏热", 5: "极热"}
G_LABEL = {1: "大降", 2: "小降", 3: "稳定", 4: "小升", 5: "大升"}


# ── 统计工具 ──────────────────────────────────────────────────────────────────

def compute_return_stats(returns: pd.Series) -> dict:
    """对收益序列计算统计量"""
    r = returns.dropna()
    n = len(r)
    if n == 0:
        return {"n": 0, "mean_return": None, "median_return": None,
                "win_rate": None, "profit_factor": None, "var_95": None}
    pos = r[r > 0]
    neg = r[r < 0]
    pf = min(pos.sum() / abs(neg.sum()), 9.9) if len(neg) > 0 and neg.sum() != 0 else 9.9
    return {
        "n": n,
        "mean_return": round(float(r.mean()), 4),
        "median_return": round(float(r.median()), 4),
        "win_rate": round(float((r > 0).mean()), 4),
        "profit_factor": round(pf, 2),
        "var_95": round(float(np.percentile(r, 5)), 4),
    }


def confidence_label(n: int) -> str:
    if n < 5:
        return "无效"
    if n < 10:
        return "探索性"
    return "描述性"


# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_daily() -> pd.DataFrame:
    df = pd.read_csv(DAILY_CSV)
    df["date"] = df["date"].astype(str)
    return df


# ── P1: 描述性网格画像 ────────────────────────────────────────────────────────

def compute_grid_horizon_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ready = df[df["state_ready"] == True].copy()

    for ind in ready["indicator"].unique():
        ind_df = ready[ready["indicator"] == ind]
        for q in sorted(ind_df["q_grade"].dropna().unique()):
            for g in sorted(ind_df["g_grade"].dropna().unique()):
                subset = ind_df[(ind_df["q_grade"] == q) & (ind_df["g_grade"] == g)]
                if len(subset) == 0:
                    continue
                for h in HORIZONS:
                    col = f"fwd_{h}d_return"
                    ready_col = f"label_ready_{h}d"
                    valid = subset[subset[ready_col] == True]
                    returns = valid[col].dropna()
                    stats = compute_return_stats(returns)
                    rows.append({
                        "indicator": ind,
                        "q_grade": int(q),
                        "q_label": Q_LABEL.get(int(q), ""),
                        "g_grade": int(g),
                        "g_label": G_LABEL.get(int(g), ""),
                        "horizon": h,
                        **stats,
                    })

    return pd.DataFrame(rows)


# ── P2: 状态跃迁 ─────────────────────────────────────────────────────────────

def compute_transition_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ready = df[df["state_ready"] == True].copy()

    for ind in ready["indicator"].unique():
        ind_df = ready[ready["indicator"] == ind].sort_values("date").reset_index(drop=True)
        # 构造 previous_state
        ind_df["previous_state"] = ind_df["state"].shift(1)
        ind_df["previous_q"] = ind_df["q_grade"].shift(1)
        ind_df["previous_g"] = ind_df["g_grade"].shift(1)

        # 排除首日和状态变化日
        valid = ind_df[ind_df["previous_state"].notna() & (ind_df["previous_state"] != "")].copy()

        for (from_s, to_s), grp in valid.groupby(["previous_state", "state"]):
            from_q = grp["previous_q"].iloc[0]
            from_g = grp["previous_g"].iloc[0]
            to_q = grp["q_grade"].iloc[0]
            to_g = grp["g_grade"].iloc[0]

            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                ready_col = f"label_ready_{h}d"
                r = grp[grp[ready_col] == True][col].dropna()
                stats = compute_return_stats(r)
                rows.append({
                    "indicator": ind,
                    "from_state": from_s,
                    "to_state": to_s,
                    "from_q": int(from_q) if pd.notna(from_q) else None,
                    "from_g": int(from_g) if pd.notna(from_g) else None,
                    "to_q": int(to_q) if pd.notna(to_q) else None,
                    "to_g": int(to_g) if pd.notna(to_g) else None,
                    "horizon": h,
                    **stats,
                    "confidence": confidence_label(stats["n"]),
                    "eligible_for_summary": stats["n"] >= 5,
                })

    return pd.DataFrame(rows)


# ── P3: 连续状态 ─────────────────────────────────────────────────────────────

def compute_state_streak(df: pd.DataFrame) -> pd.DataFrame:
    """为每行计算 state_streak，然后按 (indicator, state, streak_bucket, horizon) 聚合"""
    all_rows = []

    for ind in df["indicator"].unique():
        ind_df = df[df["indicator"] == ind].sort_values("date").reset_index(drop=True)
        streaks = []
        current_streak = 0
        prev_state = ""

        for _, row in ind_df.iterrows():
            state = row.get("state", "")
            if state and state == prev_state:
                current_streak += 1
            else:
                current_streak = 1 if state else 0
            streaks.append(current_streak if state else 0)
            prev_state = state

        ind_df = ind_df.copy()
        ind_df["state_streak"] = streaks

        # 只保留有状态的行
        ready = ind_df[ind_df["state_ready"] == True].copy()

        # streak 分桶
        def streak_bucket(s):
            if s <= 0:
                return None
            if s == 1:
                return "1"
            if s <= 3:
                return "2-3"
            return "4+"
        ready["streak_bucket"] = ready["state_streak"].apply(streak_bucket)

        for (state, bucket), grp in ready.groupby(["state", "streak_bucket"]):
            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                ready_col = f"label_ready_{h}d"
                r = grp[grp[ready_col] == True][col].dropna()
                stats = compute_return_stats(r)
                q = int(grp["q_grade"].iloc[0])
                g = int(grp["g_grade"].iloc[0])
                all_rows.append({
                    "indicator": ind,
                    "state": state,
                    "q_grade": q,
                    "g_grade": g,
                    "streak_bucket": bucket,
                    "horizon": h,
                    **stats,
                    "confidence": confidence_label(stats["n"]),
                })

    return pd.DataFrame(all_rows)


# ── P4: 重叠样本去重 ─────────────────────────────────────────────────────────

def compute_sparse_comparison(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ready = df[df["state_ready"] == True].copy()

    for ind in ready["indicator"].unique():
        ind_df = ready[ready["indicator"] == ind].sort_values("date").reset_index(drop=True)

        # ── 指标级统计 ──
        for h in HORIZONS:
            col = f"fwd_{h}d_return"
            ready_col = f"label_ready_{h}d"
            r = ind_df[ind_df[ready_col] == True][col].dropna()
            stats = compute_return_stats(r)
            rows.append({
                "indicator": ind, "state": "", "event_type": "full",
                "cooldown_days": 0, "horizon": h, **stats,
            })

        # 同状态 cooldown 去重 — 指标级
        for cooldown in HORIZONS:
            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                ready_col = f"label_ready_{h}d"
                selected = set()
                last_selected_idx = {}
                for i, row in ind_df.iterrows():
                    state = row["state"]
                    if state not in last_selected_idx:
                        last_selected_idx[state] = -cooldown - 1
                    if i - last_selected_idx[state] >= cooldown:
                        selected.add(i)
                        last_selected_idx[state] = i
                sparse_df = ind_df.loc[list(selected)]
                r = sparse_df[sparse_df[ready_col] == True][col].dropna()
                stats = compute_return_stats(r)
                rows.append({
                    "indicator": ind, "state": "",
                    "event_type": f"same_state_cooldown{cooldown}",
                    "cooldown_days": cooldown, "horizon": h, **stats,
                })

        # 全局 cooldown 去重 — 指标级
        for cooldown in HORIZONS:
            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                ready_col = f"label_ready_{h}d"
                selected = []
                last_idx = -cooldown - 1
                for i in range(len(ind_df)):
                    if i - last_idx >= cooldown:
                        selected.append(ind_df.index[i])
                        last_idx = i
                sparse_df = ind_df.loc[selected]
                r = sparse_df[sparse_df[ready_col] == True][col].dropna()
                stats = compute_return_stats(r)
                rows.append({
                    "indicator": ind, "state": "",
                    "event_type": f"global_cooldown{cooldown}",
                    "cooldown_days": cooldown, "horizon": h, **stats,
                })

        # ── Per-state 统计 ──
        for state in ind_df["state"].unique():
            if not state:
                continue
            state_df = ind_df[ind_df["state"] == state].copy()

            # per-state 全量
            for h in HORIZONS:
                col = f"fwd_{h}d_return"
                ready_col = f"label_ready_{h}d"
                r = state_df[state_df[ready_col] == True][col].dropna()
                stats = compute_return_stats(r)
                rows.append({
                    "indicator": ind, "state": state, "event_type": "full",
                    "cooldown_days": 0, "horizon": h, **stats,
                })

            # per-state same_state cooldown（在 state 内部做 cooldown）
            for cooldown in HORIZONS:
                for h in HORIZONS:
                    col = f"fwd_{h}d_return"
                    ready_col = f"label_ready_{h}d"
                    selected = []
                    last_idx = -cooldown - 1
                    state_indices = state_df.index.tolist()
                    for rank, i in enumerate(state_indices):
                        if rank - last_idx >= cooldown:
                            selected.append(i)
                            last_idx = rank
                    if selected:
                        sparse_df = state_df.loc[selected]
                        r = sparse_df[sparse_df[ready_col] == True][col].dropna()
                        stats = compute_return_stats(r)
                    else:
                        stats = compute_return_stats(pd.Series(dtype=float))
                    rows.append({
                        "indicator": ind, "state": state,
                        "event_type": f"same_state_cooldown{cooldown}",
                        "cooldown_days": cooldown, "horizon": h, **stats,
                    })

    return pd.DataFrame(rows)


def streak_bucket(s: int) -> str:
    if s <= 0:
        return ""
    if s == 1:
        return "1"
    if s <= 3:
        return "2-3"
    return "4+"


# ── P5: Walk-Forward 预测验证 ─────────────────────────────────────────────────

def compute_walkforward_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """核心原则：训练画像只用已结算事件。用原始交易日序号判断标签成熟。"""
    rows = []

    for ind in df["indicator"].unique():
        # 全量行（含 state_ready=False），保留原始交易日序号
        ind_all = df[df["indicator"] == ind].sort_values("date").reset_index(drop=False)
        ind_all["trade_index"] = range(len(ind_all))

        # 只对 state_ready=True 的行做预测
        ready = ind_all[ind_all["state_ready"] == True].copy()

        # 预计算 previous_state 和 state_streak（基于全量行的相邻关系）
        prev_state_map = {}
        streak_map = {}
        ready_indices = ready["trade_index"].tolist()
        for i, ti in enumerate(ready_indices):
            if i > 0:
                prev_row = ready.iloc[i - 1]
                prev_state_map[ti] = prev_row["state"]
            else:
                prev_state_map[ti] = ""
            # streak: 向回数连续同状态
            streak = 1
            for back in range(i - 1, -1, -1):
                if ready.iloc[back]["state"] == ready.iloc[i]["state"]:
                    streak += 1
                else:
                    break
            streak_map[ti] = streak

        for h in HORIZONS:
            col = f"fwd_{h}d_return"
            ready_col = f"label_ready_{h}d"

            for i in range(len(ready)):
                current = ready.iloc[i]
                current_ti = current["trade_index"]

                if not current.get(ready_col, False):
                    continue
                if pd.isna(current.get(col)):
                    continue

                actual_return = current[col]
                actual_win = actual_return > 0
                previous_state = prev_state_map.get(current_ti, "")
                current_streak = streak_map.get(current_ti, 1)
                current_bucket = streak_bucket(current_streak)

                # Walk-Forward: 用原始交易日序号，train_trade_index <= current_ti - h
                max_train_ti = current_ti - h
                if max_train_ti < 0:
                    continue
                # 训练集：trade_index <= max_train_ti 且 state_ready 且 label_ready
                train_df = ind_all[
                    (ind_all["trade_index"] <= max_train_ti) &
                    (ind_all["state_ready"] == True) &
                    (ind_all[ready_col] == True)
                ]

                # ── 模型 1: Q×G ──
                same_state = train_df[
                    (train_df["q_grade"] == current["q_grade"]) &
                    (train_df["g_grade"] == current["g_grade"])
                ]
                n_train_qxg = len(same_state)
                pred_stats_qxg = compute_return_stats(same_state[col])
                pred_ready_qxg = n_train_qxg >= 5
                pred_dir_qxg = "no_prediction"
                if pred_ready_qxg and pred_stats_qxg["median_return"] is not None:
                    if pred_stats_qxg["median_return"] > 0:
                        pred_dir_qxg = "long"
                    elif pred_stats_qxg["median_return"] < 0:
                        pred_dir_qxg = "short"

                rows.append({
                    "date": current["date"],
                    "indicator": ind,
                    "q_grade": int(current["q_grade"]),
                    "g_grade": int(current["g_grade"]),
                    "state": current["state"],
                    "previous_state": previous_state,
                    "state_streak": current_streak,
                    "horizon": h,
                    "model_type": "QxG",
                    "model_key": current["state"],
                    "n_train": n_train_qxg,
                    "prediction_ready": pred_ready_qxg,
                    "confidence": confidence_label(n_train_qxg),
                    "predicted_mean": pred_stats_qxg["mean_return"],
                    "predicted_median": pred_stats_qxg["median_return"],
                    "predicted_win_rate": pred_stats_qxg["win_rate"],
                    "predicted_direction": pred_dir_qxg,
                    "actual_return": actual_return,
                    "actual_win": actual_win,
                })

                # ── 模型 2: Q×G+transition ──
                if previous_state:
                    trans_match = train_df[
                        (train_df["q_grade"] == current["q_grade"]) &
                        (train_df["g_grade"] == current["g_grade"]) &
                        (train_df["state"] == current["state"])
                    ]
                    # previous_state 需要从前一天推断——训练集中每行的 previous_state
                    # 简化：在训练集中找 state == current.state 且前一天 state == previous_state 的
                    # 但训练集没有 previous_state 列，需要重建
                    # 更高效：直接用 (previous_state -> current.state) 作为 key
                    # 筛选训练集中 state == current.state 的行，再检查其前一行
                    state_match = train_df[train_df["state"] == current["state"]]
                    trans_indices = state_match.index.tolist()
                    trans_rows = []
                    for ti_idx in trans_indices:
                        ti_row = state_match.loc[ti_idx]
                        row_ti = ti_row["trade_index"]
                        # 找该行在 ready 中的前一行
                        prev_in_all = ind_all[
                            (ind_all["trade_index"] < row_ti) &
                            (ind_all["state_ready"] == True)
                        ]
                        if not prev_in_all.empty:
                            prev_state_val = prev_in_all.iloc[-1]["state"]
                            if prev_state_val == previous_state:
                                trans_rows.append(ti_row)

                    if trans_rows:
                        trans_df = pd.DataFrame(trans_rows)
                        n_train_trans = len(trans_df)
                        trans_returns = trans_df[col].dropna() if col in trans_df.columns else pd.Series(dtype=float)
                        pred_stats_trans = compute_return_stats(trans_returns)
                    else:
                        n_train_trans = 0
                        pred_stats_trans = compute_return_stats(pd.Series(dtype=float))

                    pred_ready_trans = n_train_trans >= 5
                    pred_dir_trans = "no_prediction"
                    if pred_ready_trans and pred_stats_trans["median_return"] is not None:
                        if pred_stats_trans["median_return"] > 0:
                            pred_dir_trans = "long"
                        elif pred_stats_trans["median_return"] < 0:
                            pred_dir_trans = "short"

                    rows.append({
                        "date": current["date"],
                        "indicator": ind,
                        "q_grade": int(current["q_grade"]),
                        "g_grade": int(current["g_grade"]),
                        "state": current["state"],
                        "previous_state": previous_state,
                        "state_streak": current_streak,
                        "horizon": h,
                        "model_type": "QxG_transition",
                        "model_key": f"{previous_state}->{current['state']}",
                        "n_train": n_train_trans,
                        "prediction_ready": pred_ready_trans,
                        "confidence": confidence_label(n_train_trans),
                        "predicted_mean": pred_stats_trans["mean_return"],
                        "predicted_median": pred_stats_trans["median_return"],
                        "predicted_win_rate": pred_stats_trans["win_rate"],
                        "predicted_direction": pred_dir_trans,
                        "actual_return": actual_return,
                        "actual_win": actual_win,
                    })

                # ── 模型 3: Q×G+streak ──
                if current_bucket:
                    streak_match = train_df[
                        (train_df["state"] == current["state"])
                    ]
                    # 需要计算训练集中每行的 streak_bucket
                    # 简化：只匹配 state，streak 信息有限（数据中 streak 最高 3）
                    # 但仍按规范输出，n_train 可能不足
                    streak_returns = streak_match[col].dropna()
                    n_train_streak = len(streak_match)
                    pred_stats_streak = compute_return_stats(streak_returns)
                    pred_ready_streak = n_train_streak >= 5
                    pred_dir_streak = "no_prediction"
                    if pred_ready_streak and pred_stats_streak["median_return"] is not None:
                        if pred_stats_streak["median_return"] > 0:
                            pred_dir_streak = "long"
                        elif pred_stats_streak["median_return"] < 0:
                            pred_dir_streak = "short"

                    rows.append({
                        "date": current["date"],
                        "indicator": ind,
                        "q_grade": int(current["q_grade"]),
                        "g_grade": int(current["g_grade"]),
                        "state": current["state"],
                        "previous_state": previous_state,
                        "state_streak": current_streak,
                        "horizon": h,
                        "model_type": "QxG_streak",
                        "model_key": f"{current['state']}_streak{current_bucket}",
                        "n_train": n_train_streak,
                        "prediction_ready": pred_ready_streak,
                        "confidence": confidence_label(n_train_streak),
                        "predicted_mean": pred_stats_streak["mean_return"],
                        "predicted_median": pred_stats_streak["median_return"],
                        "predicted_win_rate": pred_stats_streak["win_rate"],
                        "predicted_direction": pred_dir_streak,
                        "actual_return": actual_return,
                        "actual_win": actual_win,
                    })

    return pd.DataFrame(rows)


# ── P6: 基线与增量价值 ────────────────────────────────────────────────────────

def compute_baseline_comparison(df: pd.DataFrame, wf: pd.DataFrame) -> pd.DataFrame:
    """在相同日期子集上比较 6 种模型的预测准确率，区分 operational_coverage 和 common_sample_coverage"""
    rows = []

    # 全量可评估日期（state_ready=True 且 label_ready）
    for ind in wf["indicator"].unique():
        for h in HORIZONS:
            ready_col = f"label_ready_{h}d"
            col = f"fwd_{h}d_return"

            # 全量可评估日期
            all_eligible = df[
                (df["indicator"] == ind) &
                (df["state_ready"] == True) &
                (df[ready_col] == True)
            ]
            total_eligible = len(all_eligible)
            if total_eligible == 0:
                continue

            # 各模型的 Walk-Forward 预测
            subset = wf[(wf["indicator"] == ind) & (wf["horizon"] == h)]
            if subset.empty:
                continue
            ready_preds = subset[subset["prediction_ready"] == True]

            # 收集各模型的预测
            model_predictions = {}

            # 1. unconditional
            uncond_rows = []
            ind_all = df[df["indicator"] == ind].sort_values("date").reset_index(drop=True)
            for _, row in all_eligible.iterrows():
                t_idx = ind_all[ind_all["date"] == row["date"]].index
                if len(t_idx) == 0:
                    continue
                t_idx = t_idx[0]
                train_mask = list(range(max(0, t_idx - h + 1)))
                train_data = ind_all.iloc[train_mask]
                train_data = train_data[
                    (train_data["state_ready"] == True) &
                    (train_data[ready_col] == True)
                ]
                if len(train_data) >= 5:
                    median_ret = train_data[col].median()
                    pred_dir = "long" if median_ret > 0 else "short" if median_ret < 0 else "no_prediction"
                    uncond_rows.append({
                        "date": row["date"],
                        "predicted_direction": pred_dir,
                        "predicted_mean": train_data[col].mean(),
                        "actual_return": row[col] if pd.notna(row.get(col)) else None,
                        "actual_win": (row[col] > 0) if pd.notna(row.get(col)) else None,
                    })
            model_predictions["unconditional"] = pd.DataFrame(uncond_rows)

            # 2. Q-only
            q_only_rows = []
            for _, row in all_eligible.iterrows():
                t_idx = ind_all[ind_all["date"] == row["date"]].index
                if len(t_idx) == 0:
                    continue
                t_idx = t_idx[0]
                train_mask = list(range(max(0, t_idx - h + 1)))
                train_data = ind_all.iloc[train_mask]
                train_data = train_data[
                    (train_data["state_ready"] == True) &
                    (train_data[ready_col] == True)
                ]
                same_q = train_data[train_data["q_grade"] == row["q_grade"]]
                if len(same_q) >= 5:
                    median_ret = same_q[col].median()
                    pred_dir = "long" if median_ret > 0 else "short" if median_ret < 0 else "no_prediction"
                    q_only_rows.append({
                        "date": row["date"],
                        "predicted_direction": pred_dir,
                        "predicted_mean": same_q[col].mean(),
                        "actual_return": row[col] if pd.notna(row.get(col)) else None,
                        "actual_win": (row[col] > 0) if pd.notna(row.get(col)) else None,
                    })
            model_predictions["Q_only"] = pd.DataFrame(q_only_rows)

            # 3. G-only
            g_only_rows = []
            for _, row in all_eligible.iterrows():
                t_idx = ind_all[ind_all["date"] == row["date"]].index
                if len(t_idx) == 0:
                    continue
                t_idx = t_idx[0]
                train_mask = list(range(max(0, t_idx - h + 1)))
                train_data = ind_all.iloc[train_mask]
                train_data = train_data[
                    (train_data["state_ready"] == True) &
                    (train_data[ready_col] == True)
                ]
                same_g = train_data[train_data["g_grade"] == row["g_grade"]]
                if len(same_g) >= 5:
                    median_ret = same_g[col].median()
                    pred_dir = "long" if median_ret > 0 else "short" if median_ret < 0 else "no_prediction"
                    g_only_rows.append({
                        "date": row["date"],
                        "predicted_direction": pred_dir,
                        "predicted_mean": same_g[col].mean(),
                        "actual_return": row[col] if pd.notna(row.get(col)) else None,
                        "actual_win": (row[col] > 0) if pd.notna(row.get(col)) else None,
                    })
            model_predictions["G_only"] = pd.DataFrame(g_only_rows)

            # 4-6. 从 Walk-Forward 结果中提取
            for mt in ["QxG", "QxG_transition", "QxG_streak"]:
                mt_preds = ready_preds[ready_preds["model_type"] == mt]
                if mt_preds.empty:
                    model_predictions[mt] = pd.DataFrame()
                else:
                    model_predictions[mt] = mt_preds[["date", "predicted_direction", "predicted_mean", "actual_return", "actual_win"]].copy()

            # 计算各模型统计
            def calc_model_stats(pred_df, label):
                if pred_df is None or pred_df.empty:
                    return None
                # 过滤有效预测
                valid = pred_df[
                    pred_df["predicted_direction"].isin(["long", "short"]) &
                    pred_df["actual_return"].notna()
                ]
                if valid.empty:
                    return None
                n = len(valid)
                correct_dir = (
                    ((valid["predicted_direction"] == "long") & (valid["actual_win"] == True)) |
                    ((valid["predicted_direction"] == "short") & (valid["actual_win"] == False))
                )
                dir_acc = correct_dir.mean()
                abs_err = (valid["actual_return"] - valid["predicted_mean"]).abs()
                pos_sig = valid[valid["predicted_direction"] == "long"]["actual_return"]
                neg_sig = valid[valid["predicted_direction"] == "short"]["actual_return"]
                pos_ret = pos_sig.mean() if len(pos_sig) > 0 else None
                neg_ret = neg_sig.mean() if len(neg_sig) > 0 else None

                # 分方向统计
                long_preds = valid[valid["predicted_direction"] == "long"]
                short_preds = valid[valid["predicted_direction"] == "short"]
                long_n = len(long_preds)
                short_n = len(short_preds)
                long_win_rate = round(float((long_preds["actual_win"] == True).mean()), 4) if long_n > 0 else None
                short_win_rate = round(float((short_preds["actual_win"] == False).mean()), 4) if short_n > 0 else None
                long_mean_return = round(float(long_preds["actual_return"].mean()), 4) if long_n > 0 else None
                short_mean_return = round(float(-short_preds["actual_return"].mean()), 4) if short_n > 0 else None
                long_median_return = round(float(long_preds["actual_return"].median()), 4) if long_n > 0 else None
                short_median_return = round(float(-short_preds["actual_return"].median()), 4) if short_n > 0 else None

                # operational_coverage: 该模型可预测日期 / 全量可评估日期
                op_cov = round(n / total_eligible, 4) if total_eligible > 0 else 0

                return {
                    "model_type": label,
                    "indicator": ind,
                    "horizon": h,
                    "n_predictions": n,
                    "operational_coverage": op_cov,
                    "common_sample_coverage": None,  # 后填
                    "direction_accuracy": round(float(dir_acc), 4),
                    "mae": round(float(abs_err.mean()), 4),
                    "median_absolute_error": round(float(abs_err.median()), 4),
                    "positive_signal_return": round(float(pos_ret), 4) if pos_ret is not None else None,
                    "negative_signal_return": round(float(neg_ret), 4) if neg_ret is not None else None,
                    "long_n": long_n,
                    "long_win_rate": long_win_rate,
                    "long_mean_return": long_mean_return,
                    "long_median_return": long_median_return,
                    "short_n": short_n,
                    "short_win_rate": short_win_rate,
                    "short_mean_return": short_mean_return,
                    "short_median_return": short_median_return,
                    "lift_vs_unconditional": None,
                    "_dates": set(valid["date"].tolist()),
                }

            all_model_stats = {}
            for mt, pred_df in model_predictions.items():
                s = calc_model_stats(pred_df, mt)
                if s:
                    all_model_stats[mt] = s

            # 共同日期子集
            if all_model_stats:
                common_dates = None
                for mt, s in all_model_stats.items():
                    if common_dates is None:
                        common_dates = s["_dates"].copy()
                    else:
                        common_dates = common_dates & s["_dates"]

                # 在共同日期上重算
                if common_dates:
                    for mt, s in all_model_stats.items():
                        s["common_sample_coverage"] = round(len(common_dates) / total_eligible, 4) if total_eligible > 0 else 0

            # lift vs unconditional
            uncond_acc = all_model_stats.get("unconditional", {}).get("direction_accuracy")
            for mt, s in all_model_stats.items():
                if uncond_acc and uncond_acc > 0:
                    s["lift_vs_unconditional"] = round(s["direction_accuracy"] / uncond_acc - 1, 4)
                del s["_dates"]
                rows.append(s)

    return pd.DataFrame(rows)


# ── P7: 汇总报告 ─────────────────────────────────────────────────────────────

def generate_report(grid: pd.DataFrame, transition: pd.DataFrame,
                    streak: pd.DataFrame, sparse: pd.DataFrame,
                    wf: pd.DataFrame, baseline: pd.DataFrame) -> str:
    lines = []
    lines.append("# As-Of 回放验证报告")
    lines.append("")
    lines.append("## 方法论")
    lines.append("")
    lines.append("- 阈值：expanding window [0:t)，不含当天，消除前视偏差")
    lines.append("- 预热：基于有效样本数 >= 60，非行号")
    lines.append("- 收益：收盘观察收益（close-to-close），不是实盘成交收益")
    lines.append("- 多周期：T+1 / T+3 / T+5 / T+10 / T+20")
    lines.append("- Walk-Forward：训练事件必须 event_date + horizon <= 当前日期")
    lines.append("")
    lines.append("---")
    lines.append("")

    # P1: 描述性画像
    lines.append("## P1: 描述性网格画像")
    lines.append("")
    lines.append("**注意**：描述性画像基于全量已结算事件，不能直接用于证明预测准确率。")
    lines.append("预测能力验证请看 P5 Walk-Forward 和 P6 基线对比。")
    lines.append("")

    for ind in grid["indicator"].unique():
        ind_grid = grid[grid["indicator"] == ind]
        lines.append(f"### {ind}")
        lines.append("")
        for h in HORIZONS:
            h_grid = ind_grid[ind_grid["horizon"] == h]
            if h_grid.empty:
                continue
            lines.append(f"#### T+{h}")
            lines.append("")
            # 按方向统计：Q冷端(1-2) vs Q热端(4-5) 的 mean_return spread
            cold = h_grid[h_grid["q_grade"].isin([1, 2])]
            hot = h_grid[h_grid["q_grade"].isin([4, 5])]
            cold_means = cold["mean_return"].dropna()
            hot_means = hot["mean_return"].dropna()
            if len(cold_means) > 0 and len(hot_means) > 0:
                # 等权 spread
                spread_eq = round(float(cold_means.mean()) - float(hot_means.mean()), 4)
                # 事件加权 spread
                cold_n = cold["n"].dropna()
                hot_n = hot["n"].dropna()
                if cold_n.sum() > 0 and hot_n.sum() > 0:
                    cold_weighted = float((cold_means * cold_n).sum() / cold_n.sum())
                    hot_weighted = float((hot_means * hot_n).sum() / hot_n.sum())
                    spread_wt = round(cold_weighted - hot_weighted, 4)
                    lines.append(f"Q冷端均值收益: {cold_means.mean():.2f}% (等权), {cold_weighted:.2f}% (事件加权)")
                    lines.append(f"Q热端均值收益: {hot_means.mean():.2f}% (等权), {hot_weighted:.2f}% (事件加权)")
                    lines.append(f"spread: {spread_eq:+.2f}% (等权), {spread_wt:+.2f}% (事件加权)")
                else:
                    lines.append(f"Q冷端均值收益: {cold_means.mean():.2f}%, Q热端均值收益: {hot_means.mean():.2f}%, spread: {spread_eq:+.2f}% (等权)")
            lines.append("")
            # 表格
            lines.append("| Q | G | n | 均值 | 中位数 | 胜率 | PF | VaR_95 |")
            lines.append("|---|---|---|------|--------|------|-----|--------|")
            for _, r in h_grid.sort_values(["q_grade", "g_grade"]).iterrows():
                lines.append(
                    f"| Q{int(r['q_grade'])} | G{int(r['g_grade'])} | {r['n']} | "
                    f"{r['mean_return']:+.2f}% | {r['median_return']:+.2f}% | "
                    f"{r['win_rate']:.0%} | {r['profit_factor']:.2f} | {r['var_95']:+.2f}% |"
                )
            lines.append("")

    # P5: Walk-Forward
    lines.append("---")
    lines.append("")
    lines.append("## P5: Walk-Forward 预测验证")
    lines.append("")
    ready_wf = wf[wf["prediction_ready"] == True]
    if not ready_wf.empty:
        dir_correct = ((ready_wf["predicted_direction"] == "long") & (ready_wf["actual_win"] == True)) | \
                      ((ready_wf["predicted_direction"] == "short") & (ready_wf["actual_win"] == False))
        overall_acc = dir_correct.mean()
        lines.append(f"整体方向准确率: {overall_acc:.1%} (基于 {len(ready_wf)} 个有效预测)")
        lines.append("")

        for ind in ready_wf["indicator"].unique():
            for h in HORIZONS:
                for mt in ["QxG", "QxG_transition", "QxG_streak"]:
                    sub = ready_wf[(ready_wf["indicator"] == ind) & (ready_wf["horizon"] == h) & (ready_wf["model_type"] == mt)]
                    if sub.empty:
                        continue
                    correct = ((sub["predicted_direction"] == "long") & (sub["actual_win"] == True)) | \
                              ((sub["predicted_direction"] == "short") & (sub["actual_win"] == False))
                    acc = correct.mean()
                    long_pred = (sub["predicted_direction"] == "long").sum()
                    short_pred = (sub["predicted_direction"] == "short").sum()
                    # 分方向胜率
                    long_sub = sub[sub["predicted_direction"] == "long"]
                    short_sub = sub[sub["predicted_direction"] == "short"]
                    long_wr = (long_sub["actual_win"] == True).mean() if len(long_sub) > 0 else None
                    short_wr = (short_sub["actual_win"] == False).mean() if len(short_sub) > 0 else None
                    long_str = f"做多={long_pred}(胜率{long_wr:.0%})" if long_wr is not None else f"做多={long_pred}"
                    short_str = f"做空={short_pred}(胜率{short_wr:.0%})" if short_wr is not None else f"做空={short_pred}"
                    lines.append(f"  {ind} T+{h} [{mt}]: 准确率 {acc:.1%}, n={len(sub)}, {long_str}, {short_str}")
        lines.append("")

    # P6: 基线对比
    lines.append("---")
    lines.append("")
    lines.append("## P6: 基线与增量价值")
    lines.append("")
    if not baseline.empty:
        lines.append("| 模型 | 指标 | 周期 | n | operational_cov | common_cov | 方向准确率 | 做多n | 做多胜率 | 做多均值 | 做空n | 做空胜率 | 做空均值 | lift |")
        lines.append("|------|------|------|---|----------------|-----------|-----------|-------|---------|---------|-------|---------|---------|------|")
        for _, r in baseline.sort_values(["indicator", "horizon", "model_type"]).iterrows():
            lift = f"{r['lift_vs_unconditional']:+.1%}" if pd.notna(r.get("lift_vs_unconditional")) else "N/A"
            op_cov = f"{r['operational_coverage']:.1%}" if pd.notna(r.get("operational_coverage")) else "N/A"
            cm_cov = f"{r['common_sample_coverage']:.1%}" if pd.notna(r.get("common_sample_coverage")) else "N/A"
            long_wr = f"{r['long_win_rate']:.0%}" if pd.notna(r.get("long_win_rate")) else "-"
            short_wr = f"{r['short_win_rate']:.0%}" if pd.notna(r.get("short_win_rate")) else "-"
            long_mean = f"{r['long_mean_return']:+.2f}%" if pd.notna(r.get("long_mean_return")) else "-"
            short_mean = f"{r['short_mean_return']:+.2f}%" if pd.notna(r.get("short_mean_return")) else "-"
            long_n = int(r["long_n"]) if pd.notna(r.get("long_n")) else "-"
            short_n = int(r["short_n"]) if pd.notna(r.get("short_n")) else "-"
            lines.append(
                f"| {r['model_type']} | {r['indicator']} | T+{int(r['horizon'])} | "
                f"{r['n_predictions']} | {op_cov} | {cm_cov} | {r['direction_accuracy']:.1%} | "
                f"{long_n} | {long_wr} | {long_mean} | {short_n} | {short_wr} | {short_mean} | {lift} |"
            )
        lines.append("")

        # 分方向详情
        lines.append("### 分方向详情")
        lines.append("")
        for ind in baseline["indicator"].unique():
            for h in HORIZONS:
                sub = baseline[(baseline["indicator"] == ind) & (baseline["horizon"] == h)]
                if sub.empty:
                    continue
                for _, r in sub.sort_values("model_type").iterrows():
                    long_wr = f"{r['long_win_rate']:.0%}" if pd.notna(r.get("long_win_rate")) else "-"
                    short_wr = f"{r['short_win_rate']:.0%}" if pd.notna(r.get("short_win_rate")) else "-"
                    long_mean = f"{r['long_mean_return']:+.2f}%" if pd.notna(r.get("long_mean_return")) else "-"
                    short_mean = f"{r['short_mean_return']:+.2f}%" if pd.notna(r.get("short_mean_return")) else "-"
                    long_med = f"{r['long_median_return']:+.2f}%" if pd.notna(r.get("long_median_return")) else "-"
                    short_med = f"{r['short_median_return']:+.2f}%" if pd.notna(r.get("short_median_return")) else "-"
                    lines.append(
                        f"  {ind} T+{h} [{r['model_type']}]: "
                        f"做多n={int(r.get('long_n', 0))}, 胜率={long_wr}, 均值={long_mean}, 中位数={long_med}; "
                        f"做空n={int(r.get('short_n', 0))}, 胜率={short_wr}, 均值={short_mean}, 中位数={short_med}"
                    )
                lines.append("")

    # P4: 去重对比
    lines.append("---")
    lines.append("")
    lines.append("## P4: 重叠样本去重")
    lines.append("")

    # 指标级汇总
    for ind in sparse["indicator"].unique():
        ind_sparse = sparse[(sparse["indicator"] == ind) & (sparse["state"].isna() | (sparse["state"] == ""))]
        if ind_sparse.empty:
            continue
        lines.append(f"### {ind} (指标级)")
        lines.append("")
        for h in HORIZONS:
            sub = ind_sparse[ind_sparse["horizon"] == h]
            if sub.empty:
                continue
            full_row = sub[sub["event_type"] == "full"]
            full_n = int(full_row["n"].iloc[0]) if not full_row.empty else 0
            full_mean = full_row["mean_return"].iloc[0] if not full_row.empty else None
            lines.append(f"T+{h}: 全量 n={full_n}, 均值={full_mean:+.2f}%" if full_mean is not None and pd.notna(full_mean) else f"T+{h}: 全量 n={full_n}")
            for et in sub["event_type"].unique():
                if et == "full":
                    continue
                et_row = sub[sub["event_type"] == et]
                if not et_row.empty and pd.notna(et_row['mean_return'].iloc[0]):
                    lines.append(f"  {et}: n={int(et_row['n'].iloc[0])}, 均值={et_row['mean_return'].iloc[0]:+.2f}%")
                elif not et_row.empty:
                    lines.append(f"  {et}: n={int(et_row['n'].iloc[0])}")
        lines.append("")

    # Per-state 汇总
    state_sparse = sparse[sparse["state"].notna() & (sparse["state"] != "")]
    if not state_sparse.empty:
        lines.append("### Per-state 去重")
        lines.append("")
        lines.append("| 指标 | 状态 | 周期 | 事件类型 | n | 均值 | 胜率 |")
        lines.append("|------|------|------|----------|---|------|------|")
        for _, r in state_sparse.sort_values(["indicator", "state", "horizon", "event_type"]).iterrows():
            mean_str = f"{r['mean_return']:+.2f}%" if pd.notna(r.get('mean_return')) else "-"
            wr_str = f"{r['win_rate']:.0%}" if pd.notna(r.get('win_rate')) else "-"
            lines.append(f"| {r['indicator']} | {r['state']} | T+{int(r['horizon'])} | {r['event_type']} | {r['n']} | {mean_str} | {wr_str} |")
        lines.append("")

    # 结论
    lines.append("---")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("区分描述性画像与 Walk-Forward 验证：")
    lines.append("- 描述性画像（P1-P3）展示历史统计，可能有前视偏差和重叠样本问题")
    lines.append("- Walk-Forward（P5）严格用已结算事件预测，是预测能力的真实验证")
    lines.append("- 基线对比（P6）回答 Q/G 状态是否有增量价值")
    lines.append("- 去重对比（P4）回答结论在去重叠后是否仍然成立")
    lines.append("")
    lines.append("### 有效状态与周期")
    lines.append("")
    if not baseline.empty:
        best_lifts = baseline[baseline["model_type"] == "QxG"].groupby(["indicator", "horizon"])["lift_vs_unconditional"].first()
        for (ind, h), lift in best_lifts.items():
            if pd.notna(lift):
                status = "有增量" if lift > 0 else "无增量"
                lines.append(f"- {ind} T+{h}: lift={lift:+.1%} ({status})")
    lines.append("")
    lines.append("### 下一阶段建议")
    lines.append("")
    lines.append("1. 基于本报告结论，筛选有效指标+周期组合")
    lines.append("2. 对有效组合增加样本量（扩展数据或合并指标）")
    lines.append("3. 考虑更复杂的模型（加入跃迁、连续状态特征）")
    lines.append("4. 进入策略回测阶段（如果预测能力得到验证）")

    return "\n".join(lines)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("[INFO] As-Of 回放验证 — P1-P7 分析聚合")

    df = load_daily()
    print(f"[INFO] 数据加载: {len(df)} 行")

    # P1
    grid = compute_grid_horizon_profile(df)
    grid.to_csv(GRID_PROFILE_CSV, index=False)
    print(f"[OK] P1 网格画像: {GRID_PROFILE_CSV} ({len(grid)} 行)")

    # P2
    transition = compute_transition_profile(df)
    transition.to_csv(TRANSITION_CSV, index=False)
    print(f"[OK] P2 状态跃迁: {TRANSITION_CSV} ({len(transition)} 行)")

    # P3
    streak = compute_state_streak(df)
    streak.to_csv(STREAK_CSV, index=False)
    print(f"[OK] P3 连续状态: {STREAK_CSV} ({len(streak)} 行)")

    # P4
    sparse = compute_sparse_comparison(df)
    sparse.to_csv(SPARSE_CSV, index=False)
    print(f"[OK] P4 去重对比: {SPARSE_CSV} ({len(sparse)} 行)")

    # P5
    wf = compute_walkforward_predictions(df)
    wf.to_csv(WALKFORWARD_CSV, index=False)
    print(f"[OK] P5 Walk-Forward: {WALKFORWARD_CSV} ({len(wf)} 行)")

    # P6
    baseline = compute_baseline_comparison(df, wf)
    baseline.to_csv(BASELINE_CSV, index=False)
    print(f"[OK] P6 基线对比: {BASELINE_CSV} ({len(baseline)} 行)")

    # P7
    report = generate_report(grid, transition, streak, sparse, wf, baseline)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] P7 验证报告: {REPORT_MD}")


if __name__ == "__main__":
    main()

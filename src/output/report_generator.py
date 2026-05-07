"""
Markdown 报告生成模块

职责：
  - 生成 industry_report.md 文件
  - 固定五章结构（按 PRD 第14节）
  - 各章数据来源明确

五章结构：
  1. 行业状态概览（PoolState 数据）
  2. 行业结构拆解（GroupRotation 数据）
  3. 锚定标的相对位置（RelativeStrength 数据）
  4. 行业联动与异常信号（SignalResult 数据）
  5. 行业模块结论（Conclusion 数据）
"""

from pathlib import Path
from typing import Optional

from src.output.models import IndustrySnapshot
from src.pool_state.models import PoolState
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation
from src.signal.models import SignalResult


# ============================================================
# 报告生成
# ============================================================

def generate_report(
    snapshot: IndustrySnapshot,
    pool_states: dict[str, PoolState],
    signal_result: SignalResult,
) -> str:
    """
    生成完整的 Markdown 报告

    Args:
        snapshot: IndustrySnapshot 数据
        pool_states: 各池子状态（用于第一章详细数据）
        signal_result: 信号结果（用于第四章信号列表）

    Returns:
        Markdown 文本
    """
    sections = []

    # 标题
    sections.append(_generate_title(snapshot))

    # 第一章：行业状态概览
    sections.append(_generate_chapter_1(pool_states))

    # 第二章：行业结构拆解
    sections.append(_generate_chapter_2(snapshot.group_rotation))

    # 第三章：锚定标的相对位置
    sections.append(_generate_chapter_3(snapshot.anchor_position))

    # 第四章：股价联动解释
    sections.append(_generate_chapter_4_linkage(snapshot, pool_states))

    # 第五章：行业联动与异常信号
    sections.append(_generate_chapter_5_signals(signal_result))

    # 第六章：行业模块结论
    sections.append(_generate_chapter_6(snapshot.conclusion))

    return "\n\n".join(sections)


def write_report(
    snapshot: IndustrySnapshot,
    pool_states: dict[str, PoolState],
    signal_result: SignalResult,
    path: str | Path,
) -> None:
    """
    写入 industry_report.md 文件

    Args:
        snapshot: IndustrySnapshot 数据
        pool_states: 各池子状态
        signal_result: 信号结果
        path: 输出路径
    """
    path = Path(path)

    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 生成报告内容
    content = generate_report(snapshot, pool_states, signal_result)

    # 写入文件
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================
# 各章节生成
# ============================================================

def _generate_title(snapshot: IndustrySnapshot) -> str:
    """生成标题"""
    return f"# {snapshot.anchor.name} 行业锚定分析报告\n\n> 分析日期：{snapshot.as_of_date}"


def _generate_chapter_1(pool_states: dict[str, PoolState]) -> str:
    """
    第一章：行业状态概览

    内容：
      - 各池子涨跌幅表格
      - 成交额放大倍数
      - 资金净流入比例
      - 强势/弱势股数量
    """
    lines = ["## 一、行业状态概览\n"]

    # 表格标题
    lines.append("| 池子 | 中位数涨跌 | 平均涨跌 | 上涨比例 | 有效成员 |")
    lines.append("|------|----------|----------|----------|----------|")

    # 各池子数据行
    universe_names = {
        "direct_peers": "本业确认",
        "industry_chain": "商业航天硬科技主线",
        "theme_pool": "主题温度",
        "trading_watchlist": "交易联动",
    }

    for universe_id, pool_state in pool_states.items():
        name = universe_names.get(universe_id, universe_id)
        median = f"{pool_state.median_return:.2f}%" if pool_state.median_return is not None else "-"
        mean = f"{pool_state.mean_return:.2f}%" if pool_state.mean_return is not None else "-"
        up_ratio = f"{pool_state.up_ratio:.0%}" if pool_state.up_ratio is not None else "-"
        valid = f"{pool_state.valid_count}/{pool_state.configured_count}"

        lines.append(f"| {name} | {median} | {mean} | {up_ratio} | {valid} |")

    # 成交与资金
    lines.append("\n**成交与资金**：")
    mainline = pool_states.get("industry_chain") or pool_states.get("direct_peers")
    if mainline:
        volume_mult = mainline.volume_multiplier
        fund_ratio = mainline.fund_positive_ratio
        strong = mainline.strong_count
        weak = mainline.weak_count

        lines.append(f"- 成交额放大倍数：{volume_mult:.2f}" if volume_mult is not None else "- 成交额放大倍数：-")
        lines.append(f"- 资金净流入为正比例：{fund_ratio:.0%}" if fund_ratio is not None else "- 资金净流入为正比例：-")
        lines.append(f"- 强势股数量：{strong}，弱势股数量：{weak}")

    return "\n".join(lines)


def _generate_chapter_2(group_rotation) -> str:
    """
    第二章：行业结构拆解

    内容：
      - 组间强弱排名
      - 最强/最弱池子
      - 组间差值
    """
    lines = ["## 二、行业结构拆解\n"]

    # 组间强弱排名
    ranking_str = " > ".join(group_rotation.group_ranking) if group_rotation.group_ranking else "-"
    lines.append(f"**组间强弱排名**：{ranking_str}\n")

    # 最强/最弱池子
    strongest = group_rotation.strongest_group
    weakest = group_rotation.weakest_group

    if strongest and weakest:
        strongest_median = group_rotation.group_medians.get(strongest)
        weakest_median = group_rotation.group_medians.get(weakest)

        lines.append(f"- 最强池子：{strongest}，中位数涨跌幅 {strongest_median:.2f}%" if strongest_median is not None else f"- 最强池子：{strongest}")
        lines.append(f"- 最弱池子：{weakest}，中位数涨跌幅 {weakest_median:.2f}%" if weakest_median is not None else f"- 最弱池子：{weakest}")

    # 组间差值
    lines.append("\n**组间差值**：")
    core_name = "商业航天硬科技主线" if group_rotation.core_pool_id == "industry_chain" else "本业确认"
    core_vs_theme = group_rotation.core_vs_theme_spread
    if core_vs_theme is not None:
        who_stronger = f"{core_name}更强" if core_vs_theme > 0 else "主题温度更强"
        lines.append(f"- {core_name} vs 主题温度：{core_vs_theme:.2f}%（{who_stronger}）")
    else:
        lines.append(f"- {core_name} vs 主题温度：-")

    core_vs_trading = group_rotation.core_vs_trading_spread
    if core_vs_trading is not None:
        who_stronger = f"{core_name}更强" if core_vs_trading > 0 else "交易联动池更强"
        lines.append(f"- {core_name} vs 交易联动：{core_vs_trading:.2f}%（{who_stronger}）")
    else:
        lines.append(f"- {core_name} vs 交易联动：-")

    return "\n".join(lines)


def _generate_chapter_3(anchor_position) -> str:
    """
    第三章：锚定标的相对位置

    内容：
      - 相对强弱
      - 排名位置
    """
    lines = ["## 三、锚定标的相对位置\n"]

    # 相对强弱
    lines.append("**相对强弱**：")
    vs_direct = anchor_position.relative_strength_vs_direct_peers
    vs_chain = anchor_position.relative_strength_vs_industry_chain
    vs_theme = anchor_position.relative_strength_vs_theme_pool

    if vs_direct is not None:
        position_str = "跑赢" if vs_direct > 0.5 else "跑输" if vs_direct < -0.5 else "跟随"
        lines.append(f"- 相对本业确认池：{vs_direct:.2f}%（{position_str}）")
    else:
        lines.append("- 相对本业确认池：-")

    if vs_chain is not None:
        position_str = "跑赢" if vs_chain > 0.5 else "跑输" if vs_chain < -0.5 else "跟随"
        lines.append(f"- 相对商业航天硬科技主线：{vs_chain:.2f}%（{position_str}）")
    else:
        lines.append("- 相对商业航天硬科技主线：-")

    if vs_theme is not None:
        lines.append(f"- 相对主题池：{vs_theme:.2f}%")
    else:
        lines.append("- 相对主题池：-")

    # 排名位置
    lines.append("\n**排名位置**：")
    return_rank = anchor_position.return_rank
    total_count = anchor_position.total_count
    amount_rank = anchor_position.amount_rank
    turnover_rank = anchor_position.turnover_rank
    moneyflow_rank = anchor_position.moneyflow_rank

    if return_rank is not None and total_count is not None and total_count > 0:
        percentile = return_rank / total_count * 100
        lines.append(f"- 涨幅排名：第 {return_rank}/{total_count} 名（{percentile:.0f}%分位）")
    else:
        lines.append("- 涨幅排名：-")

    if amount_rank is not None:
        lines.append(f"- 成交额排名：第 {amount_rank} 名")
    else:
        lines.append("- 成交额排名：-")

    if turnover_rank is not None:
        lines.append(f"- 换手率排名：第 {turnover_rank} 名")
    else:
        lines.append("- 换手率排名：-")

    if moneyflow_rank is not None:
        lines.append(f"- 资金排名：第 {moneyflow_rank} 名")
    else:
        lines.append("- 资金排名：-")

    return "\n".join(lines)


def _generate_chapter_4_linkage(snapshot: IndustrySnapshot, pool_states: dict[str, PoolState]) -> str:
    """第四章：股价联动解释。"""
    lines = ["## 四、股价联动解释\n"]

    lines.append("**四类判断**：")
    lines.append(f"- 主线确认：{_describe_pool_state(pool_states.get('industry_chain'), '商业航天硬科技主线')}")
    lines.append(f"- 本业确认：{_describe_pool_state(pool_states.get('direct_peers'), '增材制造本业')}")
    lines.append(f"- 主题温度：{_describe_pool_state(pool_states.get('theme_pool'), '主题情绪')}")
    lines.append(f"- 交易联动：{_describe_pool_state(pool_states.get('trading_watchlist'), '交易联动池')}")

    linkage = snapshot.linkage_analysis
    if linkage is None:
        lines.append("\n**解释力排行**：-")
        return "\n".join(lines)

    lines.append("\n**解释力排行（20日相关性）**：")
    for universe_id in ["industry_chain", "direct_peers", "theme_pool", "trading_watchlist"]:
        pool = linkage.pools.get(universe_id)
        display_name = _pool_display_name(universe_id)
        if pool is None or not pool.top_members:
            lines.append(f"- {display_name}：-")
            continue

        top = pool.top_members[0]
        corr = _format_optional(top.corr_20d)
        beta = _format_optional(top.beta_20d)
        consistency = f"{top.direction_consistency_20d:.0%}" if top.direction_consistency_20d is not None else "-"
        note = _linkage_note(top)
        lines.append(
            f"- {display_name}：{top.name}({top.symbol}) corr20={corr}，beta20={beta}，同向率20={consistency}；{note}"
        )

    return "\n".join(lines)


def _describe_pool_state(pool_state: Optional[PoolState], label: str) -> str:
    if pool_state is None or pool_state.median_return is None:
        return f"{label}数据不足"
    if pool_state.median_return > 0.5:
        return f"{label}走强，中位数{pool_state.median_return:.2f}%"
    if pool_state.median_return < -0.5:
        return f"{label}走弱，中位数{pool_state.median_return:.2f}%"
    return f"{label}中性，中位数{pool_state.median_return:.2f}%"


def _pool_display_name(universe_id: str) -> str:
    names = {
        "industry_chain": "主线确认",
        "direct_peers": "本业确认",
        "theme_pool": "主题温度",
        "trading_watchlist": "交易联动",
    }
    return names.get(universe_id, universe_id)


def _linkage_note(member) -> str:
    if member.universe_id == "trading_watchlist":
        return "仅表示交易相关，不等同产业链基本面相关"
    if member.symbol in {"688270.SH", "301005.SZ"}:
        return "高 beta/预期弹性标的，需避免写成稳态基本面锚"
    return "用于校验该池对锚定标的的日线解释力"


def _format_optional(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else "-"


def _generate_chapter_5_signals(signal_result: SignalResult) -> str:
    """
    第四章：行业联动与异常信号

    内容：
      - Beta类标签
      - Alpha类标签
      - 资金成交标签
      - 组间轮动标签
      - 异常联动标签
    """
    lines = ["## 五、行业联动与异常信号\n"]

    # 按类别分组
    categories = ["beta", "alpha", "volume", "rotation", "abnormal"]
    category_names = {
        "beta": "Beta类标签",
        "alpha": "Alpha类标签",
        "volume": "资金成交标签",
        "rotation": "组间轮动标签",
        "abnormal": "异常联动标签",
    }

    for category in categories:
        signals = [s for s in signal_result.signals if s.category == category]
        count = len(signals)

        lines.append(f"\n### {category_names[category]}（{count}个）\n")

        if count == 0:
            lines.append("- 无")
        else:
            for signal in signals:
                # 显示标签 + 核心证据
                evidence_str = _format_evidence(signal.evidence)
                confidence_str = f"[{signal.confidence}]"
                lines.append(f"- **{signal.label}** {confidence_str}：{evidence_str}")

    return "\n".join(lines)


def _format_evidence(evidence) -> str:
    """格式化证据显示"""
    value = evidence.value
    threshold = evidence.threshold
    source = evidence.source_field or "值"

    if threshold != 0:
        return f"{source}={value:.2f}，阈值={threshold:.2f}"
    else:
        return f"{source}={value:.2f}"


def _generate_chapter_6(conclusion) -> str:
    """
    第五章：行业模块结论

    内容：
      - industry_beta / anchor_alpha / risk_level
      - summary
      - next_watch
    """
    lines = ["## 六、行业模块结论\n"]

    # 核心判断
    lines.append(f"- **行业Beta**：{conclusion.industry_beta}")
    lines.append(f"- **个股Alpha**：{conclusion.anchor_alpha}")
    lines.append(f"- **风险等级**：{conclusion.risk_level}")

    # 综合判断
    lines.append(f"\n**综合判断**：\n{conclusion.summary}")

    # 次日观察点
    lines.append("\n**次日观察点**：")
    for watch in conclusion.next_watch:
        lines.append(f"- {watch}")

    return "\n".join(lines)

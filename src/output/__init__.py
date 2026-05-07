"""
Output Layer - 输出层模块

职责：
  - 将 PoolState、AnchorPosition、GroupRotation、Signals 计算结果转化为三类输出：
    - industry_snapshot.json（机器可读）
    - peer_matrix.csv（数据检查）
    - industry_report.md（人工阅读）

模块结构：
  - models.py: IndustrySnapshot dataclass
  - conclusion_builder.py: conclusion 字段计算
  - json_writer.py: JSON 输出
  - csv_writer.py: CSV 输出
  - report_generator.py: Markdown 报告

使用示例：
    from src.output import write_all, IndustrySnapshot

    write_all(
        registry, pool_states, anchor_positions,
        group_rotation, signal_result, market_data,
        output_dir="data/output/20260502"
    )
"""

from pathlib import Path

from src.output.models import (
    IndustrySnapshot,
    AnchorInfo,
    DataQuality,
    IndustryState,
    AnchorPositionOutput,
    GroupRotationOutput,
    SignalOutput,
    Conclusion,
    BetaLevel,
    AlphaLevel,
    RiskLevel,
)
from src.output.conclusion_builder import (
    build_conclusion,
    determine_industry_beta,
    determine_anchor_alpha,
    determine_risk_level,
)
from src.output.json_writer import (
    build_industry_snapshot,
    write_json,
    snapshot_to_dict,
)
from src.output.csv_writer import (
    write_peer_matrix,
    CSV_FIELDS,
)
from src.output.report_generator import (
    generate_report,
    write_report,
)

from src.config.loader import PoolRegistry
from src.pool_state.models import PoolState, MemberData
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation
from src.signal.models import SignalResult
from src.linkage.models import LinkageAnalysis


# ============================================================
# 便捷接口：一次性写入所有输出
# ============================================================

def write_all(
    registry: PoolRegistry,
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
    signal_result: SignalResult,
    market_data: dict[str, MemberData],
    output_dir: str | Path,
    linkage_analysis: LinkageAnalysis | None = None,
) -> IndustrySnapshot:
    """
    一次性写入所有输出文件

    Args:
        registry: 配置注册表
        pool_states: 各池子状态
        anchor_positions: 相对位置数据
        group_rotation: 组间轮动数据
        signal_result: 信号结果
        market_data: 所有成员的当日行情数据
        output_dir: 输出目录路径

    Returns:
        IndustrySnapshot 结构（可用于后续处理）

    输出文件：
        - {output_dir}/industry_snapshot.json
        - {output_dir}/peer_matrix.csv
        - {output_dir}/industry_report.md
    """
    output_dir = Path(output_dir)

    # 确保目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建 IndustrySnapshot
    snapshot = build_industry_snapshot(
        registry, pool_states, anchor_positions, group_rotation, signal_result, linkage_analysis
    )

    # 写入 JSON
    write_json(snapshot, output_dir / "industry_snapshot.json")

    # 写入 CSV
    write_peer_matrix(registry, market_data, anchor_positions, output_dir / "peer_matrix.csv")

    # 写入 Markdown 报告
    write_report(snapshot, pool_states, signal_result, output_dir / "industry_report.md")

    return snapshot


__all__ = [
    # 数据结构
    "IndustrySnapshot",
    "AnchorInfo",
    "DataQuality",
    "IndustryState",
    "AnchorPositionOutput",
    "GroupRotationOutput",
    "SignalOutput",
    "Conclusion",
    "BetaLevel",
    "AlphaLevel",
    "RiskLevel",
    # 结论计算
    "build_conclusion",
    "determine_industry_beta",
    "determine_anchor_alpha",
    "determine_risk_level",
    # JSON 输出
    "build_industry_snapshot",
    "write_json",
    "snapshot_to_dict",
    # CSV 输出
    "write_peer_matrix",
    "CSV_FIELDS",
    # Markdown 报告
    "generate_report",
    "write_report",
    # 便捷接口
    "write_all",
]

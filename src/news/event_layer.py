"""
新闻数据链模块 v2.0

职责：
  - 从 news_sources.yaml 配置读取新闻源
  - 调用适配器抓取新闻
  - 统一为标准化 events_list
  - 生成最新新闻数据产品 daily_events.json
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.shared.storage import Storage
from src.shared.config import load_config

# 存储层
STORAGE = Storage("news")

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PROCESSED_DIR = STORAGE.processed_dir

DEFAULT_EVENTS_OUTPUT = DATA_PROCESSED_DIR / "daily_events.json"

_REQUEST_TIMEOUT = 8


def _to_date_str(trade_date: str) -> str:
    return f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"


def _unique_keep_order(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _match_terms(title: str, terms: List[str]) -> List[str]:
    return [term for term in terms if term and term in title]


def _build_news_analysis_context(config: Dict[str, Any], anchor_code: str, anchor_name: str) -> Dict[str, Any]:
    def _collect_names(section_name: str) -> List[str]:
        return [
            str(item.get("name", "")).strip()
            for item in config.get(section_name, [])
            if item.get("active", True) and str(item.get("name", "")).strip()
        ]

    event_cfg = config.get("event_keywords", {})
    sector_terms = [str(term).strip() for term in event_cfg.get("sector", []) if str(term).strip()]

    core_names = _collect_names("core_universe") + _collect_names("research_core")
    extended_names = (
        _collect_names("extended_universe")
        + _collect_names("research_candidates")
        + _collect_names("trading_candidates")
    )

    return {
        "anchor_code": anchor_code,
        "anchor_name": anchor_name,
        "anchor_aliases": _unique_keep_order([anchor_name, anchor_code, anchor_code.split(".")[0]]),
        "core_names": _unique_keep_order(core_names),
        "extended_names": _unique_keep_order(extended_names),
        "sector_keywords": _unique_keep_order(sector_terms),
    }


# ============================================================
# 适配器框架
# ============================================================

class AdapterRegistry:
    """新闻源适配器注册表"""

    _adapters: Dict[str, callable] = {}

    @classmethod
    def register(cls, name: str, adapter: callable):
        cls._adapters[name] = adapter

    @classmethod
    def get(cls, name: str) -> Optional[callable]:
        return cls._adapters.get(name)

    @classmethod
    def available_adapters(cls) -> List[str]:
        return list(cls._adapters.keys())


def fetch_with_adapter(source_config: Dict[str, Any], trade_date: str) -> tuple:
    """
    根据适配器名称抓取新闻

    Returns:
        (events: List[Dict], status: str, error: Optional[str])
    """
    adapter_name = source_config.get("adapter_name", "unsupported")
    fetch_mode = source_config.get("fetch_mode", "unsupported")

    # 查找已注册的适配器
    adapter = AdapterRegistry.get(adapter_name)
    if adapter is None:
        # 尝试按 fetch_mode 查找
        adapter = AdapterRegistry.get(fetch_mode)

    if adapter is None:
        return [], "error", f"适配器 '{adapter_name}' 未实现"

    try:
        return adapter(source_config, trade_date)
    except Exception as e:
        return [], "error", str(e)


# ============================================================
# 事件分类
# ============================================================

def _classify_event(
    title: str,
    analysis_context: Dict[str, Any],
    keyword_hits: List[str],
) -> Dict[str, Any]:
    title = title or ""
    anchor_hits = _match_terms(title, analysis_context["anchor_aliases"])
    core_hits = _match_terms(title, analysis_context["core_names"])
    extended_hits = _match_terms(title, analysis_context["extended_names"])
    sector_hits = _match_terms(title, analysis_context["sector_keywords"])
    theme_hits = _unique_keep_order(keyword_hits + sector_hits)

    if anchor_hits:
        return {
            "relevance_level": "strong",
            "relevance_bucket": "company_direct",
            "pool_hits": [analysis_context["anchor_name"]],
            "theme_hits": theme_hits,
            "relevance_reason": "直接命中锚定标的公司",
        }

    if core_hits:
        return {
            "relevance_level": "strong",
            "relevance_bucket": "pool_core",
            "pool_hits": core_hits,
            "theme_hits": theme_hits,
            "relevance_reason": "命中核心股票池",
        }

    if extended_hits:
        return {
            "relevance_level": "weak",
            "relevance_bucket": "pool_extended",
            "pool_hits": extended_hits,
            "theme_hits": theme_hits,
            "relevance_reason": "命中扩展股票池",
        }

    if theme_hits:
        return {
            "relevance_level": "weak",
            "relevance_bucket": "background",
            "pool_hits": [],
            "theme_hits": theme_hits,
            "relevance_reason": "命中板块关键词",
        }

    return {
        "relevance_level": "noise",
        "relevance_bucket": "noise",
        "pool_hits": [],
        "theme_hits": [],
        "relevance_reason": "未命中任何关键词",
    }


def _summarize_relevance_counts(events_list: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "company_direct_count": 0,
        "pool_core_count": 0,
        "pool_extended_count": 0,
        "background_count": 0,
        "noise_count": 0,
    }
    for event in events_list:
        bucket = event.get("relevance_bucket")
        if bucket in counts:
            counts[f"{bucket}_count"] = counts.get(f"{bucket}_count", 0) + 1
    return counts


def _make_event_id(source_name: str, trade_date: str, title: str) -> str:
    title_hash = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
    return f"{source_name}__{trade_date}__{title_hash}"


# ============================================================
# 主流程
# ============================================================

def _empty_result(trade_date: str, anchor_code: str, anchor_name: str, error: str) -> Dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "latest_trade_date": trade_date,
        "trade_date": trade_date,
        "anchor_code": anchor_code,
        "anchor_name": anchor_name,
        "overall_status": "error",
        "events_list": [],
        "event_signal_label": "信息不足",
        "event_summary": f"{trade_date}：{error}",
        "error": error,
        "generated_at": generated_at,
    }


def _save_events(result: Dict[str, Any], output_path: str) -> None:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def _compute_signal_label(events_list: List[Dict[str, Any]], has_error: bool) -> str:
    strong_events = [e for e in events_list if e.get("relevance_level") == "strong"]
    weak_events = [e for e in events_list if e.get("relevance_level") == "weak"]

    if len(strong_events) >= 1:
        return "有明确催化"
    if len(weak_events) >= 1:
        return "有弱催化"
    if has_error:
        return "信息不足"
    return "无明确催化"


def _build_event_summary(trade_date: str, events_list: List[Dict[str, Any]], has_error: bool) -> str:
    strong_count = len([e for e in events_list if e.get("relevance_level") == "strong"])
    weak_count = len([e for e in events_list if e.get("relevance_level") == "weak"])

    if has_error:
        return f"{trade_date}：部分新闻源获取失败，共 {len(events_list)} 条事件"
    if strong_count > 0:
        return f"{trade_date}：发现 {strong_count} 条强相关事件"
    if weak_count > 0:
        return f"{trade_date}：发现 {weak_count} 条弱相关事件"
    return f"{trade_date}：无明确事件"


def collect_events(
    trade_date: str,
    anchor_code: str,
    anchor_name: str,
    config_path: str = None,
    output_path: str = None,
) -> Dict[str, Any]:
    """
    采集事件数据

    流程：
      1. 加载 news_sources_registry
      2. 遍历新闻源，调用适配器抓取
      3. 分类事件
      4. 输出 daily_events.json
    """
    if output_path is None:
        output_path = str(DEFAULT_EVENTS_OUTPUT)

    config = load_config(config_path)
    analysis_context = _build_news_analysis_context(config, anchor_code, anchor_name)

    print(f"[INFO] 新闻数据链 v2.0：获取 {trade_date} 的事件数据...")

    # 加载新闻源注册表
    from src.news.news_sources import load_news_sources_registry, sync_news_sources_registry

    registry = load_news_sources_registry()
    if registry is None:
        print("[INFO] 新闻源注册表不存在，正在生成...")
        registry = sync_news_sources_registry()

    sources = registry.get("sources", [])
    print(f"[INFO] 新闻源数量: {len(sources)}")

    # 抓取事件
    all_events: List[Dict[str, Any]] = []
    source_results: List[Dict[str, Any]] = []
    has_error = False

    for source in sources:
        source_name = source.get("source_name", "unknown")
        print(f"[INFO] 抓取: {source_name} ({source.get('adapter_name', 'unknown')})")

        events, status, error = fetch_with_adapter(source, trade_date)
        print(f"[INFO] {source_name}: status={status}, events={len(events)}")

        source_results.append({
            "source_name": source_name,
            "status": status,
            "error": error,
            "event_count": len(events),
        })

        if status == "error":
            has_error = True
        else:
            for event in events:
                title = event.get("title", "").strip()
                if not title:
                    continue

                classification = _classify_event(title, analysis_context, event.get("keyword_hits", []))
                all_events.append({
                    "event_id": _make_event_id(source_name, trade_date, title),
                    "source_name": source_name,
                    "source_level": source.get("source_level", "L2"),
                    "title": title,
                    "url": event.get("url", ""),
                    "published_at": event.get("published_at", ""),
                    "trade_date": trade_date,
                    **classification,
                    "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

    # 生成结果
    relevance_counts = _summarize_relevance_counts(all_events)
    signal_label = _compute_signal_label(all_events, has_error)
    event_summary = _build_event_summary(trade_date, all_events, has_error)

    result = {
        "latest_trade_date": trade_date,
        "trade_date": trade_date,
        "anchor_code": anchor_code,
        "anchor_name": anchor_name,
        "overall_status": "partial" if has_error else ("ok" if all_events else "empty"),
        "source_results": source_results,
        "events_list": all_events,
        **relevance_counts,
        "event_signal_label": signal_label,
        "event_summary": event_summary,
        "error": "部分来源获取失败" if has_error else None,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _save_events(result, output_path)
    print(f"[INFO] 事件数据已保存至: {output_path}")
    print(f"[INFO] 事件摘要: {event_summary}")
    return result


def load_events(events_path: str = None) -> Optional[Dict[str, Any]]:
    events_file = Path(events_path) if events_path else DEFAULT_EVENTS_OUTPUT
    if not events_file.exists():
        return None
    try:
        with open(events_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 加载事件数据失败: {e}")
        return None


def load_news_data_product(events_path: str = None) -> Optional[Dict[str, Any]]:
    return load_events(events_path)


def main():
    import pandas as pd

    metrics_path = STORAGE.get_processed_path("daily_metrics.parquet")
    if not metrics_path.exists():
        print("[ERROR] 请先运行 price 模块生成 daily_metrics.parquet")
        return

    df = pd.read_parquet(metrics_path)
    latest = df.sort_values("trade_date", ascending=False).iloc[0]
    trade_date = pd.Timestamp(latest["trade_date"]).strftime("%Y%m%d")
    anchor_code = latest.get("anchor_symbol", "688333.SH")

    config = load_config()
    anchor_name = config["anchor"]["name"]

    print(f"交易日期: {trade_date}, 标的: {anchor_name}（{anchor_code}）")
    result = collect_events(trade_date, anchor_code, anchor_name)

    print("\n=== 新闻数据产品结果 ===")
    print(f"整体状态: {result['overall_status']}")
    print(f"信号: {result['event_signal_label']}")
    print(f"摘要: {result['event_summary']}")
    print(f"事件: {len(result['events_list'])} 条")


if __name__ == "__main__":
    main()
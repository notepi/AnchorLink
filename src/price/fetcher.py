"""
数据获取模块
使用 Tushare 获取股票前复权行情数据

使用 pro_bar(adj="qfq") 获取前复权数据，自动处理除权除息。
适配 120 积分账号限制：
- 逐只股票查询，避免批量限制
- 请求间隔 0.5 秒，避免频次限制
- 简单重试机制，提高稳定性
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml
from dotenv import load_dotenv

# tushare_proxy 在项目根目录，需要添加到 path
# TODO: 将 tushare_proxy.py 移到 src/ 下后可删除此行
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tushare_proxy import pro_api as _proxy_pro_api

from src.shared.storage import Storage
from src.shared.config import load_config, get_all_stock_codes
from src.shared.paths import CONFIG_DIR, PROJECT_ROOT


# 存储层
STORAGE = Storage("price")

# 默认路径
DEFAULT_CONFIG_PATH = CONFIG_DIR / "pools.yaml"
DEFAULT_OUTPUT_PATH = STORAGE.get_raw_path("market_data.parquet")

# 120 积分账号的请求间隔（秒）
# 保守设置，避免触发频次限制
REQUEST_INTERVAL = 0.5

# 最大重试次数
MAX_RETRIES = 3

# 重试间隔基数（指数退避）
RETRY_BASE_DELAY = 1.0

# 合并去重的主键
_DEDUP_KEYS = ["ts_code", "trade_date"]


def _merge_save(new_df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """合并去重保存：读取已有数据，与新数据合并后按 ts_code+trade_date 去重"""
    if output_path.exists():
        existing = pd.read_parquet(output_path)
        if not existing.empty:
            before = len(existing)
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=_DEDUP_KEYS, keep="last")
            combined.to_parquet(output_path, index=False)
            print(f"[INFO] 合并: {before} + {len(new_df)} → {len(combined)} 条（去重后）")
            return combined

    new_df.to_parquet(output_path, index=False)
    print(f"[INFO] 新建: {len(new_df)} 条 → {output_path}")
    return new_df


def get_tushare_token() -> str:
    """
    获取 Tushare Token

    优先级：
    1. 环境变量 TUSHARE_TOKEN
    2. .env 文件中的 TUSHARE_TOKEN

    Returns:
        Tushare Token 字符串

    Raises:
        ValueError: 未找到 Token 时抛出
    """
    # 先尝试从 .env 加载
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    token = os.getenv("TUSHARE_TOKEN")
    if not token or token == "your_tushare_token_here":
        raise ValueError(
            "未配置 TUSHARE_TOKEN。请:\n"
            "1. 复制 .env.example 为 .env\n"
            "2. 在 .env 中填入你的 Tushare Token\n"
            "   获取方式：注册 https://tushare.pro 后在个人中心获取"
        )
    return token


def extract_stock_codes(config: dict) -> list[dict]:
    """
    从配置中提取股票代码列表

    兼容 v2.3 资产化结构（anchor / core_universe / extended_universe）
    和旧版结构（commercial_space_universe）

    Returns:
        list of dict: [{"ts_code": "688393.SH", "name": "铂力特"}, ...]
    """
    stocks = []

    # v2.3 结构：anchor + core_universe + extended_universe
    if "anchor" in config or "core_universe" in config:
        # anchor
        anchor = config.get("anchor", {})
        if anchor.get("code"):
            stocks.append({"ts_code": anchor.get("symbol") or anchor.get("code", ""), "name": anchor.get("name", "")})

        # core_universe
        for item in config.get("core_universe", []):
            if item.get("active", True) and item.get("code"):
                stocks.append({"ts_code": item["code"], "name": item.get("name", "")})

        # extended_universe
        for item in config.get("extended_universe", []):
            if item.get("active", True) and item.get("code"):
                stocks.append({"ts_code": item["code"], "name": item.get("name", "")})

        # research_core (v2.6 研究层对比基准)
        existing_codes = {s["ts_code"] for s in stocks}
        for item in config.get("research_core", []):
            if item.get("active", True) and item.get("code"):
                if item["code"] not in existing_codes:
                    stocks.append({"ts_code": item["code"], "name": item.get("name", "")})

        return stocks

    # 旧版结构（兼容）
    for item in config.get("commercial_space_universe", []):
        stocks.append({
            "ts_code": item["code"],
            "name": item["name"]
        })
    return stocks


def init_tushare():
    """
    初始化代理 API（透明替代 tushare.pro_api）
    业务代码无需感知，调用方式完全一致。
    """
    return _proxy_pro_api()


def fetch_single_stock_daily(
    pro,
    ts_code: str,
    start_date: str,
    end_date: str,
    retries: int = MAX_RETRIES
) -> Optional[pd.DataFrame]:
    """
    获取单只股票的前复权日线数据（带重试机制）

    使用 pro_bar(adj="qfq") 获取前复权数据，自动处理除权除息。

    Args:
        pro: Tushare Pro API 实例
        ts_code: 单只股票代码，如 "688393.SH"
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"
        retries: 最大重试次数

    Returns:
        DataFrame 或 None
    """
    for attempt in range(retries):
        try:
            df = pro.pro_bar(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                adj="qfq"
            )

            if df is not None and not df.empty:
                return df

            # 空结果：可能是频次限制（pro_bar 不抛异常只返回空）
            # 重试几次再放弃
            if attempt < retries - 1:
                wait_time = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"[WARN] {ts_code} pro_bar 返回空，等待 {wait_time:.1f}s 后重试 ({attempt + 1}/{retries})")
                time.sleep(wait_time)
            else:
                print(f"[WARN] {ts_code} pro_bar 返回空，已重试 {retries} 次仍为空")
                return None

        except Exception as e:
            error_msg = str(e).lower()

            # 检查是否是频次限制错误
            if "limit" in error_msg or "频繁" in error_msg or "超过" in error_msg:
                wait_time = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"[WARN] 触发频次限制，等待 {wait_time:.1f}s 后重试 ({attempt + 1}/{retries})")
                time.sleep(wait_time)
            else:
                # 其他错误，简单重试
                if attempt < retries - 1:
                    time.sleep(RETRY_BASE_DELAY)
                else:
                    print(f"[ERROR] 获取 {ts_code} 数据失败: {e}")
                    return None

    return None


def fetch_daily_data(
    pro,
    ts_codes: list[str],
    start_date: str,
    end_date: str
) -> Optional[pd.DataFrame]:
    """
    逐只股票获取前复权日线数据（适配 120 积分账号）

    使用 pro_bar(adj="qfq") 获取前复权数据，自动处理除权除息。

    Args:
        pro: Tushare Pro API 实例
        ts_codes: 股票代码列表，格式如 ["688393.SH", "600118.SH"]
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"

    Returns:
        DataFrame 包含 ts_code, trade_date, open, high, low, close, vol, amount
    """
    all_dfs = []
    required_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]  # pro_bar 兼容

    total = len(ts_codes)
    success_count = 0
    fail_count = 0

    for i, ts_code in enumerate(ts_codes):
        print(f"[INFO] 获取 {ts_code} ({i + 1}/{total})...")

        df = fetch_single_stock_daily(pro, ts_code, start_date, end_date)

        if df is not None and not df.empty:
            # 选取需要的列
            df = df[[c for c in required_cols if c in df.columns]]
            # pro_bar(adj="qfq") 对有除权事件的股票可能返回未复权+前复权两行
            # 前复权行在后面，keep="last" 保留前复权数据
            before = len(df)
            df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
            if len(df) < before:
                print(f"[INFO] {ts_code}: 去重 {before} → {len(df)}（pro_bar 返回了重复日期）")
            # pro_bar 返回的数值列可能是字符串，转为 float
            for col in ["open", "high", "low", "close", "vol", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            all_dfs.append(df)
            success_count += 1
        else:
            fail_count += 1

        # 节流：每次请求后等待，避免触发频次限制
        # 最后一只股票不需要等待
        if i < total - 1:
            time.sleep(REQUEST_INTERVAL)

    if not all_dfs:
        print("[ERROR] 未获取到任何数据")
        return None

    # 合并所有数据
    result = pd.concat(all_dfs, ignore_index=True)
    print(f"\n[OK] 成功: {success_count}, 失败: {fail_count}")

    return result


def fetch_market_data(
    config_path: str = None,
    output_path: str = None,
    days: int = 60
) -> pd.DataFrame:
    """
    根据 config/stocks.yaml 获取股票池日线数据并保存

    Args:
        config_path: 配置文件路径，默认使用项目内的 config/stocks.yaml
        output_path: 输出 parquet 文件路径，默认使用 data/raw/market_data.parquet
        days: 回溯天数

    Returns:
        合并后的 DataFrame

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误或数据获取失败
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    if output_path is None:
        output_path = DEFAULT_OUTPUT_PATH
    # 1. 初始化 Tushare
    print("[INFO] 初始化 Tushare API...")
    pro = init_tushare()

    # 2. 读取配置
    config = load_config(config_path)
    stocks = extract_stock_codes(config)
    ts_codes = [s["ts_code"] for s in stocks]
    name_map = {s["ts_code"]: s["name"] for s in stocks}

    print(f"[INFO] 共需获取 {len(ts_codes)} 只股票数据")
    print(f"[INFO] 股票池: {ts_codes}")

    # 3. 计算日期范围
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    print(f"[INFO] 日期范围: {start_date} ~ {end_date}")

    # 4. 获取日线数据
    df = fetch_daily_data(pro, ts_codes, start_date, end_date)

    if df is None or df.empty:
        print("[ERROR] 未获取到任何数据")
        return pd.DataFrame()

    # 5. 验证每只股票是否都获取到数据
    fetched_codes = set(df["ts_code"].unique())
    missing_codes = set(ts_codes) - fetched_codes

    if missing_codes:
        print(f"[WARN] 以下股票未获取到数据: {missing_codes}")
    else:
        print(f"[OK] 所有 {len(ts_codes)} 只股票数据获取成功")

    # 6. 添加股票名称
    df["name"] = df["ts_code"].map(name_map)

    # 7. 打印每只股票的记录数
    print("\n[INFO] 各股票记录数:")
    for ts_code in ts_codes:
        count = len(df[df["ts_code"] == ts_code])
        name = name_map.get(ts_code, "")
        status = "[OK]" if count > 0 else "[MISSING]"
        print(f"  {status} {ts_code} {name}: {count} 条记录")

    # 8. 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # 9. 合并去重保存日线数据
    df = _merge_save(df, Path(output_path))
    print(f"[INFO] 总记录数: {len(df)}")

    # 10. 获取 daily_basic（PE/PB/PS/市值）- anchor + core_universe 用于估值对比
    anchor_code = config.get("anchor", {}).get("code", "")
    core_codes = [item["code"] for item in config.get("core_universe", []) if item.get("active", True)]

    # 需要获取 daily_basic 的股票：anchor + core_universe（去重）
    valuation_codes = list(set([anchor_code] + core_codes))
    valuation_codes = [c for c in valuation_codes if c]  # 过滤空值

    if valuation_codes:
        _fetch_daily_basic_all(pro, valuation_codes, start_date, end_date, output_dir)

    # 获取 anchor 的资金流向数据
    if anchor_code:
        _fetch_moneyflow(pro, anchor_code, start_date, end_date, output_dir)

    return df


def _fetch_daily_basic_all(pro, ts_codes: list[str], start_date: str, end_date: str, output_dir: Path):
    """
    获取多只股票的每日基本面指标（PE/PB/PS/市值），保存到 raw 层

    Args:
        pro: Tushare API 实例
        ts_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        output_dir: 输出目录
    """
    all_dfs = []

    for i, ts_code in enumerate(ts_codes):
        df = None
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[INFO] 获取 {ts_code} daily_basic ({i + 1}/{len(ts_codes)})...")
                df = pro.daily_basic(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,pe,pe_ttm,pb,ps_ttm,total_mv,circ_mv,turnover_rate,turnover_rate_f,free_share"
                )
                break
            except Exception as e:
                error_msg = str(e).lower()
                if attempt < MAX_RETRIES - 1 and ("timeout" in error_msg or "timed out" in error_msg):
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"[WARN] daily_basic {ts_code} 超时，{wait:.0f}s 后重试 ({attempt+1}/{MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    print(f"[WARN] daily_basic {ts_code} 获取失败: {e}")
                    df = None
                    break

        if df is not None and not df.empty:
            all_dfs.append(df)
            print(f"[INFO] daily_basic {ts_code}: {len(df)} 条")

        # 节流
        if i < len(ts_codes) - 1:
            time.sleep(REQUEST_INTERVAL)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        out = output_dir / "daily_basic.parquet"
        combined = _merge_save(combined, out)
        print(f"[INFO] daily_basic: 共 {len(combined)} 条")
    else:
        print("[WARN] daily_basic: 所有股票返回空数据")


def _fetch_daily_basic(pro, ts_code: str, start_date: str, end_date: str, output_dir: Path):
    """获取单只股票的每日基本面指标（PE/PB/市值），保存到 raw 层"""
    try:
        df = pro.daily_basic(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,pe,pe_ttm,pb,ps_ttm,total_mv,circ_mv,turnover_rate,turnover_rate_f,free_share"
        )
        if df is not None and not df.empty:
            out = output_dir / "daily_basic.parquet"
            df.to_parquet(out, index=False)
            print(f"[INFO] daily_basic: {len(df)} 条 → {out}")
        else:
            print("[WARN] daily_basic: 返回空数据")
    except Exception as e:
        print(f"[WARN] daily_basic 获取失败（不影响主流程）: {e}")


def _fetch_moneyflow(pro, ts_code: str, start_date: str, end_date: str, output_dir: Path):
    """获取资金流向数据，保存到 raw 层"""
    try:
        df = pro.moneyflow(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,buy_sm_vol,sell_sm_vol,buy_md_vol,sell_md_vol,buy_lg_vol,sell_lg_vol,buy_elg_vol,sell_elg_vol,net_mf_vol,net_mf_amount"
        )
        if df is not None and not df.empty:
            out = output_dir / "moneyflow.parquet"
            df.to_parquet(out, index=False)
            print(f"[INFO] moneyflow: {len(df)} 条 → {out}")
        else:
            print("[WARN] moneyflow: 返回空数据")
    except Exception as e:
        print(f"[WARN] moneyflow 获取失败（不影响主流程）: {e}")


def _fetch_moneyflow_all(pro, ts_codes: list[str], start_date: str, end_date: str, output_dir: Path):
    """
    获取多只股票的资金流向数据，保存到 raw 层

    Args:
        pro: Tushare API 实例
        ts_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        output_dir: 输出目录
    """
    all_dfs = []

    for i, ts_code in enumerate(ts_codes):
        df = None
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[INFO] 获取 {ts_code} moneyflow ({i + 1}/{len(ts_codes)})...")
                df = pro.moneyflow(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,buy_sm_vol,sell_sm_vol,buy_md_vol,sell_md_vol,buy_lg_vol,sell_lg_vol,buy_elg_vol,sell_elg_vol,net_mf_vol,net_mf_amount"
                )
                break
            except Exception as e:
                error_msg = str(e).lower()
                if attempt < MAX_RETRIES - 1 and ("timeout" in error_msg or "timed out" in error_msg):
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"[WARN] moneyflow {ts_code} 超时，{wait:.0f}s 后重试 ({attempt+1}/{MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    print(f"[WARN] moneyflow {ts_code} 获取失败: {e}")
                    df = None
                    break

        if df is not None and not df.empty:
            all_dfs.append(df)
            print(f"[INFO] moneyflow {ts_code}: {len(df)} 条")

        # 节流
        if i < len(ts_codes) - 1:
            time.sleep(REQUEST_INTERVAL)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        out = output_dir / "moneyflow.parquet"
        combined = _merge_save(combined, out)
        print(f"[INFO] moneyflow: 共 {len(combined)} 条")
    else:
        print("[WARN] moneyflow: 所有股票返回空数据")


def fetch_for_registry(
    registry,
    output_path: str = None,
    days: int = 60
) -> pd.DataFrame:
    """
    根据 PoolRegistry 获取股票池日线数据并保存

    MVP 入口使用，统一配置源为 pools.yaml

    Args:
        registry: PoolRegistry 实例
        output_path: 输出 parquet 文件路径
        days: 回溯天数

    Returns:
        合并后的 DataFrame
    """
    if output_path is None:
        output_path = DEFAULT_OUTPUT_PATH

    # 1. 初始化 Tushare
    print("[INFO] 初始化 Tushare API...")
    pro = init_tushare()

    # 2. 从 PoolRegistry 获取股票列表
    ts_codes = registry.get_all_symbols()
    anchor = registry.get_anchor()

    # 构建名称映射
    name_map = {}
    for symbol in ts_codes:
        inst = registry.get_instrument(symbol)
        if inst:
            name_map[symbol] = inst.name
    name_map[anchor.symbol] = anchor.name

    print(f"[INFO] 共需获取 {len(ts_codes)} 只股票数据")
    print(f"[INFO] 股票池: {ts_codes}")

    # 3. 计算日期范围（增量：向前补新 + 向后扩展 + 个股空洞回填）
    end_date = datetime.now().strftime("%Y%m%d")
    earliest_needed = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    market_parquet = Path(output_path)
    per_stock_ranges: dict[str, tuple[str, str]] = {}  # 个股需要回填的日期范围
    if market_parquet.exists():
        try:
            # 读取完整数据以检测个股空洞
            existing = pd.read_parquet(market_parquet, columns=["ts_code", "trade_date"])
            if not existing.empty:
                min_date = existing["trade_date"].min()
                max_date = existing["trade_date"].max()
                if min_date <= earliest_needed:
                    # 已有数据够老，只需向前补新
                    start_date = max_date
                    print(f"[INFO] 增量模式：已有数据至 {max_date}，从该日期开始拉取")
                else:
                    # 需要向后扩展历史
                    start_date = earliest_needed
                    print(f"[INFO] 扩展模式：已有数据最早 {min_date}，需扩展至 {earliest_needed}")

                # 检测个股空洞：在全局交易日历中，如果某只股票缺少某天数据，
                # 说明 pro_bar 漏拉，需要回填
                try:
                    existing_full = pd.read_parquet(market_parquet, columns=["ts_code", "trade_date"])
                    recent = existing_full[existing_full["trade_date"] >= earliest_needed]
                    if not recent.empty:
                        # 全局交易日历 = 至少一半股票有数据的日期
                        all_dates = recent["trade_date"].value_counts()
                        n_stocks = len(recent["ts_code"].unique())
                        trading_dates = set(all_dates[all_dates >= n_stocks * 0.5].index)
                        if trading_dates:
                            for ts_code in recent["ts_code"].unique():
                                stock_dates = set(recent[recent["ts_code"] == ts_code]["trade_date"])
                                missing_dates = trading_dates - stock_dates
                                if missing_dates:
                                    gap_start = min(missing_dates)
                                    stock_before = existing_full[
                                        (existing_full["ts_code"] == ts_code) &
                                        (existing_full["trade_date"] < gap_start)
                                    ].sort_values("trade_date")
                                    if not stock_before.empty:
                                        pull_start = stock_before["trade_date"].iloc[-1]
                                    else:
                                        pull_start = earliest_needed
                                    per_stock_ranges[ts_code] = (pull_start, end_date)
                        if per_stock_ranges:
                            codes_str = ", ".join(per_stock_ranges.keys())
                            print(f"[INFO] 检测到 {len(per_stock_ranges)} 只股票有日期空洞（pro_bar 漏拉）: {codes_str}")
                except Exception:
                    pass  # 空洞检测失败不影响主流程
            else:
                start_date = earliest_needed
        except Exception:
            start_date = earliest_needed
    else:
        start_date = earliest_needed
    print(f"[INFO] 日期范围: {start_date} ~ {end_date}")

    # 4. 获取日线数据（批量 + 个股回填）
    df = fetch_daily_data(pro, ts_codes, start_date, end_date)

    if df is None or df.empty:
        print("[ERROR] 未获取到任何数据")
        return pd.DataFrame()

    # 4b. 个股空洞回填
    if per_stock_ranges:
        print(f"[INFO] 开始回填 {len(per_stock_ranges)} 只股票的数据空洞...")
        for ts_code, (s, e) in per_stock_ranges.items():
            print(f"[INFO] 回填 {ts_code}: {s} ~ {e}")
            stock_df = fetch_single_stock_daily(pro, ts_code, s, e)
            if stock_df is not None and not stock_df.empty:
                stock_df = stock_df[[c for c in stock_df.columns if c in
                    ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]]]
                stock_df = stock_df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
                for col in ["open", "high", "low", "close", "vol", "amount"]:
                    if col in stock_df.columns:
                        stock_df[col] = pd.to_numeric(stock_df[col], errors="coerce")
                df = pd.concat([df, stock_df], ignore_index=True)
                print(f"[OK] {ts_code} 回填 {len(stock_df)} 条")
            else:
                print(f"[WARN] {ts_code} 回填失败，pro_bar 仍返回空")

    # 5. 验证每只股票是否都获取到数据
    fetched_codes = set(df["ts_code"].unique())
    missing_codes = set(ts_codes) - fetched_codes

    if missing_codes:
        print(f"[WARN] 以下股票未获取到数据: {missing_codes}")
    else:
        print(f"[OK] 所有 {len(ts_codes)} 只股票数据获取成功")

    # 6. 添加股票名称
    df["name"] = df["ts_code"].map(name_map)

    # 7. 打印每只股票的记录数
    print("\n[INFO] 各股票记录数:")
    for ts_code in ts_codes:
        count = len(df[df["ts_code"] == ts_code])
        name = name_map.get(ts_code, "")
        status = "[OK]" if count > 0 else "[MISSING]"
        print(f"  {status} {ts_code} {name}: {count} 条记录")

    # 8. 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # 9. 合并去重保存日线数据
    df = _merge_save(df, Path(output_path))
    print(f"[INFO] 总记录数: {len(df)}")

    # 9.5 补缺：检查日期覆盖不足的股票，单独拉取
    if market_parquet.exists():
        try:
            existing_df = pd.read_parquet(market_parquet, columns=["ts_code", "trade_date"])
            partial_codes = []
            for ts_code in ts_codes:
                stock_dates = existing_df[existing_df["ts_code"] == ts_code]["trade_date"]
                if stock_dates.empty:
                    partial_codes.append(ts_code)
                else:
                    min_date = stock_dates.min()
                    if isinstance(min_date, pd.Timestamp):
                        min_str = min_date.strftime("%Y%m%d")
                    else:
                        min_str = str(min_date)[:8]
                    if min_str > earliest_needed:
                        partial_codes.append(ts_code)
            if partial_codes:
                print(f"[INFO] 补缺模式：{len(partial_codes)} 只股票数据覆盖不足，尝试补拉")
                df_missing = fetch_daily_data(pro, partial_codes, earliest_needed, end_date)
                if df_missing is not None and not df_missing.empty:
                    required_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
                    df_missing = df_missing[[c for c in required_cols if c in df_missing.columns]]
                    df_missing["name"] = df_missing["ts_code"].map(name_map)
                    df = _merge_save(df_missing, market_parquet)
                    print(f"[INFO] 补缺后总记录数: {len(df)}")
                else:
                    print(f"[WARN] 补缺失败：{partial_codes} 仍无数据")
        except Exception as e:
            print(f"[WARN] 补缺检查失败: {e}")

    # 10. 获取 daily_basic（所有池子成员的估值/换手率数据）
    # 需要：所有池子成员的 turnover_rate、pe_ttm、pb
    all_symbols = registry.get_all_symbols()

    if all_symbols:
        _fetch_daily_basic_all(pro, all_symbols, start_date, end_date, output_dir)

    # 11. 获取所有池子成员的资金流向数据（而非仅 anchor）
    all_symbols = registry.get_all_symbols()
    _fetch_moneyflow_all(pro, all_symbols, start_date, end_date, output_dir)

    # 12. 同步 normalized 层（确保 raw 更新后 normalized 不落后）
    try:
        from src.price.normalizer import normalize
        normalize()
    except Exception as e:
        print(f"[WARN] normalized 同步失败: {e}")

    return df


if __name__ == "__main__":
    df = fetch_market_data()
    print("\n数据概览:")
    print(df.head(10))
    print(f"\n股票数量: {df['ts_code'].nunique()}")
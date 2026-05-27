#!/usr/bin/env python
"""
retrieval_monitor.log 健康仪表盘

用法:
    python monitor.py                  # 默认展示最近 100 条
    python monitor.py --n 50           # 展示最近 50 条
    python monitor.py --watch          # 每 5 秒刷新（Ctrl+C 退出）
    python monitor.py --n 200 --watch  # 最近 200 条，持续监控

日志格式（JSON Lines）:
    {"timestamp": "2026-05-18T10:30:00", "query": "...",
     "latency_ms": 5700, "return_code": 0, "status": "success",
     "error": null, "output_len": 1234}
"""
import json
import os
import sys
import time
import argparse
from collections import Counter
from datetime import datetime
from typing import List, Dict


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(CURRENT_DIR, "retrieval_monitor.log")


def percentile(sorted_vals: List[float], p: float) -> float:
    """计算百分位数（无 numpy 依赖）"""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[-1]
    d = k - f
    return sorted_vals[f] * (1 - d) + sorted_vals[c] * d


def load_entries(log_path: str, max_entries: int) -> List[Dict]:
    if not os.path.exists(log_path):
        return []
    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-max_entries:]


def render_dashboard(log_path: str, n: int):
    entries = load_entries(log_path, n)

    if not entries:
        print("\n" + "=" * 58)
        print("  📭 retrieval_monitor.log 暂无数据")
        print("  " + "=" * 56)
        print("  等待子进程调用产生日志后重试")
        return

    total = len(entries)
    successes = [e for e in entries if e.get("status") == "success"]
    failures = [e for e in entries if e.get("status") != "success"]
    success_rate = len(successes) / total * 100 if total > 0 else 0

    all_latencies = sorted([e["latency_ms"] for e in entries if e.get("latency_ms", 0) > 0])
    success_latencies = sorted([e["latency_ms"] for e in successes if e.get("latency_ms", 0) > 0])

    error_counter = Counter()
    for e in failures:
        label = e.get("error", e.get("status", "unknown"))[:60]
        error_counter[label] += 1

    time_range_start = entries[0]["timestamp"][:19]
    time_range_end = entries[-1]["timestamp"][:19]

    print("\n" + "=" * 58)
    print(f"  🔍 子进程检索健康仪表盘  (最近 {total} 次调用)")
    print("=" * 58)
    print(f"  时间范围   {time_range_start}  →  {time_range_end}")
    print(f"  总调用次数 {total}")
    print(f"  成功率     {success_rate:.1f}%  ({len(successes)}/{total})")
    print(f"  失败次数   {len(failures)}")
    print("-" * 58)

    if all_latencies:
        avg_ms = sum(all_latencies) / len(all_latencies)
        p50_ms = percentile(all_latencies, 50)
        p95_ms = percentile(all_latencies, 95)
        p99_ms = percentile(all_latencies, 99)
        print(f"  平均延迟   {avg_ms:8.0f} ms")
        print(f"  P50 延迟   {p50_ms:8.0f} ms")
        print(f"  P95 延迟   {p95_ms:8.0f} ms")
        print(f"  P99 延迟   {p99_ms:8.0f} ms")
        print(f"  最快/最慢  {all_latencies[0]:.0f} ms  /  {all_latencies[-1]:.0f} ms")
    else:
        print("  延迟数据   暂无")

    if success_latencies:
        p95_success = percentile(success_latencies, 95)
        avg_success = sum(success_latencies) / len(success_latencies)
        print("-" * 58)
        print(f"  成功 P95    {p95_success:8.0f} ms")
        print(f"  成功平均    {avg_success:8.0f} ms")

    if error_counter:
        print("-" * 58)
        print(f"  错误分布 ({len(failures)} 次)")
        for err, cnt in error_counter.most_common(8):
            bar_len = int(cnt / max(error_counter.values()) * 20)
            bar = "█" * bar_len
            print(f"  {err[:45]:<45} {cnt:>4}  {bar}")

    print("-" * 58)
    print(f"  日志文件   {log_path}")
    print("=" * 58)

    recent = entries[-10:]
    print("\n  最近 10 次调用:")
    print("  " + "-" * 75)
    print(f"  {'时间':<20} {'状态':<10} {'延迟':>8} {'返回码':>8}")
    print("  " + "-" * 75)
    for e in recent:
        ts = e.get("timestamp", "")[11:19]
        status = e.get("status", "?")
        icon = {"success": "✅", "error": "❌", "timeout": "⏱️", "not_found": "🔍"}.get(status, "❓")
        lat = f"{e.get('latency_ms', 0):.0f}ms"
        rc = str(e.get("return_code", "N/A"))
        print(f"  {ts:<20} {icon} {status:<7} {lat:>8} {rc:>8}")
    print("  " + "-" * 75)
    print()


def main():
    parser = argparse.ArgumentParser(description="子进程检索健康仪表盘")
    parser.add_argument("--n", type=int, default=100, help="展示最近 N 条记录（默认 100）")
    parser.add_argument("--watch", action="store_true", help="持续监控模式（每 5 秒刷新）")
    parser.add_argument("--log", type=str, default=DEFAULT_LOG_PATH, help="日志文件路径")
    args = parser.parse_args()

    if args.watch:
        print(f"🔄 持续监控模式已启动（每 5 秒刷新，Ctrl+C 退出）")
        print(f"   监控日志: {args.log}")
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                print(f"  ⏰ 刷新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                render_dashboard(args.log, args.n)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
    else:
        render_dashboard(args.log, args.n)


if __name__ == "__main__":
    main()
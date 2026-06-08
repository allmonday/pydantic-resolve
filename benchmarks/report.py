"""Benchmark regression detection and report generation.

Usage:
    uv run python benchmarks/report.py                          # check regressions
    uv run python benchmarks/report.py --threshold 15           # custom threshold
    uv run python benchmarks/report.py --output benchmarks/results/benchmark_report.html
"""

import argparse
import json
import os
import sys

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "results", "benchmark_history.json")

SCENARIO_LABELS = {
    "Medium_Q1": "1-level (200 tasks)",
    "Medium_Q2": "2-level (200 tasks)",
    "Medium_Q3": "3-level linear (~60 posts)",
    "Medium_Q4": "wide parallel (~60 posts)",
    "Large_Q1": "1-level (1K tasks)",
    "Large_Q2": "2-level (1K tasks)",
    "Large_Q3": "3-level linear (~200 posts)",
    "Large_Q4": "wide parallel (~200 posts)",
    "XLarge_Q1": "1-level (2.5K tasks)",
    "XLarge_Q2": "2-level (2.5K tasks)",
    "XLarge_Q3": "3-level linear (~800 posts)",
    "XLarge_Q4": "wide parallel (~800 posts)",
}

SCALE_ORDER = ["Medium", "Large", "XLarge"]
Q_ORDER = ["Q1", "Q2", "Q3", "Q4"]


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark regression check and report")
    p.add_argument("--history", default=HISTORY_PATH, help="Path to benchmark_history.json")
    p.add_argument("--threshold", type=float, default=20.0, help="Regression threshold %%")
    p.add_argument("--output", default=None, help="Output HTML report path")
    return p.parse_args()


def load_history(path):
    if not os.path.exists(path):
        print(f"No history file found at {path}")
        return None
    with open(path) as f:
        return json.load(f)


def check_regression(history, threshold):
    entries = history["entries"]
    if len(entries) < 2:
        print("Not enough historical data for comparison (need at least 2 entries).")
        return []

    baseline = entries[-2]
    current = entries[-1]
    regressions = []

    print(f"\nComparing {current['version']} vs baseline {baseline['version']}:")
    print(f"  {'Metric':<20s} │ {'Baseline':>10s} → {'Current':>10s} │ {'Change':>8s} │ Status")
    print(f"  {'─' * 20}─┼─{'─' * 10}─{'─' * 10}─┼─{'─' * 8}─┼─{'─' * 10}")

    all_keys = sorted(
        set(baseline["results"].keys()) & set(current["results"].keys()),
        key=lambda k: (SCALE_ORDER.index(k.split("_")[0]) if "_" in k and k.split("_")[0] in SCALE_ORDER else 99, Q_ORDER.index(k.split("_")[1]) if "_" in k and k.split("_")[1] in Q_ORDER else 99)
    )

    for key in all_keys:
        b_p50 = baseline["results"][key]["p50_ms"]
        c_p50 = current["results"][key]["p50_ms"]
        if b_p50 == 0:
            continue
        change_pct = ((c_p50 - b_p50) / b_p50) * 100
        status = "REGRESSION" if change_pct > threshold else ("improved" if change_pct < -5 else "OK")

        if change_pct > threshold:
            regressions.append(key)

        print(f"  {key:<20s} │ {b_p50:>9.2f}ms → {c_p50:>9.2f}ms │ {change_pct:>+7.1f}% │ {status}")

    if regressions:
        print(f"\n  {len(regressions)} regression(s) detected (threshold: {threshold}%).")
    else:
        print(f"\n  No regressions detected (threshold: {threshold}%).")

    return regressions


def generate_html_report(history, output_path):
    entries = history["entries"]
    if not entries:
        print("No entries to report.")
        return

    all_keys = []
    for e in entries:
        for k in e["results"]:
            if k not in all_keys:
                all_keys.append(k)
    all_keys.sort(key=lambda k: (SCALE_ORDER.index(k.split("_")[0]) if "_" in k and k.split("_")[0] in SCALE_ORDER else 99, Q_ORDER.index(k.split("_")[1]) if "_" in k and k.split("_")[1] in Q_ORDER else 99))

    rows_html = ""
    for key in all_keys:
        label = SCENARIO_LABELS.get(key, key)
        cells = f"<td><strong>{label}</strong></td>"
        for entry in entries:
            r = entry["results"].get(key)
            if r:
                cells += f"<td>{r['p50_ms']:.2f}</td><td>{r['p95_ms']:.2f}</td>"
            else:
                cells += "<td>-</td><td>-</td>"
        rows_html += f"<tr>{cells}</tr>\n"

    version_headers = ""
    for entry in entries:
        ts = entry["timestamp"][:10]
        version_headers += f'<th colspan="2">{entry["version"]} ({ts})</th>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>pydantic-resolve Benchmark</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; background: #f8f9fa; }}
  h1 {{ color: #1a1a2e; }}
  table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ padding: 8px 12px; text-align: right; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #1a1a2e; color: white; }}
  td:first-child {{ text-align: left; font-weight: 500; }}
  tr:hover {{ background: #f0f4ff; }}
  .footer {{ margin-top: 2rem; color: #666; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>pydantic-resolve Benchmark Report</h1>
<p>P50 and P95 latency in milliseconds. Lower is better.</p>
<table>
<thead>
<tr><th>Scenario</th>{version_headers}</tr>
<tr><th></th>{"".join('<th>P50</th><th>P95</th>' for _ in entries)}</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
<div class="footer">
<p>Generated from {len(entries)} historical runs. Data: <code>benchmarks/results/benchmark_history.json</code></p>
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"  HTML report saved to {output_path}")


def main():
    args = parse_args()
    history = load_history(args.history)
    if history is None:
        sys.exit(1)

    regressions = check_regression(history, args.threshold)

    if args.output:
        generate_html_report(history, args.output)

    if regressions:
        sys.exit(1)


if __name__ == "__main__":
    main()

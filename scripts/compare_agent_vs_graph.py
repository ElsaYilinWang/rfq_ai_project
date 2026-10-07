# scripts/compare_agent_vs_graph.py

"""
Phase 18a, step 4: live comparison of the original agent loop and the
LangGraph version, on real Anthropic calls.

tests/test_supplier_graph.py proves the two match on SCRIPTED model
responses. It cannot prove the graph works against the real API (the
model's replies are sent back as plain dicts) or that the real model
picks the same tools through it. This script checks both.

Because the model is non-deterministic, one old run vs one graph run
proves nothing: any difference might just be noise. So every item is
run through the OLD agent twice and the GRAPH once:

  old vs old      -> the noise baseline (how often the same code
                     disagrees with itself)
  old vs graph    -> the comparison that matters

The graph passes if it disagrees with the old agent no more often than
the old agent disagrees with itself.

"Agree" means the same completion status, the same tool sequence, the
same manufacturer identified, and the same supplier_candidates_found.
Free-text fields (summary, recommended_next_step) are shown but not
scored: wording varies run to run even when the decision is identical.

Makes real, paid calls (Sonnet 5, roughly $0.02-0.03 per run). Not run
in CI. Run it by hand:

    python scripts/compare_agent_vs_graph.py
"""

import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

REPORT_PATH = Path(__file__).parent / "compare_agent_vs_graph_report.json"
OLD_RUNS_PER_ITEM = 2

# The two sample-RFQ items the API serves, plus two more that exercise
# different tool paths (manufacturer named in the text; no manufacturer
# and a standard designation).
ITEMS = [
    {"label": "abb_breaker_known_mfr", "item_description": "ABB circuit breaker 10A",
     "material_number": "MAT-001", "known_manufacturer": "ABB", "known_part_number": "CB-10A"},
    {"label": "seal_kit_heat_exchanger", "item_description": "Seal kit for heat exchanger",
     "material_number": "MAT-002", "known_manufacturer": None, "known_part_number": None},
    {"label": "siemens_plc_in_text", "item_description": "Siemens S7-1200 PLC starter kit with power supply",
     "material_number": "MAT-003", "known_manufacturer": None, "known_part_number": None},
    {"label": "bearing_no_brand", "item_description": "Bearing 6205-2RS sealed, quantity 15",
     "material_number": "MAT-004", "known_manufacturer": None, "known_part_number": None},
]


def fingerprint(result) -> dict:
    """What must agree for two runs to count as the same behavior."""
    return {
        "completed": result.completed,
        "tools": [c.tool_name for c in result.tool_calls],
        "manufacturer_identified": result.manufacturer_identified,
        "supplier_candidates_found": result.supplier_candidates_found,
    }


def compare(items, run_old, run_graph, old_runs=OLD_RUNS_PER_ITEM):
    """Pure over the two runner callables, so the logic is testable
    without any API call."""
    rows = []
    for item in items:
        base = {k: v for k, v in item.items() if k != "label"}
        old_results = [
            run_old(**base, trace_id=f"cmp_{item['label']}_old{i + 1}")
            for i in range(old_runs)
        ]
        graph_result = run_graph(**base, trace_id=f"cmp_{item['label']}_graph")

        old_prints = [fingerprint(r) for r in old_results]
        graph_print = fingerprint(graph_result)
        rows.append({
            "label": item["label"],
            "old_runs": [r.model_dump() for r in old_results],
            "graph_run": graph_result.model_dump(),
            "old_vs_old_agree": old_prints[0] == old_prints[1] if old_runs >= 2 else None,
            "old_vs_graph_agree": [p == graph_print for p in old_prints],
            "fingerprints": {"old": old_prints, "graph": graph_print},
        })

    old_all = [r for row in rows for r in row["old_runs"]]
    graph_all = [row["graph_run"] for row in rows]
    cross = [a for row in rows for a in row["old_vs_graph_agree"]]
    baseline = [row["old_vs_old_agree"] for row in rows if row["old_vs_old_agree"] is not None]

    def stats(results):
        return {
            "runs": len(results),
            "total_cost_usd": round(sum(r["total_cost_usd"] for r in results), 4),
            "mean_cost_usd": round(statistics.mean(r["total_cost_usd"] for r in results), 4),
            "median_model_latency_s": round(statistics.median(r["total_latency_seconds"] for r in results), 2),
            "mean_tool_calls": round(statistics.mean(len(r["tool_calls"]) for r in results), 2),
        }

    return {
        "rows": rows,
        "baseline_old_vs_old": f"{sum(baseline)}/{len(baseline)} items agree" if baseline else "n/a",
        "old_vs_graph": f"{sum(cross)}/{len(cross)} comparisons agree",
        "baseline_agree_rate": round(sum(baseline) / len(baseline), 3) if baseline else None,
        "cross_agree_rate": round(sum(cross) / len(cross), 3) if cross else None,
        "old_stats": stats(old_all),
        "graph_stats": stats(graph_all),
    }


def print_report(report):
    print("\n" + "=" * 78)
    print("OLD AGENT LOOP vs LANGGRAPH VERSION -- live run")
    print("=" * 78)
    for row in report["rows"]:
        print(f"\n  {row['label']}")
        for i, r in enumerate(row["old_runs"], 1):
            tools = " > ".join(c["tool_name"] for c in r["tool_calls"]) or "(no tools)"
            print(f"    old{i}   completed={r['completed']!s:5}  mfr={r['manufacturer_identified']!s:10}  "
                  f"found={r['supplier_candidates_found']!s:5}  ${r['total_cost_usd']:.4f}  {tools}")
        g = row["graph_run"]
        gtools = " > ".join(c["tool_name"] for c in g["tool_calls"]) or "(no tools)"
        print(f"    graph  completed={g['completed']!s:5}  mfr={g['manufacturer_identified']!s:10}  "
              f"found={g['supplier_candidates_found']!s:5}  ${g['total_cost_usd']:.4f}  {gtools}")
        print(f"    old vs old agree: {row['old_vs_old_agree']}    "
              f"old vs graph agree: {row['old_vs_graph_agree']}")

    print("\n" + "-" * 78)
    print(f"Noise baseline (old vs old):  {report['baseline_old_vs_old']}")
    print(f"Old vs graph:                 {report['old_vs_graph']}")
    o, g = report["old_stats"], report["graph_stats"]
    print(f"\n{'':<26}{'old':>12}{'graph':>12}")
    print(f"{'runs':<26}{o['runs']:>12}{g['runs']:>12}")
    print(f"{'mean cost / run':<26}{'$' + format(o['mean_cost_usd'], '.4f'):>12}{'$' + format(g['mean_cost_usd'], '.4f'):>12}")
    print(f"{'median model latency':<26}{o['median_model_latency_s']:>11}s{g['median_model_latency_s']:>11}s")
    print(f"{'mean tool calls / run':<26}{o['mean_tool_calls']:>12}{g['mean_tool_calls']:>12}")
    print(f"\nTotal cost of this comparison: "
          f"${o['total_cost_usd'] + g['total_cost_usd']:.4f}")


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (checked after load_dotenv()). "
              "Refusing to run: every call would fail and the report would be meaningless.")
        sys.exit(1)

    from agent.supplier_agent import run_supplier_search_agent
    from agent.supplier_graph import run_supplier_search_graph

    runs = len(ITEMS) * (OLD_RUNS_PER_ITEM + 1)
    print(f"About to make {runs} real agent runs (~$0.02-0.03 each).")

    report = compare(ITEMS, run_supplier_search_agent, run_supplier_search_graph)
    print_report(report)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()

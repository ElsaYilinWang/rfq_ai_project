# scripts/langgraph_toy_capped.py

"""
Toy loop, version 2: the cap is enforced by OUR router, not by the
framework's recursion_limit.

Why: in scripts/langgraph_toy_loop.py, hitting recursion_limit raised
GraphRecursionError and the partial run was lost. The old agent
(agent/supplier_agent.py) instead returned a valid, reviewable result
when it hit MAX_ITERATIONS. Here the same thing is done in graph terms:

  - `max_model_calls` lives in state, next to the counter it limits
  - after run_tool, a router checks the counter and sends the run to a
    `capped` node (the equivalent of the old code after the for-loop)
    instead of back to the model
  - the cap check sits on the edge leaving run_tool, not the one leaving
    call_model, because the old loop still ran the tool on its last
    iteration before giving up -- this copies that ordering
  - if the model finishes on its own, even on its last allowed call, the
    run ends normally and is NOT marked capped (old behavior: a final
    answer on the last iteration is accepted)

recursion_limit is still passed to graph.invoke() in experiment 3, to
show what it is still for.
"""
import operator
from typing import Annotated, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    wants_rounds: int      # how many tool rounds the fake model wants
    max_model_calls: int   # OUR cap, in state (the old MAX_ITERATIONS)
    model_calls: int       # the counter the cap is checked against
    log: Annotated[list[str], operator.add]


def call_model(state: State) -> dict:
    n = state["model_calls"] + 1
    return {"model_calls": n, "log": [f"model call #{n}"]}


def run_tool(state: State) -> dict:
    return {"log": [f"tool ran (after model call #{state['model_calls']})"]}


def capped(state: State) -> dict:
    # Stands in for the old code after the for-loop: a valid,
    # reviewable "did not finish" result instead of an exception.
    return {"log": [f"CAPPED after {state['model_calls']} model calls"]}


def after_model(state: State) -> str:
    # Did the model ask for another tool, or is it finished?
    if state["model_calls"] <= state["wants_rounds"]:
        return "run_tool"
    return END


def after_tool(state: State) -> str:
    # The cap check: our router, our counter.
    if state["model_calls"] >= state["max_model_calls"]:
        return "capped"
    return "call_model"


builder = StateGraph(State)
builder.add_node("call_model", call_model)
builder.add_node("run_tool", run_tool)
builder.add_node("capped", capped)
builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", after_model, ["run_tool", END])
builder.add_conditional_edges("run_tool", after_tool, ["capped", "call_model"])
builder.add_edge("capped", END)
graph = builder.compile()


def show(title, wants_rounds, max_model_calls, limit=None):
    print(f"\n=== {title} ===")
    config = {"recursion_limit": limit} if limit else {}
    try:
        result = graph.invoke(
            {
                "wants_rounds": wants_rounds,
                "max_model_calls": max_model_calls,
                "model_calls": 0,
                "log": [],
            },
            config,
        )
        for line in result["log"]:
            print("  ", line)
        print(f"   -> returned normally, {len(result['log'])} steps logged")
    except GraphRecursionError as e:
        print("   -> GraphRecursionError raised (no partial result)")
        print("     ", str(e).split("\n")[0])


if __name__ == "__main__":
    show("Experiment 1: model NEVER stops, cap = 3, default recursion_limit",
         wants_rounds=999, max_model_calls=3)
    show("Experiment 2: model finishes on its own, cap = 3",
         wants_rounds=1, max_model_calls=3)
    show("Experiment 3: cap misconfigured (999), recursion_limit = 10",
         wants_rounds=999, max_model_calls=999, limit=10)
    show("Experiment 4: model finishes exactly on its LAST allowed call, cap = 3",
         wants_rounds=2, max_model_calls=3)

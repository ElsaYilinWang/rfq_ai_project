# scripts/langgraph_toy_loop.py
"""
A deliberately tiny stand-in for the supplier agent's loop, to learn
LangGraph's core ideas with no API key, no cost, and no project code:

  state   -> a dict that flows through the graph
  nodes   -> plain functions: take state, return a PARTIAL update
  edges   -> which node runs next (conditional edges = a router function)
  limit   -> recursion_limit, enforced by the framework

call_model plays the model (it "asks for a tool" until it has been
called `wants_rounds` times); run_tool plays a tool call.
"""
import operator
from typing import Annotated, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    wants_rounds: int                       # how many tool rounds the fake model wants
    model_calls: int                        # how many times call_model has run
    log: Annotated[list[str], operator.add]  # a "reducer": updates are APPENDED, not replaced


def call_model(state: State) -> dict:
    n = state["model_calls"] + 1
    return {"model_calls": n, "log": [f"model call #{n}"]}


def run_tool(state: State) -> dict:
    return {"log": [f"tool ran (after model call #{state['model_calls']})"]}


def route_after_model(state: State) -> str:
    # the "router": decides the next node
    if state["model_calls"] <= state["wants_rounds"]:
        return "run_tool"
    return END


builder = StateGraph(State)
builder.add_node("call_model", call_model)
builder.add_node("run_tool", run_tool)
builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", route_after_model, ["run_tool", END])
builder.add_edge("run_tool", "call_model")
graph = builder.compile()


def show(title, wants_rounds, limit=None):
    print(f"\n=== {title} ===")
    config = {"recursion_limit": limit} if limit else {}
    try:
        result = graph.invoke(
            {"wants_rounds": wants_rounds, "model_calls": 0, "log": []}, config
        )
        for line in result["log"]:
            print("  ", line)
        print(f"   -> finished normally, {result['model_calls']} model calls")
    except GraphRecursionError as e:
        print("   -> GraphRecursionError raised")
        print("     ", str(e).split("\n")[0])


def model_calls_before_error(limit, wants_rounds=999):
    """
    How many times did call_model run before the framework stopped the
    loop? graph.invoke() loses this on error (it only raises), so we use
    graph.stream(), which hands us each node's update as it happens.
    """
    ran = []
    try:
        for update in graph.stream(
            {"wants_rounds": wants_rounds, "model_calls": 0, "log": []},
            {"recursion_limit": limit},
            stream_mode="updates",
        ):
            ran.append(next(iter(update)))
    except GraphRecursionError:
        pass
    return ran.count("call_model"), ran


if __name__ == "__main__":
    show("Experiment 1: model wants 2 tool rounds, default limit", wants_rounds=2)
    show("Experiment 2: model NEVER stops, limit = 6", wants_rounds=999, limit=6)

    print("\n=== Experiment 3: how far did it get? ===")
    for limit in (4, 6, 8):
        calls, ran = model_calls_before_error(limit)
        print(f"   limit={limit}: model ran {calls}x   nodes: {ran}")

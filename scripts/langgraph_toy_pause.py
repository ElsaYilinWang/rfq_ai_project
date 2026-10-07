# scripts/langgraph_toy_pause.py

"""
Toy graph #3: pause for a human, then resume. No API key, no cost.

Four things to see:

  1. interrupt() pauses the run. The paused run is a CHECKPOINT, saved
     under a thread_id; nothing is running and nothing is being paid for.
  2. Command(resume=...) continues it. The human's answer becomes the
     return value of interrupt(). Nodes that already finished do NOT
     run again.
  3. The catch: the node that CONTAINS the interrupt re-runs from its
     first line on resume. Anything expensive placed before interrupt()
     in that node happens twice.
  4. Where should a per-run id such as trace_id live: in the graph's
     state, or in the call config? Compare what each one looks like
     after a resume.

prepare() stands in for the agent loop (the expensive model work).
"""
import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

EXPENSIVE_CALLS = {"count": 0}   # how many times the "model work" really ran


class State(TypedDict):
    trace_id: Optional[str]                  # kept in STATE
    decision: Optional[dict]
    log: Annotated[list[str], operator.add]


def expensive_work() -> str:
    EXPENSIVE_CALLS["count"] += 1
    return f"expensive work run #{EXPENSIVE_CALLS['count']}"


# --- Design A: work and pause in SEPARATE nodes -----------------------

def prepare(state: State) -> dict:
    return {"log": [expensive_work()]}


def human_approval(state: State) -> dict:
    # Nothing before interrupt() except cheap, repeatable code.
    answer = interrupt({"question": "Approve the draft?", "trace_id": state["trace_id"]})
    return {"decision": answer, "log": [f"human answered: {answer['decision']}"]}


def record(state: State, config: RunnableConfig) -> dict:
    cfg_trace = config["configurable"].get("trace_id_in_config")   # kept in CONFIG
    return {"log": [f"recorded | trace_id from STATE={state['trace_id']!r} | from CONFIG={cfg_trace!r}"]}


builder_a = StateGraph(State)
builder_a.add_node("prepare", prepare)
builder_a.add_node("human_approval", human_approval)
builder_a.add_node("record", record)
builder_a.add_edge(START, "prepare")
builder_a.add_edge("prepare", "human_approval")
builder_a.add_edge("human_approval", "record")
builder_a.add_edge("record", END)
graph_a = builder_a.compile(checkpointer=InMemorySaver())


# --- Design B: work and pause in the SAME node (the trap) -------------

def prepare_and_approve(state: State) -> dict:
    work = expensive_work()                                   # runs BEFORE the interrupt...
    answer = interrupt({"question": "Approve the draft?"})
    return {"decision": answer, "log": [work, f"human answered: {answer['decision']}"]}


builder_b = StateGraph(State)
builder_b.add_node("prepare_and_approve", prepare_and_approve)
builder_b.add_edge(START, "prepare_and_approve")
builder_b.add_edge("prepare_and_approve", END)
graph_b = builder_b.compile(checkpointer=InMemorySaver())


def fresh_state():
    return {"trace_id": "trace-123", "decision": None, "log": []}


if __name__ == "__main__":
    print("=== Experiment 1: run until the pause (Design A) ===")
    EXPENSIVE_CALLS["count"] = 0
    config = {"configurable": {"thread_id": "run-1", "trace_id_in_config": "trace-123"}}
    out = graph_a.invoke(fresh_state(), config)
    print("   invoke returned keys:", list(out.keys()))
    print("   interrupt payload   :", out["__interrupt__"][0].value)
    print("   next node waiting   :", graph_a.get_state(config).next)
    print("   expensive work ran  :", EXPENSIVE_CALLS["count"], "time(s)")

    print("\n=== Experiment 2: resume with an approval (Design A) ===")
    # NOTE: the resume call passes a config WITHOUT trace_id_in_config.
    resume_config = {"configurable": {"thread_id": "run-1"}}
    final = graph_a.invoke(Command(resume={"decision": "approve", "note": "looks good"}), resume_config)
    for line in final["log"]:
        print("  ", line)
    print("   expensive work ran  :", EXPENSIVE_CALLS["count"], "time(s)   (prepare did NOT run again)")

    print("\n=== Experiment 3: the same pause, work INSIDE the interrupt node (Design B) ===")
    EXPENSIVE_CALLS["count"] = 0
    cfg_b = {"configurable": {"thread_id": "run-2"}}
    graph_b.invoke(fresh_state(), cfg_b)
    print("   after the pause     : expensive work ran", EXPENSIVE_CALLS["count"], "time(s)")
    graph_b.invoke(Command(resume={"decision": "approve"}), cfg_b)
    print("   after the resume    : expensive work ran", EXPENSIVE_CALLS["count"], "time(s)")

"""
LangGraph workflow for the Recruform Resume Tailoring Agent.

Graph topology:
  input_guard ──(ok)──► analyze_jd ──(ok)──► tailor_resume
                │                    │               │
              (err)                (err)           (ok)
                │                    │               ▼
                └────────────────────┴──► output_guard ──(ok)──► cost_guard ──► END
                                                    │
                                                  (err)
                                                    ▼
                                                   END
"""
from langgraph.graph import END, StateGraph

from agent.nodes import (
    analyze_jd_node,
    cost_guard_node,
    input_guard_node,
    output_guard_node,
    tailor_resume_node,
)
from agent.state import AgentState


def _has_error(state: AgentState) -> str:
    """Router: 'error' → END, 'ok' → continue."""
    return "error" if state.get("error") else "ok"


def build_graph():
    """Compile and return the LangGraph resume tailoring workflow."""
    wf = StateGraph(AgentState)

    wf.add_node("input_guard",    input_guard_node)
    wf.add_node("analyze_jd",     analyze_jd_node)
    wf.add_node("tailor_resume",  tailor_resume_node)
    wf.add_node("output_guard",   output_guard_node)
    wf.add_node("cost_guard",     cost_guard_node)

    wf.set_entry_point("input_guard")

    wf.add_conditional_edges("input_guard",   _has_error, {"error": END, "ok": "analyze_jd"})
    wf.add_conditional_edges("analyze_jd",    _has_error, {"error": END, "ok": "tailor_resume"})
    wf.add_conditional_edges("tailor_resume", _has_error, {"error": END, "ok": "output_guard"})
    wf.add_conditional_edges("output_guard",  _has_error, {"error": END, "ok": "cost_guard"})
    wf.add_edge("cost_guard", END)

    return wf.compile()

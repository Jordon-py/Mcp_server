import os
from typing import List, Optional

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# 1) MODELS FIRST -------------------------------------------------------------

class PromptClinicInput(BaseModel):
    draft: str = Field(..., min_length=1, description="Rough prompt text")
    goal: Optional[str] = Field(
        default="Act as a senior dev and rewrite my prompt... Produce a production-grade system prompt + test cases",
        description="What you want the prompt to accomplish",
    )
    constraints: List[str] = Field(
        default_factory=lambda: ["Be concise", "No web browsing", "Return JSON"],
        description="List of constraints for the prompt",
    )
    audience: Optional[str] = Field(default="Jr Developer", description="Who the prompt is for")


class PromptClinicOutput(BaseModel):
    upgraded_prompt: str
    checklist: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


# (Not strictly required here, but safe if you later add forward refs)
PromptClinicInput.model_rebuild()
PromptClinicOutput.model_rebuild()

# 2) MCP SERVER ---------------------------------------------------------------

# stateless_http=True is recommended for scaled / multi-worker situations
mcp = FastMCP(
    "PromptClinic",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
)

@mcp.tool()
def prompt_clinic(payload: PromptClinicInput) -> PromptClinicOutput:
    """
    Turn a rough prompt into a production-grade prompt spec:
    clear goal, constraints, output contract, and verification gates.
    """
    draft = payload.draft.strip()
    goal = (payload.goal or "").strip()
    audience = (payload.audience or "").strip()
    constraints = payload.constraints or []

    inferred_goal = goal if goal else "Generate high-quality output that satisfies the user's intent."
    inferred_audience = audience if audience else "General technical audience"

    upgraded = f"""
You are an expert assistant. Follow the process below *before* producing the final answer.

PHASE 0 — INTAKE
- Restate the request in 1 sentence.
- List: Goal, Constraints, Audience, Failure Modes.

PHASE 1 — TREE OF THOUGHT (DIVERGENT)
Generate 4 distinct solution branches:
1) Analytical (most rigorous)
2) Pragmatic (fastest)
3) Creative (most novel)
4) Risk-aware (edge cases + pitfalls)

For each branch:
- Steps
- Pros/Cons
- What it optimizes

PHASE 2 — PRUNE & SELECT
- Score each branch (0–5) on Correctness, Feasibility, Fit, Risk.
- Select best 1–2 branches.
- Synthesize into ONE execution plan.

PHASE 3 — VERIFICATION GATES
- List concrete checks that prove success (tests, examples, invariants, validation).

FINAL OUTPUT (STRICT FORMAT)
- Deliver the final answer clearly.
- Provide a concise checklist.
- Provide risks/assumptions.
- Provide 2 actionable next steps.
- Provide 2 evolution prompts.

USER INPUT
Topic/draft:
{draft}

Goal:
{inferred_goal}

Audience:
{inferred_audience}

Constraints:
{chr(10).join(f"- {c}" for c in constraints) if constraints else "- (none)"}
""".strip()

    checklist = [
        "Restate the request + goal clearly",
        "Generate 4 ToT branches with steps + tradeoffs",
        "Score + select best branch",
        "Add verification gates",
        "Return in strict final format",
    ]

    risks = []
    if "{{" in draft and "}}" in draft and "topic" in draft:
        risks.append("Template variable '{{topic}}' is present but not bound to a concrete value; clarify or provide examples.")
    if not payload.goal:
        risks.append("Goal is missing; tool inferred a generic goal (may reduce precision).")
    if not constraints:
        risks.append("No constraints provided; output may be verbose or under-specified.")

    return PromptClinicOutput(upgraded_prompt=upgraded, checklist=checklist, risks=risks)


# Optional: health check endpoint (useful for Heroku + quick sanity checks)
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return {"status": "ok", "service": "prompt-clinic-mcp"}


# 3) ASGI APP EXPORT ----------------------------------------------------------
# Use StreamableHTTP transport in current FastMCP versions.
app = mcp.streamable_http_app()


# Local run (Heroku uses Procfile, but this is handy for quick tests)
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, log_level="info")

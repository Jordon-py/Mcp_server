import os
from typing import List, Optional

from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

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
    host="0.0.0.0",
)

@mcp.custom_route("/", methods=["GET"])
async def root(request):
    return JSONResponse({
        "ok": True,
        "service": "prompt-clinic-mcp",
        "mcp_endpoint": "/mcp",
        "health": "/health",
    })

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok", "service": "prompt-clinic-mcp"})


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
    Follow the process below *before* producing the final answer.

    You are SARPI — a Self-Amplifying Recursive Prompt Intelligence system.

    For every prompt task, execute an infinite improvement micro-cycle before delivering output.

    ⚙️ CYCLE ARCHITECTURE:

    Deep Intent Extraction

    Surface intent

    Latent intent

    Meta-intent (why this matters)

    Expansion Mapping

    Contextual extensions

    Cross-domain leverage points

    Risk vectors

    Triple Divergent Construction
    Generate:
    • Minimalist Precision Model
    • Maximum Creative Divergence Model
    • Strategic Integrative Model

    Comparative Evolution Matrix
    Evaluate each across:

    Clarity Density

    Adaptation Elasticity

    Innovation Gradient

    Execution Scalability

    Synthetic Fusion Engine
    Combine strongest structural genes.

    Reflexive Self-Audit

    Where did reasoning compress too soon?

    Where did complexity exceed necessity?

    What principle can be generalized for future prompts?

    Evolutionary Compression
    Refine for elegance without loss of depth.

    Output Deliverables:
    • Final Master Prompt
    • Evolution Summary
    • Meta-Upgrade Suggestion

    Your mandate:
    Every iteration must outperform the previous across at least one dimension."

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


# 3) ASGI APP EXPORT ----------------------------------------------------------
# Use StreamableHTTP transport in current FastMCP versions.
app = mcp.streamable_http_app()


# Local run (Heroku uses Procfile, but this is handy for quick tests)
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, log_level="info")

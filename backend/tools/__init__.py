"""Tool layer public exports.

Reasoning and execution nodes (nodes/) import tools from here rather
than reaching into individual tool modules — one import surface for
the whole tool layer, matching the "separate reasoning agents from
execution/tool agents" requirement.

CALLING CONVENTION — READ BEFORE ADDING A NEW NODE THAT CALLS A TOOL:

Every tool below takes a `db: Annotated[Session, InjectedToolArg]`
parameter that is deliberately excluded from the tool's args_schema
(so an LLM agent would never see or try to fill it itself).

Because of that, call tools with `.coroutine(**kwargs)`, passing ALL
parameters including `db` as normal keyword arguments:

    result = await get_behavioral_twin.coroutine(
        approver_id=approval.approver_id,
        department=approval.department,
        db=db,
    )

Do NOT call `.ainvoke({...})` / `.invoke({...})` from node code. Those
methods build their call strictly from args_schema, which excludes
`db` — verified with a standalone repro: `.ainvoke()` raises
`TypeError: missing 1 required positional argument: 'db'` every time,
silently, because the schema-based path never passes injected args
through. `.ainvoke()`/`.invoke()` remain valid ONLY if a tool is later
bound to an LLM agent/ToolNode, where the agent framework supplies
InjectedToolArg values through its own separate injection mechanism —
not for our deterministic node-to-tool calls, where the node itself
(not an LLM) decides which tool to call.
"""

from tools.crm_tool import crm_fetch_deal, crm_update_deal_stage
from tools.database_tool import persist_approvals, update_approval_status
from tools.behavioral_twin_tool import get_behavioral_twin, update_behavioral_twin
from tools.slack_tool import send_slack_nudge
from tools.email_tool import send_email_nudge
from tools.momentum_tool import compute_momentum
from tools.learning_tool import record_approval_outcome

__all__ = [
    "crm_fetch_deal",
    "crm_update_deal_stage",
    "persist_approvals",
    "update_approval_status",
    "get_behavioral_twin",
    "update_behavioral_twin",
    "send_slack_nudge",
    "send_email_nudge",
    "compute_momentum",
    "record_approval_outcome",
]

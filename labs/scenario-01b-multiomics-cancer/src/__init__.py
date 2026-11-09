"""Agentic Multi-Omics Tumor Board -- shared package.

Modules:
  * omics   -- the 12 deterministic analysis "skills" (tools).
  * router  -- a non-LLM, deterministic if/else twin of the agent's routing.
  * agent   -- the Azure OpenAI tool-calling loop (keyless or API-key auth).

RESEARCH / EDUCATION ONLY -- not for clinical use.
"""

__all__ = ["omics", "router", "agent"]

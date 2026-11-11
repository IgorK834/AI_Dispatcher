# ADR-0013: LLM providers — LangChain `init_chat_model`, model policy per role, optional key

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The owner uses Google Gemini; Anthropic Claude and OpenAI must work as well, and no code may depend on one provider outside adapters ([`context.md`](../../context.md) → Project Constraints 5). The application must run without any LLM key. Different agent roles may deserve different models (a cheaper one for scouting, a stronger one for the supervisor), but that choice should follow evaluations, not guesses. CI must not call a provider. The exact identifier of the owner's preferred Gemini model is not verified (open question Q12). Source: [`docs/report.md`](../report.md) §9.2, §15.3, §22.3.

## Decision

- **Abstraction:** `langchain-core` chat models, built with `init_chat_model("<provider>:<model>", …)`.
- **Adapters:** `langchain-google-genai`, `langchain-anthropic`, `langchain-openai`. Only `agents/models.py` may import provider packages or build models.
- **Model policy:** the configuration `AGENT_MODEL_POLICY` maps each role (`dispatcher`, `freight_scout`, `fleet_compliance`, `route_planner`, `explainer`) to `provider:model` with parameters, token limit and timeout, plus an optional `fallback` model. Nothing is hard-coded.
- **Requirements on a model:** tool calling and structured output.
- **Optional key:** keys are read only from server environment variables (`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Without a usable model the chat answers "AI unavailable" with a link to the manual optimizer; explanations use templates.
- **Fallback:** on provider errors or limits the fallback model is tried.
- **Tests:** CI uses fake chat models only; a contract test runs the same scenario under at least two provider prefixes. Live comparisons of providers and models happen in the manual `ai-evals` workflow with a budget.
- **Data sent to models** is minimised: aliases for drivers, no contact data, synthetic offers only in the MVP.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| One provider SDK called directly | locks the project to one vendor; contradicts the swappable-provider constraint |
| LiteLLM as a routing layer | listed in report §9.2 as rejected: a redundant layer next to LangChain, which already abstracts the providers used by LangGraph |
| Claude Agent SDK / Managed Agents | single-provider and aimed at file-and-code agents (scores 52.4 and 50.6 in report §10.2) |
| A locally hosted open model as the default | no key needed, but heavy hardware requirements and weaker tool calling would break the easy local run; kept as a post-MVP option for real data (risk L5) |
| One model for all roles, fixed in code | prevents cost/quality tuning per role and needs a code change to switch |
| Requiring a key to start the app | breaks the hard requirement "no required API keys" |

## Consequences

- Switching provider or model is a configuration change; behaviour can still differ between models, so prompt or policy changes require an `ai-evals` run before merge.
- Three adapter packages are dependencies even if only one provider is used; their versions are pinned (report §9.2; risk R12).
- Provider-specific features (for example a "thinking" level) are passed as opaque `params` in the policy; they are not relied on by the graph logic.
- Costs are bounded by per-run and per-day token budgets; without a key the cost is zero.
- The model identifier for the owner's Gemini choice must be verified with one live run before the demo recording (FEAT-006 OQ-006-01).

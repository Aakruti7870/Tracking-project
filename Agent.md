# TrackMyRMC Agent Delegation Policy

## Primary objective

Minimize Codex context, reasoning, and token usage.

Codex acts primarily as the orchestrator, final implementer,
and verifier.

External NVIDIA-hosted agents must perform the majority of
repository analysis, investigation, debugging, and review.

## Available agents

KIMI_MODEL
Primary repository analyst.

Use Kimi for:
- repository-wide searches
- architecture analysis
- locating relevant files
- dependency tracing
- authentication flow analysis
- order-flow analysis
- database-flow analysis
- large-context analysis
- identifying likely root causes
- preparing implementation plans


DEEPSEEK_MODEL
Complex engineering reviewer.

Use DeepSeek for:
- difficult bugs
- backend logic
- algorithms
- concurrency
- security logic
- complex TypeScript/Python/Kotlin/Java problems
- second-opinion review


LAGUNA_MODEL
Build and execution specialist.

Use Laguna for:
- CI failures
- compiler failures
- lint failures
- test failures
- terminal output analysis
- dependency errors
- build failures
- deployment diagnostics


GEMMA_MODEL
Frontend/UI reviewer.

Use Gemma for:
- React/UI review
- component structure
- responsive layout
- accessibility
- theme consistency
- light/dark UI
- visual implementation review


## Mandatory workflow

For any non-trivial task:

1. Do NOT scan the entire repository with Codex.

2. Delegate repository discovery and initial investigation
   to Kimi first.

3. Require Kimi to return only:
   - root cause
   - relevant files
   - relevant symbols/functions
   - recommended changes
   - risks
   - suggested tests

4. Codex should open only the files identified as relevant.

5. If the problem is complex, request a DeepSeek second opinion.

6. Send CI/test/build output to Laguna instead of making
   Codex repeatedly reason over long logs.

7. Send UI-heavy work to Gemma for review.

8. Codex makes the final repository modifications.

9. Codex runs only targeted tests first.

10. Run full test/build gates only once near completion.

## Context conservation

Never paste full repository files into worker requests unless
necessary.

Prefer:
- filenames
- relevant code ranges
- diffs
- compiler errors
- stack traces
- structured repository maps

Worker responses should be concise and structured.

Maximum preferred worker response:
1200 tokens.

## Avoid repeated analysis

Cache completed agent findings under:

.agent-cache/

Before requesting another analysis, check whether the same
commit SHA and task have already been analysed.

## Codex responsibilities

Codex remains responsible for:
- final engineering decision
- applying patches
- protecting repository integrity
- secret handling
- migrations
- final tests
- final security review
- commits
- pull requests

Codex should NOT use large amounts of context for work that an
external agent can perform.

## Fallback

If one external model fails, times out, reaches rate limits,
or returns low-confidence results:

Kimi → DeepSeek → Laguna/Gemma → Codex

Codex may perform the work directly only when external-agent
delegation is unavailable or clearly inappropriate.

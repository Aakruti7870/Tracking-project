# Architecture Refactor Plan

## Goal

Make the existing production app smaller, easier to reason about, and safer to extend without replacing the proven stack.

Keep:
- Expo + React Native + Expo Router
- TypeScript, but with less local type ceremony
- Python backend + PostgreSQL
- Existing auth, KYC, payment, order, tracking, signing and CI contracts

The target is **less TypeScript volume with stronger TypeScript boundaries**, not a JavaScript rewrite.

## Core rules

1. Read the real call path before changing code.
2. Reuse existing helpers and UI primitives before creating new ones.
3. One domain concept should have one canonical contract.
4. Route files should compose features; business rules should not live in JSX.
5. Keep validation, security, accessibility and error handling even when code is shortened.
6. Prefer deletion and consolidation over new dependencies or abstraction layers.
7. Do not change Android package identity, signing, SHA/App Links, auth, KYC or payments in structural-only PRs.
8. Every non-trivial refactor must preserve behavior and pass the full CI matrix.

## Target frontend shape

```text
frontend/
  app/                  # Expo Router entry points only
  src/
    api/                # transport and endpoint clients
    domain/             # canonical Order, Plant, User, Trip, KYC, Payment contracts
    features/           # workflow logic grouped by product capability
    components/ui/      # reusable interaction primitives
    hooks/
    theme/
    utils/
```

Preferred flow:

```text
route -> feature hook/service -> api client -> backend
```

## Phase 1 — Domain contract foundation

- Move durable entity types out of rendering components.
- Keep compatibility re-exports temporarily so existing imports do not break in a big-bang migration.
- Remove `any` from shared reusable components where the correct type is already known.
- Do not change runtime behavior.

Initial contracts:
- Plant
- Order

Next contracts after this PR:
- User/Auth session
- KYC
- Trip/Tracking
- Payment
- Role/capability identifiers

## Phase 2 — API boundary cleanup

- Give each domain a small endpoint client.
- Reuse the existing transport client.
- Remove duplicate request/response declarations from screens.
- Keep runtime validation at backend trust boundaries.

## Phase 3 — Feature extraction

Start with Customer Order because it currently combines form state, maps autocomplete, KYC rules, quotation locks, API orchestration and rendering.

Split behavior, not UI for its own sake:

```text
features/orders/
  useNewOrder.ts
  orderRules.ts
```

Keep the route thin and keep the current visual behavior unless a separate UX PR requests changes.

## Phase 4 — Permission/capability consolidation

Replace scattered role comparisons with a single capability rule layer where duplication is proven.

Example intent:

```ts
can(user, "dispatch_order")
can(user, "approve_kyc")
can(user, "view_finance")
```

Do not introduce this abstraction until duplicated permission checks have been inventoried.

## Phase 5 — Runtime performance cleanup

Prioritize measurable runtime waste rather than line count:
- duplicate API calls
- unnecessary rerenders
- repeated sort/filter work during render
- leaked location/listener subscriptions
- oversized image assets
- redundant dependencies
- oversized backend responses

## Phase 6 — Dead code and dependency cleanup

Remove only after proving there are no callers:
- stale routes
- compatibility aliases
- abandoned feature flags
- unused assets
- duplicate utilities
- overlapping dependencies

Potential dependency audit item: both `date-fns` and `dayjs` are currently installed; choose one only after all callers and behavior are verified.

## Protected production boundaries

Structural refactors must not casually modify:
- Android package ID
- Play signing / keystore workflows
- `PLAY_SIGNING_SHA256`
- Digital Asset Links/App Links
- authentication and review access
- KYC eligibility
- payment/webhook semantics
- order/trip state machines

Changes to these areas require focused tests beyond ordinary structural CI.

## Success criteria

The refactor is successful when:
- TypeScript remains strict at domain/API boundaries.
- Duplicate interfaces and local wrapper types fall substantially.
- Shared components contain no avoidable `any` props.
- Route files become smaller and easier to scan.
- Runtime behavior remains unchanged unless a PR explicitly changes it.
- Full CI stays green at every migration step.
- The project becomes easier to extend without increasing architectural layers.

## Expected reduction

Do not optimize for a fixed line-count target. A realistic long-term goal is roughly 25–40% less handwritten frontend TS/TSX, with the largest reductions in oversized route files and repeated type/form/API boilerplate. The remaining TypeScript should be stronger and more reusable than the code it replaces.

# Frontend TypeScript simplification audit

This inventory was produced before refactoring. It covers every TypeScript/TSX
module under `frontend/app` and `frontend/src` (18,112 lines at the time of the
scan), with manual review concentrated on the largest modules and repeated
patterns reported by the inventory.

## Ranked candidates

| Priority | Location | Current problem and approximate size | Proposed form | Risk | Expected reduction |
| --- | --- | --- | --- | --- | --- |
| P0 | `src/hooks/useApi.ts`, `useGet` (34 lines) | An older request can overwrite the result of a newer `path`/token request, and a request can update state after unmount. | Add effect cleanup/request invalidation while keeping the public hook contract. | Medium: shared data-fetching behavior. | Neutral; correctness fix rather than line reduction. |
| P0 | customer/owner order lists and driver trip list, filtered collections (three sites) | Memoized filters omitted the selected matcher from their dependency lists, allowing stale results after a tab change. | Derive these small filtered arrays during render; remove unnecessary memoization and dependency hazards. | Low: bounded display collections. | Nine lines and three memoization imports. |
| P1 | `src/screens/BusinessModule.tsx`, component and `unpackRows` (659 lines) | One component combines seven business modules, response normalization, mutations, forms, and rendering; it has broad `any` response/state types. | Introduce small discriminated resource/row contracts, then extract only the stable form and row-normalization responsibilities. | High: broad plant operations behavior. | 80–140 lines in the screen after extraction; little repository-wide reduction initially. |
| P1 | `src/screens/LoginScreen.tsx`, `LoginScreen` (795 lines) | Authentication orchestration and several large UI states live in one component, with repeated API-error rendering and route casts. | Retain the auth boundary and extract presentation-only login stages; centralize safe error-detail extraction. | Very high: protected auth/OTP/MFA routing. | 100–180 lines in the screen, mainly moved; 20–40 genuinely duplicated lines removed. |
| P1 | `app/workforce.tsx`, `WorkforceScreen` (616 lines) | Attendance, leave, visits, expense claims, API orchestration, and form state share a route; mutation error/loading code repeats. | Keep contracts local/canonical and extract stable feature sections plus one typed mutation runner. | High: staff workflows. | 60–100 lines of repeated render/mutation code. |
| P1 | `src/components/OwnerProductionBilling.tsx` and `src/components/LoadPlanner.tsx` (395 lines combined) | Mutation runners, error handling, busy state, and untyped leaf props repeat; production normalization starts from `any`. | Use explicit wire/command/leaf-prop types and shared safe API-error reading, without changing endpoints or status gates. | Medium-high: ordering and dispatch boundaries. | 15–30 lines and nine `any` occurrences. |
| P1 | `app/authority/plants.tsx`, route (481 lines) | Large plant administration form and list orchestration are coupled, with repeated field rendering and mutation handling. | Extract a typed plant editor only after verifying its API payload against the canonical plant contract. | High: plant administration boundary. | 50–90 route lines; modest net reduction. |
| P2 | `src/components/WeeklyInsights.tsx`, `Total`/`Dot` (109 lines) | Two tiny leaf components discard type safety with `any`; `Dot` receives the entire theme only to read one color. | Give leaf props small explicit types and pass the required foreground color. | Low: presentation-only. | Two `any` values and a narrower prop surface; roughly 2–4 lines. |
| P2 | `src/screens/StaffCollection.tsx`, action/card helpers (320 lines) | Action bodies, dynamic container selection, and several navigation values use `any`; filtering is memoized despite cheap bounded arrays. | Type JSON bodies and card variants, then remove memoization only after render profiling shows no need. | Medium: shared staff collections. | 10–25 lines and four to six `any` values. |
| P2 | `src/api/client.ts`, HTTP helpers (288 lines) | Five request functions repeat fetch/JSON-body mechanics, while request bodies and WebAuthn records use `any`. | Use a JSON-compatible request type and one internal request function, preserving exported endpoints and response contracts. | High: system-wide API/security boundary. | 25–40 lines and six `any` values. |
| P2 | `src/components/GlassTabBar.tsx` (200 lines) | Navigation state, routes, and renderer are entirely `any`; route lookup is repeated for each tab. | Use React Navigation tab-bar state/navigation types and a precomputed tab map. | Medium: Expo Router integration can be platform-sensitive. | Four `any` values; 5–10 lines. |
| P2 | repeated `catch (e: any)` across app/screens/components (more than 50 occurrences) | Error values bypass strict typing and repeat `e.detail || fallback`. | Add one `unknown`-accepting error-detail guard at the API boundary and migrate incrementally. | Low per call; medium if bulk changed. | One `any` per migrated catch and about one line per multi-line handler. |
| P2 | large route components between 305 and 448 lines (`new-order`, reports, POD, trip detail) | Forms and orchestration dominate file size; some local leaf components use `any`. | First type leaf props and response payloads; split only stable presentation sections with clear responsibility. | Medium-high because these are protected lifecycle flows. | 5–15% per file without redesign. |
| P3 | route calls using `as any` throughout `app` and screens | Expo Router's generated route union does not include several valid dynamic/runtime routes, so callers silence it repeatedly. | Regenerate/fix typed-route configuration, or provide one narrowly typed navigation helper after platform validation. | Medium: convention-driven routing may look unused to static analysis. | Dozens of casts, little line reduction. |
| P3 | repeated inline layout objects and locally typed icon/color props | Common flex/gap shapes and icon names are verbose, but abstraction would often obscure simple JSX. | Leave most inline styles alone; type only reusable leaf components. | Low. | Small; avoid architecture for architecture's sake. |

## Large-file inventory

- Over 700 lines: `src/screens/LoginScreen.tsx` (795).
- 500–699 lines: `src/screens/BusinessModule.tsx` (659), `app/workforce.tsx` (616).
- 300–499 lines: `app/authority/plants.tsx` (481),
  `app/workforce-reports.tsx` (448), `app/new-order.tsx` (431),
  `app/plant-onboarding.tsx` (429),
  `src/components/auth/OtpOrbitVerification.tsx` (405), `app/trip/[id].tsx`
  (367), `app/plans-promotions.tsx` (350), `app/customer/plants.tsx`
  (347), `src/screens/StaffCollection.tsx` (320), and `app/pod/[id].tsx`
  (305).

Most size comes from genuine forms and role-specific UI mixed with orchestration,
not dead comments or obviously removable compatibility code. These files should
not be split solely to satisfy a line threshold.

## Protected decisions

- Authentication, OTP/MFA, KYC, payment, order, plant, trip, tracking, challan,
  invoice, native, signing, app-link, and API contracts remain TypeScript.
- No module qualifies for JavaScript conversion: the small presentation modules
  gain useful prop checking, while utility modules participate in typed callers.
- Expo Router routes, `.web` modules, service workers, plugins, Firebase files,
  and native configuration are convention-loaded and are not dead-code
  candidates based on import scans alone.
- The first implementation batch is intentionally limited to the proven request
  race in `useGet` and low-risk `any` removal in presentation/production-load
  components. The larger candidates require isolated follow-up batches.

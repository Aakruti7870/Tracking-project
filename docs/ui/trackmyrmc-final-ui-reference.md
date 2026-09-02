# TrackMyRMC Final UI Implementation Contract

This document is the authoritative implementation contract derived from the approved TrackMyRMC visual direction. Existing visual styling may be replaced to conform to this contract, but business logic, API contracts, auth/session behavior, KYC/DigiLocker behavior, payment flows, GPS/tracking, production order lifecycle, MongoDB behavior, Play-policy requirements, Android identity/signing/App Links, and privileged-role boundaries must remain intact.

## Core visual language
- Premium industrial mobility aesthetic comparable in finish and interaction quality to mature logistics/ride apps.
- Dark theme: near-black/navy base, elevated charcoal cards, white text, restrained borders, vivid orange actions and route/progress accents.
- Light theme: warm white/light gray base, clean white cards, deep navy/charcoal text, soft shadows, same vivid orange action color.
- Verification green is reserved for identity/KYC VERIFIED semantics.
- Avoid random gradients, inconsistent shadows, generic blue accents, decorative clutter, or one-off component styling.

## Visual parity rules
- The approved reference board is the final visual acceptance target for layout hierarchy, density, visual rhythm, status treatment, card structure, action hierarchy and dark/light theme behavior.
- Implement the reference as real React Native UI, not as static screenshots. Buttons, fields, cards, lists, maps, status labels, filters, tabs and navigation must remain interactive and data-driven.
- Raster artwork is allowed only for hero/brand/illustrative assets. Product controls, operational data, maps, order details, KYC states and navigation must remain code-rendered.
- If a reference element contains data not available from the repository/API, preserve the visual slot but render only real available data or a legitimate empty/loading state. Never invent production values.
- Do not add decorative UI that creates a false operational state, false verification, false ETA, false payment status or false delivery progress.
- The visual reference controls appearance only; existing repository behavior controls actual workflow and data semantics.

## Global component rules
- 44dp minimum touch targets.
- Consistent control heights, radii, spacing, typography and status colors.
- Primary action = solid orange with clear pressed/loading/disabled states.
- Secondary action = neutral elevated surface; outline action = transparent with clear border.
- Cards use consistent corner radius, padding and elevation.
- Inputs use explicit focus, error, disabled and filled states.
- Status chips use semantic color and short labels; never rely on color alone.
- Icons must be from the existing icon system unless a repository-grounded asset exists.
- Haptics only for meaningful successful/primary interactions already supported by the app.
- Loading states must preserve layout and prevent duplicate submission.
- Shared primitives are preferred over screen-specific duplicate styles. A visual rule repeated on two or more screens should normally become a token or reusable component.
- One screen must not introduce a new radius, button height, shadow family, typography scale or status color without a documented design-system reason.

## Screen composition rules
- Every applicable screen must have a clear hierarchy: top context/title, primary content, one dominant action when needed, then secondary/supporting actions.
- Avoid excessive nested cards. Cards must represent meaningful operational grouping, not decoration.
- Maintain consistent horizontal gutters and vertical rhythm across Login, Home, Orders, Tracking, Plants, KYC, Payments, Notifications, Settings and More.
- Empty, loading, error and success states must preserve the same component geometry so the interface does not jump or feel unfinished.
- Dense operational screens must remain scan-friendly: reference/status first, then grade/quantity/location/time, then secondary metadata.
- On small devices, reflow or wrap content rather than clipping, shrinking text below readability, or forcing horizontal page scrolling.

## Dark/light theme parity
- Every major user-facing screen must be intentionally designed for both dark and light themes; neither theme may be an automatic color inversion of the other.
- Dedicated light and dark hero/illustrative assets must be used where the visual treatment materially depends on background tone.
- Never display the dark Login hero unchanged in light mode.
- Preserve identical information hierarchy and interaction placement between themes.
- Ensure contrast remains accessible for labels, disabled controls, status chips, borders and placeholders in both themes.

## Navigation
- Preserve route behavior and mobile-vs-web role boundary.
- Bottom navigation remains consistent across applicable mobile areas: Home, Orders, centered New action, Plants, More.
- Selected destination uses orange accent and stronger label/icon weight.
- Top bars, back actions and screen titles must follow the same spacing/typography on all screens.
- Do not add, remove, hide or reorder privileged-role destinations purely to match the reference image.

## Login
Target: `frontend/src/screens/LoginScreen.tsx` plus its existing route wrapper only where required.
- Preserve every OTP/MFA/passkey/recovery/onboarding code path exactly.
- Dedicated dark and light hero assets. Never show dark artwork unchanged in light mode.
- Hero composition: TrackMyRMC industrial/RMC identity, concrete mixer/RMC plant context, orange live-route motif.
- User Login / Plant Staff Login selector is visually unified with the rest of the design.
- Form surface: premium card, strong title/subtitle hierarchy, clean field spacing, orange primary CTA.
- OTP flow remains six-digit and existing orbit/verification logic remains intact; only presentation may be modernized.
- Privacy Policy, Account Deletion and support links remain accessible and unchanged in destination.
- Do not replace working auth actions with mock buttons just to achieve visual parity.

## Post-login home
- Premium operational dashboard rather than generic cards.
- Greeting/identity area, verification state, active delivery/order emphasis, concise operational metrics, nearby plants or role-relevant next actions.
- Active delivery card should communicate status, ETA/distance where actual data exists, and one obvious continuation action.
- Do not invent live data.
- Home must visually align with the reference board but adapt content to the authenticated role and actual repository data.

## Orders and deliveries
- Consistent segmented filters and status chips.
- Compact, scan-friendly cards: order/challan reference, grade, quantity, plant/site, status, ETA/timestamp when repository data actually provides it.
- Delivered/paid operational statuses remain orange unless identity verification semantics require green.
- Do not change order state machines, transitions or server-recognized status strings to match mockup wording.

## Live tracking
- Route/map area is visually dominant.
- Orange route/progress treatment, dark map-compatible presentation, concise bottom delivery card with distance/ETA/status where actual data exists.
- Preserve existing GPS/tracking and external-map logic.
- Never fabricate a route line, vehicle location, ETA or distance if the tracking source is unavailable.

## Plants
- Search/filter row, map/list hierarchy, plant cards with verified badge only where verification is real.
- Keep existing nearby/search APIs and location behavior.
- Visual ranking/promoted treatment must reflect real backend state; do not visually promote an unqualified plant.

## KYC / DigiLocker / Profile
- KYC success must display the authoritative verified identity returned by the existing KYC/DigiLocker-backed profile contract.
- If the backend currently exposes the verified DigiLocker name, surface that value in the KYC success/profile UI rather than retaining an earlier user-entered display name.
- Do not invent or persist a name from frontend-only state.
- KYC VERIFIED/VERIFIED are the only green identity badges.
- Preserve KYC start/return/review and one-pending-profile protections.
- Aadhaar/PAN/mobile verification rows shown in the reference must only be rendered as verified when the repository has corresponding verified state.

## Payments
- Preserve gateway and webhook/API behavior.
- Only presentation changes: amount hierarchy, payment method cards, loading/failure/success states.
- Never expose a payment method, amount, paid state or success state that is not supported by current backend/payment-provider logic.

## Notifications / More / Settings
- One shared list-row pattern with consistent icons, separators, chevrons, pressed states and section grouping.
- Destructive actions remain visually distinct and require the existing safeguards.
- Legal/privacy/account-deletion routes must remain discoverable wherever currently required by Play policy.

## Motion and feedback
- Fast pressed feedback, short screen/card transitions, restrained success animation, no decorative long-running motion.
- Respect reduced-motion platform behavior where existing libraries allow it.
- Motion must never delay OTP, payment, KYC, tracking or order actions.

## Implementation strategy
1. Normalize design tokens and shared UI primitives first.
2. Apply the system to small/medium screens in parallel where code paths do not overlap.
3. Handle Login, KYC identity presentation, payments, tracking and large modules sequentially.
4. Run Mobile UI Quality Gate after every wave.
5. Run Laguna on critical TypeScript/security-sensitive changes.
6. Use Kimi for repository-grounded cross-module consistency/architecture review.
7. Run Gemma final UI audit after the implementation wave.

## Per-wave visual checklist
Before a visual wave is considered complete, verify all of the following:
- Dark and light rendering both reviewed.
- No protected logic or API contract changed for visual reasons.
- No static screenshot substituted for an interactive application surface.
- All existing primary actions still work and remain reachable.
- Loading, disabled, pressed, error, empty and success states remain implemented.
- Navigation/back behavior remains unchanged unless separately approved.
- No fake data or fake verification/progress/payment state added.
- Shared tokens/components used where appropriate instead of one-off styles.
- Typecheck/lint/Mobile UI Quality Gate green.
- Android/Play/auth/readiness gates green when the changed surface can affect them.

## Merge rule
A UI wave may merge only when required CI is green and the diff is demonstrably presentation-only or a separately approved sequential behavior change. A screenshot that looks closer to the reference is not sufficient evidence if interaction, accessibility, theme parity or protected logic regresses.

## Acceptance bar
No screen should look like a different product. All visible states — idle, pressed, disabled, loading, success, error, empty, verified, in-progress, delivered/cancelled — must use the same design language and preserve existing behavior. The implementation should visually converge toward the approved reference board while remaining a real, functional TrackMyRMC application.
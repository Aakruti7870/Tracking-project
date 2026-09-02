# TrackMyRMC Final UI Implementation Contract

This document is the authoritative implementation contract derived from the approved TrackMyRMC visual direction. Existing visual styling may be replaced to conform to this contract, but business logic, API contracts, auth/session behavior, KYC/DigiLocker behavior, payment flows, GPS/tracking, production order lifecycle, MongoDB behavior, Play-policy requirements, Android identity/signing/App Links, and privileged-role boundaries must remain intact.

## Core visual language
- Premium industrial mobility aesthetic comparable in finish and interaction quality to mature logistics/ride apps.
- Dark theme: near-black/navy base, elevated charcoal cards, white text, restrained borders, vivid orange actions and route/progress accents.
- Light theme: warm white/light gray base, clean white cards, deep navy/charcoal text, soft shadows, same vivid orange action color.
- Verification green is reserved for identity/KYC VERIFIED semantics.
- Avoid random gradients, inconsistent shadows, generic blue accents, decorative clutter, or one-off component styling.

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

## Navigation
- Preserve route behavior and mobile-vs-web role boundary.
- Bottom navigation remains consistent across applicable mobile areas: Home, Orders, centered New action, Plants, More.
- Selected destination uses orange accent and stronger label/icon weight.
- Top bars, back actions and screen titles must follow the same spacing/typography on all screens.

## Login
Target: `frontend/src/screens/LoginScreen.tsx` plus its existing route wrapper only where required.
- Preserve every OTP/MFA/passkey/recovery/onboarding code path exactly.
- Dedicated dark and light hero assets. Never show dark artwork unchanged in light mode.
- Hero composition: TrackMyRMC industrial/RMC identity, concrete mixer/RMC plant context, orange live-route motif.
- User Login / Plant Staff Login selector is visually unified with the rest of the design.
- Form surface: premium card, strong title/subtitle hierarchy, clean field spacing, orange primary CTA.
- OTP flow remains six-digit and existing orbit/verification logic remains intact; only presentation may be modernized.
- Privacy Policy, Account Deletion and support links remain accessible and unchanged in destination.

## Post-login home
- Premium operational dashboard rather than generic cards.
- Greeting/identity area, verification state, active delivery/order emphasis, concise operational metrics, nearby plants or role-relevant next actions.
- Active delivery card should communicate status, ETA/distance where actual data exists, and one obvious continuation action.
- Do not invent live data.

## Orders and deliveries
- Consistent segmented filters and status chips.
- Compact, scan-friendly cards: order/challan reference, grade, quantity, plant/site, status, ETA/timestamp when repository data actually provides it.
- Delivered/paid operational statuses remain orange unless identity verification semantics require green.

## Live tracking
- Route/map area is visually dominant.
- Orange route/progress treatment, dark map-compatible presentation, concise bottom delivery card with distance/ETA/status where actual data exists.
- Preserve existing GPS/tracking and external-map logic.

## Plants
- Search/filter row, map/list hierarchy, plant cards with verified badge only where verification is real.
- Keep existing nearby/search APIs and location behavior.

## KYC / DigiLocker / Profile
- KYC success must display the authoritative verified identity returned by the existing KYC/DigiLocker-backed profile contract.
- If the backend currently exposes the verified DigiLocker name, surface that value in the KYC success/profile UI rather than retaining an earlier user-entered display name.
- Do not invent or persist a name from frontend-only state.
- KYC VERIFIED/VERIFIED are the only green identity badges.
- Preserve KYC start/return/review and one-pending-profile protections.

## Payments
- Preserve gateway and webhook/API behavior.
- Only presentation changes: amount hierarchy, payment method cards, loading/failure/success states.

## Notifications / More / Settings
- One shared list-row pattern with consistent icons, separators, chevrons, pressed states and section grouping.
- Destructive actions remain visually distinct and require the existing safeguards.

## Motion and feedback
- Fast pressed feedback, short screen/card transitions, restrained success animation, no decorative long-running motion.
- Respect reduced-motion platform behavior where existing libraries allow it.

## Implementation strategy
1. Normalize design tokens and shared UI primitives first.
2. Apply the system to small/medium screens in parallel where code paths do not overlap.
3. Handle Login, KYC identity presentation, payments, tracking and large modules sequentially.
4. Run Mobile UI Quality Gate after every wave.
5. Run Laguna on critical TypeScript/security-sensitive changes.
6. Use Kimi for repository-grounded cross-module consistency/architecture review.
7. Run Gemma final UI audit after the implementation wave.

## Acceptance bar
No screen should look like a different product. All visible states — idle, pressed, disabled, loading, success, error, empty, verified, in-progress, delivered/cancelled — must use the same design language and preserve existing behavior.
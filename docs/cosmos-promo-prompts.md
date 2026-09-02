# Track My RMC — Cosmos 30-second promo prompt pack

This prompt pack is designed for **six 5-second scenes** so the final edit is exactly **30 seconds**. It is written for NVIDIA Cosmos video-to-world generation using a real RMC source clip plus an edge/depth/segmentation control derived from that clip.

> Important: do **not** ask the video model to generate final logos, phone UI text, challan text, ETA numbers, or other exact typography. Generative video models can distort text. The GitHub workflow adds the exact Track My RMC titles and `Powered by Gold E Tech` after generation.

## Global visual direction

Use this direction for every scene:

- Premium photorealistic ready-mix-concrete commercial.
- Modern white concrete mixer truck, realistic industrial RMC batching plant and silos.
- Deep navy / graphite environment with controlled saffron-orange practical lighting.
- Wet or polished industrial ground with physically plausible reflections.
- Natural heavy-vehicle motion, correct wheel rotation, correct truck proportions, no warped drum or axles.
- Camera motion should remain smooth and commercial: slow dolly, tracking shot, low-angle hero shot, or restrained crane movement.
- Digital route/HUD effects must be subtle and physically integrated; never cover the truck.
- No people unless already present in the source.
- No extra trucks unless explicitly requested.
- No fantasy machinery, floating objects, warped architecture, unreadable signage, duplicate wheels, malformed cab, or impossible plant geometry.
- Do not invent third-party brands.
- Preserve the orange / white / dark Track My RMC visual language.

## Scene 01 — Secure access + brand opening (0–5s)

**Overlay title added after generation:** `SECURE ACCESS. ONE SMART PLATFORM.`

**Prompt**

A premium cinematic opening at a modern ready-mix concrete plant at blue hour. A clean white concrete mixer truck is positioned heroically in the foreground while the illuminated batching plant and tall silos rise behind it. The camera slowly pushes forward at a low three-quarter angle. Warm amber industrial lights switch on progressively across the plant and reflect naturally on the polished ground. Add only restrained abstract digital security and connection light motifs around the environment, never covering the vehicle. The scene communicates secure role-based access for customers and plant teams, professional enterprise software, reliability and trust. Photorealistic, physically believable, stable truck proportions, realistic lights and reflections, no text rendered inside the generated scene.

## Scene 02 — Nearby plants + rate discovery (5–10s)

**Overlay title:** `DISCOVER NEARBY RMC PLANTS`

**Prompt**

A realistic concrete mixer truck waits near a modern batching plant while subtle glowing map-route lines spread across the wet industrial ground toward several distant location markers. The camera makes a smooth lateral tracking move, revealing the plant, the truck and a clean city-edge industrial environment. The route markers communicate nearby verified RMC plant discovery and fast plant selection without becoming a fantasy hologram. Include a restrained phone-shaped dark interface object in the far right foreground showing a map-like composition with orange pins, but do not generate readable text. Premium navy and saffron-orange commercial lighting, realistic distance perspective, physically accurate truck and plant, no warped geometry.

## Scene 03 — Smart order booking + pour planning (10–15s)

**Overlay title:** `SMART ORDER BOOKING`

**Prompt**

At the RMC plant loading area, the mixer truck is prepared for an upcoming concrete order. The camera performs a slow controlled orbit around the front three-quarter side of the truck while the plant remains clearly visible. Add minimal interface-like visual cues that suggest concrete grade selection, quantity, schedule and pour planning, expressed as clean geometric panels without readable text. A subtle orange confirmation pulse travels from the plant toward the truck to represent the confirmed order. Keep the scene highly realistic and industrial, with accurate mixer drum, wheels, chassis, shadows and plant structures. Premium enterprise technology advertising, no generated words or logos.

## Scene 04 — Ready dispatch (15–20s)

**Overlay title:** `READY TO DISPATCH`

**Prompt**

A loaded ready-mix concrete truck begins moving out from beneath a modern batching plant in a controlled dispatch sequence. Show physically realistic suspension, wheel rotation and slow heavy-vehicle acceleration. The camera tracks beside the truck while the plant loading structure remains in the background. A subtle orange route line activates on the ground in front of the truck and a restrained status pulse connects the plant to the vehicle, communicating assigned truck and dispatch readiness. Industrial night lighting, warm silo lamps, wet-ground reflections, deep navy-black environment, realistic concrete equipment, no impossible motion, no readable text.

## Scene 05 — Live truck tracking + ETA (20–25s)

**Overlay title:** `LIVE TRACKING. ETA. ROUTE UPDATES.`

**Prompt**

A cinematic tracking shot follows the concrete mixer truck traveling through a realistic industrial road environment after leaving the RMC plant. The camera moves smoothly alongside and slightly behind the truck. A thin saffron-orange route line follows the road surface naturally and a few subtle location nodes appear along the route. Include a restrained dark phone-shaped interface element near the edge of frame with a map-like route composition and progress indicator but no readable text. Communicate real-time truck tracking, distance, route visibility and ETA while keeping the truck fully visible. Photorealistic road physics, correct wheels, stable mixer drum, realistic lighting and reflections, no futuristic fantasy city.

## Scene 06 — Delivery progress + digital challan/POD + final hero (25–30s)

**Overlay title:** `ORDER | DISPATCH | TRACK | DELIVER`

**Prompt**

The concrete mixer truck reaches the delivery destination and settles into a clean final hero composition. Start with the truck completing its journey, then transition into a confident stationary three-quarter hero view with the RMC plant and city-industrial lights in the distance. Use a subtle green completion pulse and restrained document/checkmark interface motifs to suggest delivered status, digital challan and proof of delivery, without readable text. End on a strong premium frame with the truck centered, orange route line terminating beneath it, glossy reflections and warm industrial lighting. The final feeling is secure, reliable, modern concrete delivery with complete visibility and control. Photorealistic, stable geometry, no extra vehicles, no generated logos or words.

## Exact post-production text order

The workflow should render these exact overlays after Cosmos generation:

1. `TRACK MY RMC` / `SECURE ACCESS. ONE SMART PLATFORM.`
2. `TRACK MY RMC` / `DISCOVER NEARBY RMC PLANTS`
3. `TRACK MY RMC` / `SMART ORDER BOOKING`
4. `TRACK MY RMC` / `READY TO DISPATCH`
5. `TRACK MY RMC` / `LIVE TRACKING. ETA. ROUTE UPDATES.`
6. `TRACK MY RMC` / `ORDER | DISPATCH | TRACK | DELIVER`

Common footer on every scene: `Powered by Gold E Tech`

## Negative prompt / rejection criteria

When the endpoint supports a negative prompt, use:

`blurry, low quality, unreadable text, distorted logo, duplicate wheels, extra axles, warped truck cab, deformed mixer drum, floating truck, impossible suspension, malformed plant silos, duplicate plant structures, fantasy machinery, excessive holograms, people, watermark, third-party logo, camera shake, flicker, temporal inconsistency`

Reject/regenerate a scene if any of these are visible:

- wheel count or axle geometry changes between frames;
- mixer drum changes shape or detaches;
- truck intersects the road or plant;
- plant silos visibly bend/duplicate;
- major flicker or frame-to-frame identity drift;
- generated text appears prominently and is unreadable;
- route/HUD effects obscure the vehicle;
- unsafe or unrealistic truck motion.

## Model note

`nvidia/cosmos-transfer1-7b` is suitable for video-to-world generation from a source/control video, but NVIDIA currently marks Transfer1 for deprecation. Keep the workflow endpoint configurable so it can move to `cosmos-transfer2.5-2b` without redesigning the promo. Transfer-style models work best when the control video preserves the motion and spatial structure you want in the final scene.

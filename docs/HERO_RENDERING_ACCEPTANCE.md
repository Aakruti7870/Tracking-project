# TrackMyRMC hero rendering acceptance

This change is accepted only when both Login and Customer Home satisfy all of the following in light and dark themes:

- dedicated Light and Dark hero sources are selected from the active theme;
- the complete hero image remains visible (`contain`), with no `cover` crop;
- no subject, plant, silo, mixer, lighting, or important artwork is clipped by responsive fitting;
- light mode keeps a bright neutral surround and dark mode keeps a graphite surround;
- hero gradients are UI layers, not destructive baked-in blur;
- web zoom checks at 80%, 100%, and 120% retain full-content visibility;
- narrow Android/mobile and wider web layouts retain the complete source image;
- auth, KYC, routes, backend contracts, package ID, signing, and App Links remain unchanged.

Any future change that returns either hero to `contentFit="cover"` is a regression.

# Hero asset mapping

Login and Customer Home now use independent theme-specific asset paths so the two screens can evolve without sharing one crop-sensitive bitmap.

- `frontend/assets/images/login-hero-light.jpg`
- `frontend/assets/images/login-hero-dark.jpg`
- `frontend/assets/images/home-hero-light.jpg`
- `frontend/assets/images/home-hero-dark.jpg`

The screen code selects the active source from `colors.isDark` and renders it with `contentFit="contain"` to preserve the full source at responsive sizes and browser zoom levels.

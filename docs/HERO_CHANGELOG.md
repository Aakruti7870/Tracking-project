# Hero fix changelog

- Split Login and Customer Home hero sources into separate light/dark asset paths.
- Added runtime theme selection through the existing TrackMyRMC theme state.
- Replaced crop-prone `cover` rendering with `contain` on both hero locations.
- Added light/dark background and gradient treatment appropriate to the selected theme.
- Restored theme-aware status bar rendering on Login.
- Added a regression guard that fails if the theme switch or no-crop rendering is removed.

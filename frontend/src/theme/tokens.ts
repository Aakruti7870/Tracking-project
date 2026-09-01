// TrackMyRMC Bolt Orange — premium industrial design tokens.
// Orange drives actions and operational state. Verification green is reserved for VERIFIED/KYC VERIFIED UI.

export const palette = {
  orange: "#FF5A16",
  orangeBright: "#FF6A1A",
  orangeDeep: "#C93D00",
  orangePressed: "#B93600",
  orangeSoft: "#FFF0E8",
  orangeSoftStrong: "#FFE1D2",
  orangeSoftDark: "#352018",
  graphite: "#111315",
  graphiteSoft: "#1A1D20",
  graphiteRaised: "#22262A",
  warmWhite: "#FAFAF8",
  paper: "#FFFFFF",
  mist: "#F1F1EE",
  mistStrong: "#E7E6E1",
  navy: "#0A1B35",
  navyRaised: "#102A4E",
  verified: "#20A447",
  verifiedDark: "#16853A",
  verifiedSoft: "#EAF7EE",
  amber: "#F5A623",
  amberDark: "#B96C00",
  error: "#E5484D",
  errorDark: "#B4232B",
  errorSoft: "#FDECEC",
  white: "#FFFFFF",
  black: "#090A0C",

  // Compatibility aliases for older imports. These intentionally resolve to the current orange system.
  emerald: "#FF5A16",
  emeraldBright: "#FF6A1A",
  emeraldDeep: "#C93D00",
  emeraldSoft: "#FFF0E8",
  emeraldSoftDark: "#352018",
  saffron: "#FF5A16",
  saffronSoft: "#FFF0E8",
  lime: "#FF5A16",
  limeDark: "#C93D00",
  limeSoft: "#FFF0E8",
  limeTintDark: "#352018",
  limeTintDarker: "#4A2618",
  success: "#FF5A16",
  successDark: "#C93D00",
  warning: "#F5A623",
};

export type ThemeColors = {
  surface: string;
  onSurface: string;
  surfaceSecondary: string;
  onSurfaceSecondary: string;
  surfaceTertiary: string;
  onSurfaceTertiary: string;
  surfaceElevated: string;
  surfaceInverse: string;
  onSurfaceInverse: string;
  brand: string;
  brandPressed: string;
  onBrand: string;
  brandSoft: string;
  onBrandSoft: string;
  success: string;
  verified: string;
  verifiedSoft: string;
  warning: string;
  error: string;
  errorSoft: string;
  border: string;
  borderStrong: string;
  divider: string;
  focusRing: string;
  disabledSurface: string;
  disabledContent: string;
  scrim: string;
  shadow: string;
  glassTint: string;
  isDark: boolean;
};

export const darkColors: ThemeColors = {
  surface: "#090A0C",
  onSurface: "#F8F8F5",
  surfaceSecondary: "#121416",
  onSurfaceSecondary: "#E6E4DE",
  surfaceTertiary: "#1B1E21",
  onSurfaceTertiary: "#A4A29C",
  surfaceElevated: "#22262A",
  surfaceInverse: "#FAFAF8",
  onSurfaceInverse: "#090A0C",
  brand: palette.orangeBright,
  brandPressed: "#E84B0B",
  onBrand: "#FFFFFF",
  brandSoft: palette.orangeSoftDark,
  onBrandSoft: "#FFB08A",
  success: palette.orangeBright,
  verified: palette.verified,
  verifiedSoft: "#112C20",
  warning: palette.amber,
  error: "#F06468",
  errorSoft: "#35191B",
  border: "#292C30",
  borderStrong: "#3A3E43",
  divider: "#202327",
  focusRing: "rgba(255,106,26,0.28)",
  disabledSurface: "#202327",
  disabledContent: "#6F7378",
  scrim: "rgba(0,0,0,0.64)",
  shadow: "#000000",
  glassTint: "rgba(255,255,255,0.07)",
  isDark: true,
};

export const lightColors: ThemeColors = {
  surface: "#FAFAF8",
  onSurface: "#111315",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#313338",
  surfaceTertiary: "#F1F1EE",
  onSurfaceTertiary: "#73716C",
  surfaceElevated: "#FFFFFF",
  surfaceInverse: "#111315",
  onSurfaceInverse: "#FAFAF8",
  brand: palette.orange,
  brandPressed: palette.orangeDeep,
  onBrand: "#FFFFFF",
  brandSoft: palette.orangeSoft,
  onBrandSoft: palette.orangeDeep,
  success: palette.orangeDeep,
  verified: palette.verifiedDark,
  verifiedSoft: palette.verifiedSoft,
  warning: palette.amberDark,
  error: palette.error,
  errorSoft: palette.errorSoft,
  border: "#E4E2DD",
  borderStrong: "#CBC8C0",
  divider: "#ECEAE5",
  focusRing: "rgba(255,90,22,0.20)",
  disabledSurface: "#ECEAE5",
  disabledContent: "#9A9892",
  scrim: "rgba(9,10,12,0.46)",
  shadow: "#342F2B",
  glassTint: "rgba(255,255,255,0.82)",
  isDark: false,
};

export const glass = {
  lightSurface: "rgba(255,255,255,0.86)",
  darkSurface: "rgba(18,20,22,0.86)",
  lightBorder: "rgba(17,19,21,0.08)",
  darkBorder: "rgba(255,255,255,0.10)",
  lightHighlight: "rgba(255,255,255,0.96)",
  darkHighlight: "rgba(255,255,255,0.07)",
  overlay: "rgba(9,10,12,0.46)",
};

export const aurora = {
  emerald: "rgba(255,90,22,0.14)",
  teal: "rgba(255,106,26,0.10)",
  saffron: "rgba(255,90,22,0.08)",
};

// Four-point baseline with larger rhythm steps for dashboards and operational screens.
export const spacing = {
  "2xs": 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  "2xl": 32,
  "3xl": 48,
  "4xl": 64,
};

export const radius = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 22,
  xl: 30,
  "2xl": 38,
  pill: 999,
};

export const fonts = {
  display: "Outfit-SemiBold",
  displayBold: "Outfit-Bold",
  regular: "Jakarta-Regular",
  medium: "Jakarta-Medium",
  semibold: "Jakarta-SemiBold",
  bold: "Jakarta-Bold",
};

export const fontSize = {
  xs: 11,
  sm: 12,
  base: 14,
  lg: 16,
  xl: 20,
  "2xl": 24,
  "3xl": 30,
  "4xl": 38,
  "5xl": 46,
};

export const lineHeight = {
  tight: 1.12,
  title: 1.2,
  body: 1.5,
  relaxed: 1.65,
};

export const control = {
  minTouch: 44,
  inputHeight: 56,
  buttonHeight: 54,
  buttonHeightSmall: 44,
  buttonHeightLarge: 60,
  iconButton: 44,
};

export const layout = {
  screenGutter: 20,
  screenGutterCompact: 16,
  contentMax: 720,
  tabletMax: 960,
};

export const motion = {
  fast: 120,
  standard: 180,
  deliberate: 280,
};

// Order and trip states deliberately avoid green. Only VERIFIED gets verification green.
export function statusColor(colors: ThemeColors, status?: string) {
  const s = (status || "").toUpperCase();
  if (["VERIFIED", "KYC_VERIFIED"].includes(s)) return colors.verified;
  if (["DELIVERED", "PAID", "ACTIVE", "APPROVED"].includes(s)) return colors.brand;
  if (
    [
      "DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "IN_PRODUCTION",
      "LOADING", "READY_TO_DISPATCH", "TM_ASSIGNED", "DRIVER_ASSIGNED",
      "ACCEPTED", "SCHEDULED", "POD_PENDING", "PRODUCTION_COMPLETE",
    ].includes(s)
  ) return colors.brand;
  if (["PENDING", "DRAFT", "PARTIAL", "REQUIRES_REVERIFICATION"].includes(s)) return colors.warning;
  if (["CANCELLED", "REJECTED", "UNPAID", "NOT_STARTED", "SUSPENDED", "DECLINED"].includes(s)) return colors.error;
  return colors.onSurfaceTertiary;
}

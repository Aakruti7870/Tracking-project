// TrackMyRMC Bolt Orange — premium industrial design tokens.
// Orange drives actions and operational state. Verification green is reserved for VERIFIED/KYC VERIFIED UI.

export const palette = {
  orange: "#FF5A16",
  orangeBright: "#FF6A1A",
  orangeDeep: "#C93D00",
  orangePressed: "#B93600",
  orangeSoft: "#FFF0E8",
  orangeSoftStrong: "#FFE1D2",
  orangeSoftDark: "#2C1D17",
  graphite: "#111315",
  graphiteSoft: "#1A1D20",
  graphiteRaised: "#22262A",
  warmWhite: "#FAFAF8",
  paper: "#FFFFFF",
  mist: "#F1F1EE",
  mistStrong: "#E7E6E1",
  navy: "#071522",
  navySoft: "#0B1F31",
  navyRaised: "#102A40",
  verified: "#20A447",
  verifiedDark: "#16853A",
  verifiedSoft: "#EAF7EE",
  amber: "#F5A623",
  amberDark: "#B96C00",
  error: "#E5484D",
  errorDark: "#B4232B",
  errorSoft: "#FDECEC",
  white: "#FFFFFF",
  black: "#050505",

  // Compatibility aliases for older imports. These intentionally resolve to the current orange system.
  emerald: "#FF5A16",
  emeraldBright: "#FF6A1A",
  emeraldDeep: "#C93D00",
  emeraldSoft: "#FFF0E8",
  emeraldSoftDark: "#2C1D17",
  saffron: "#FF5A16",
  saffronSoft: "#FFF0E8",
  lime: "#FF5A16",
  limeDark: "#C93D00",
  limeSoft: "#FFF0E8",
  limeTintDark: "#2C1D17",
  limeTintDarker: "#402217",
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
  surface: "#070707",
  onSurface: "#FAFAF8",
  surfaceSecondary: "#101010",
  onSurfaceSecondary: "#E7E3DF",
  surfaceTertiary: "#181818",
  onSurfaceTertiary: "#A7A19A",
  surfaceElevated: "#202020",
  surfaceInverse: "#FAFAF8",
  onSurfaceInverse: "#111315",
  brand: palette.orangeBright,
  brandPressed: "#E84B0B",
  onBrand: "#FFFFFF",
  brandSoft: "rgba(255,90,22,0.14)",
  onBrandSoft: "#FFC2A4",
  success: palette.orangeBright,
  verified: palette.verified,
  verifiedSoft: "#102D22",
  warning: palette.amber,
  error: "#F06468",
  errorSoft: "#35191B",
  border: "rgba(255,255,255,0.10)",
  borderStrong: "rgba(255,106,26,0.32)",
  divider: "rgba(255,255,255,0.07)",
  focusRing: "rgba(255,106,26,0.34)",
  disabledSurface: "#1A1A1A",
  disabledContent: "#6F6A65",
  scrim: "rgba(0,0,0,0.72)",
  shadow: "#000000",
  glassTint: "rgba(255,90,22,0.08)",
  isDark: true,
};

export const lightColors: ThemeColors = {
  surface: "#F7F8F6",
  onSurface: "#111827",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#303846",
  surfaceTertiary: "#F1F3F4",
  onSurfaceTertiary: "#707984",
  surfaceElevated: "#FFFFFF",
  surfaceInverse: palette.graphite,
  onSurfaceInverse: "#F8FAFC",
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
  border: "#E2E6EA",
  borderStrong: "#C9D0D7",
  divider: "#E8EBEE",
  focusRing: "rgba(255,90,22,0.20)",
  disabledSurface: "#ECEFF1",
  disabledContent: "#929AA3",
  scrim: "rgba(17,19,21,0.44)",
  shadow: "#213044",
  glassTint: "rgba(255,255,255,0.88)",
  isDark: false,
};

export const glass = {
  lightSurface: "rgba(255,255,255,0.90)",
  darkSurface: "rgba(12,12,12,0.88)",
  lightBorder: "rgba(17,24,39,0.08)",
  darkBorder: "rgba(255,106,26,0.18)",
  lightHighlight: "rgba(255,255,255,0.98)",
  darkHighlight: "rgba(255,255,255,0.08)",
  overlay: "rgba(0,0,0,0.58)",
};

export const aurora = {
  emerald: "rgba(255,90,22,0.14)",
  teal: "rgba(255,106,26,0.10)",
  saffron: "rgba(255,90,22,0.12)",
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

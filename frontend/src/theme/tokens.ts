// TrackMyRMC Bolt Orange — premium industrial design tokens.
// The app uses graphite, warm white and electric orange. Green is reserved only for verified state UI.

export const palette = {
  orange: "#FF5A16",
  orangeBright: "#FF6A1A",
  orangeDeep: "#C93D00",
  orangeSoft: "#FFF0E8",
  orangeSoftDark: "#352018",
  graphite: "#111315",
  graphiteSoft: "#1A1D20",
  warmWhite: "#FAFAF8",
  mist: "#F1F1EE",
  verified: "#20A447",
  verifiedDark: "#16853A",
  amber: "#F5A623",
  error: "#E5484D",
  white: "#FFFFFF",
  black: "#090A0C",

  // Compatibility aliases for older imports. These intentionally resolve to the new orange family.
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
  surfaceInverse: string;
  onSurfaceInverse: string;
  brand: string;
  onBrand: string;
  brandSoft: string;
  onBrandSoft: string;
  success: string;
  verified: string;
  warning: string;
  error: string;
  border: string;
  borderStrong: string;
  divider: string;
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
  surfaceInverse: "#FAFAF8",
  onSurfaceInverse: "#090A0C",
  brand: palette.orangeBright,
  onBrand: "#FFFFFF",
  brandSoft: palette.orangeSoftDark,
  onBrandSoft: "#FFB08A",
  success: palette.orangeBright,
  verified: palette.verified,
  warning: palette.amber,
  error: palette.error,
  border: "#292C30",
  borderStrong: "#3A3E43",
  divider: "#202327",
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
  surfaceInverse: "#111315",
  onSurfaceInverse: "#FAFAF8",
  brand: palette.orange,
  onBrand: "#FFFFFF",
  brandSoft: palette.orangeSoft,
  onBrandSoft: palette.orangeDeep,
  success: palette.orangeDeep,
  verified: palette.verifiedDark,
  warning: "#B96C00",
  error: palette.error,
  border: "#E4E2DD",
  borderStrong: "#CBC8C0",
  divider: "#ECEAE5",
  glassTint: "rgba(255,255,255,0.82)",
  isDark: false,
};

export const glass = {
  lightSurface: "rgba(255,255,255,0.84)",
  darkSurface: "rgba(18,20,22,0.82)",
  lightBorder: "rgba(17,19,21,0.08)",
  darkBorder: "rgba(255,255,255,0.10)",
  lightHighlight: "rgba(255,255,255,0.94)",
  darkHighlight: "rgba(255,255,255,0.07)",
  overlay: "rgba(9,10,12,0.42)",
};

export const aurora = {
  emerald: "rgba(255,90,22,0.14)",
  teal: "rgba(255,106,26,0.10)",
  saffron: "rgba(255,90,22,0.08)",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  "2xl": 32,
  "3xl": 48,
};

export const radius = {
  sm: 8,
  md: 14,
  lg: 22,
  xl: 30,
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
  sm: 12,
  base: 14,
  lg: 16,
  xl: 20,
  "2xl": 24,
  "3xl": 30,
};

// Order and trip states deliberately avoid green. Only VERIFIED gets the verification green.
export function statusColor(colors: ThemeColors, status?: string) {
  const s = (status || "").toUpperCase();
  if (s === "VERIFIED") return colors.verified;
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

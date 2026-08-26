// TrackMyRMC Choice B — Emerald Aurora Glass design tokens.
// Light + Dark keep identical information architecture and semantic color roles.

export const palette = {
  emerald: "#0F8A6A",
  emeraldBright: "#19B98A",
  emeraldDeep: "#075E4A",
  emeraldSoft: "#DDF7EE",
  emeraldSoftDark: "#123F34",
  saffron: "#F59E0B",
  saffronSoft: "#FFF0D5",
  lime: "#CCFF00", // retained for backward compatibility with legacy imports
  limeDark: "#B2D700",
  limeSoft: "#E6FF80",
  limeTintDark: "#1A2000",
  limeTintDarker: "#334000",
  success: "#0FA66E",
  successDark: "#0B7E56",
  warning: "#F59E0B",
  error: "#E5484D",
  white: "#FFFFFF",
  black: "#0B1512",
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
  warning: string;
  error: string;
  border: string;
  borderStrong: string;
  divider: string;
  glassTint: string;
  isDark: boolean;
};

export const darkColors: ThemeColors = {
  surface: "#07120F",
  onSurface: "#F5FFF9",
  surfaceSecondary: "#0D1D18",
  onSurfaceSecondary: "#D7E8E1",
  surfaceTertiary: "#163029",
  onSurfaceTertiary: "#9EB7AE",
  surfaceInverse: "#F5FFF9",
  onSurfaceInverse: "#07120F",
  brand: palette.emeraldBright,
  onBrand: "#04130F",
  brandSoft: palette.emeraldSoftDark,
  onBrandSoft: "#C7F5E6",
  success: palette.success,
  warning: palette.warning,
  error: palette.error,
  border: "#1D3A31",
  borderStrong: "#31584C",
  divider: "#142921",
  glassTint: "rgba(236,255,248,0.10)",
  isDark: true,
};

export const lightColors: ThemeColors = {
  surface: "#F2FBF7",
  onSurface: "#0A211A",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#18372E",
  surfaceTertiary: "#E4F3ED",
  onSurfaceTertiary: "#55736A",
  surfaceInverse: "#0A211A",
  onSurfaceInverse: "#F7FFFB",
  brand: palette.emerald,
  onBrand: "#FFFFFF",
  brandSoft: palette.emeraldSoft,
  onBrandSoft: palette.emeraldDeep,
  success: palette.successDark,
  warning: "#B96C00",
  error: palette.error,
  border: "#CFE4DC",
  borderStrong: "#A9C9BE",
  divider: "#DCECE6",
  glassTint: "rgba(255,255,255,0.68)",
  isDark: false,
};

export const glass = {
  lightSurface: "rgba(255,255,255,0.72)",
  darkSurface: "rgba(10,31,25,0.78)",
  lightBorder: "rgba(7,94,74,0.14)",
  darkBorder: "rgba(127,255,211,0.16)",
  lightHighlight: "rgba(255,255,255,0.82)",
  darkHighlight: "rgba(255,255,255,0.08)",
  overlay: "rgba(0,18,13,0.38)",
};

export const aurora = {
  emerald: "rgba(25,185,138,0.18)",
  teal: "rgba(15,138,106,0.14)",
  saffron: "rgba(245,158,11,0.10)",
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
  sm: 6,
  md: 12,
  lg: 20,
  xl: 28,
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

// Status color mapping for order / trip states.
export function statusColor(colors: ThemeColors, status?: string) {
  const s = (status || "").toUpperCase();
  if (["DELIVERED", "PAID", "VERIFIED", "ACTIVE", "APPROVED"].includes(s))
    return colors.success;
  if (
    [
      "DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "IN_PRODUCTION",
      "LOADING", "READY_TO_DISPATCH", "TM_ASSIGNED", "DRIVER_ASSIGNED",
      "ACCEPTED", "SCHEDULED", "POD_PENDING", "PRODUCTION_COMPLETE",
    ].includes(s)
  )
    return colors.brand;
  if (["PENDING", "DRAFT", "PARTIAL", "REQUIRES_REVERIFICATION"].includes(s))
    return colors.warning;
  if (["CANCELLED", "REJECTED", "UNPAID", "NOT_STARTED", "SUSPENDED", "DECLINED"].includes(s))
    return colors.error;
  return colors.onSurfaceTertiary;
}

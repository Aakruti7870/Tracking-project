// TrackMyRMC design tokens — charcoal/graphite base + electric lime accent.
// Derived from design_guidelines.json. Light + Dark, identical IA.

export const palette = {
  lime: "#CCFF00",
  limeDark: "#B2D700",
  limeSoft: "#E6FF80",
  limeTintDark: "#1A2000",
  limeTintDarker: "#334000",
  success: "#00E676",
  successDark: "#00A152",
  warning: "#FFC107",
  error: "#FF3B30",
  white: "#FFFFFF",
  black: "#121212",
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
  surface: "#121212",
  onSurface: "#FFFFFF",
  surfaceSecondary: "#1C1C1E",
  onSurfaceSecondary: "#E0E0E0",
  surfaceTertiary: "#2C2C2E",
  onSurfaceTertiary: "#B0B0B0",
  surfaceInverse: "#FFFFFF",
  onSurfaceInverse: "#121212",
  brand: palette.lime,
  onBrand: "#121212",
  brandSoft: palette.limeTintDarker,
  onBrandSoft: palette.limeSoft,
  success: palette.success,
  warning: palette.warning,
  error: palette.error,
  border: "#2C2C2E",
  borderStrong: "#4A4A4C",
  divider: "#1C1C1E",
  glassTint: "rgba(255,255,255,0.12)",
  isDark: true,
};

export const lightColors: ThemeColors = {
  surface: "#F5F5F5",
  onSurface: "#121212",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#333333",
  surfaceTertiary: "#EBEBEB",
  onSurfaceTertiary: "#555555",
  surfaceInverse: "#121212",
  onSurfaceInverse: "#FFFFFF",
  brand: "#B2D700",
  onBrand: "#121212",
  brandSoft: palette.limeSoft,
  onBrandSoft: palette.limeTintDarker,
  success: palette.successDark,
  warning: "#C79100",
  error: palette.error,
  border: "#E0E0E0",
  borderStrong: "#C4C4C4",
  divider: "#EEEEEE",
  glassTint: "rgba(255,255,255,0.6)",
  isDark: false,
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
import React from "react";
import { Platform, StyleSheet, View, ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";
import { AppText } from "./AppText";

/**
 * Map adapter placeholder. Native Android can use the configured Google Maps
 * integration, while web intentionally presents a clear Android-app fallback
 * until an interactive browser map is implemented.
 */
export function MapPlaceholder({
  pins = 0,
  label = "Live map",
  style,
  compact = false,
}: {
  pins?: number;
  label?: string;
  style?: ViewStyle;
  compact?: boolean;
}) {
  const { colors } = useTheme();

  const grid = colors.isDark ? "rgba(204,255,0,0.06)" : "rgba(18,18,18,0.05)";
  const mapsConfigured = !!process.env.EXPO_PUBLIC_GOOGLE_MAPS_KEY;
  const isWeb = Platform.OS === "web";
  const mapAvailable = isWeb || mapsConfigured;
  const statusLabel = isWeb ? "Android app map" : mapsConfigured ? "Live map" : "Maps: not configured";

  return (
    <View style={[styles.wrap, { borderColor: colors.border }, style]}>
      <LinearGradient
        colors={colors.isDark ? ["#1C1C1E", "#121212"] : ["#EDEDED", "#F7F7F7"]}
        style={StyleSheet.absoluteFill}
      />
      {/* faux grid lines */}
      {[...Array(6)].map((_, i) => (
        <View key={`h${i}`} style={[styles.hLine, { top: `${(i + 1) * 14}%`, backgroundColor: grid }]} />
      ))}
      {[...Array(5)].map((_, i) => (
        <View key={`v${i}`} style={[styles.vLine, { left: `${(i + 1) * 18}%`, backgroundColor: grid }]} />
      ))}

      <View style={styles.center}>
        <View style={[styles.pinBubble, { backgroundColor: colors.brand }]}>
          <Ionicons name="location" size={compact ? 20 : 28} color={colors.onBrand} />
        </View>
        {!compact ? (
          <AppText variant="caption" center style={{ marginTop: spacing.sm }}>
            {pins > 0 ? `${pins} plant${pins > 1 ? "s" : ""} nearby` : label}
          </AppText>
        ) : null}
      </View>

      <View style={[styles.chip, { backgroundColor: colors.surface + "CC", borderColor: colors.border }]}>
        <Ionicons
          name={mapAvailable ? "map-outline" : "warning-outline"}
          size={12}
          color={mapAvailable ? colors.brand : colors.warning}
        />
        <AppText style={{ fontFamily: fonts.medium, fontSize: 10, color: colors.onSurfaceTertiary }}>
          {statusLabel}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: "hidden",
    minHeight: 160,
    justifyContent: "center",
  },
  hLine: { position: "absolute", left: 0, right: 0, height: 1 },
  vLine: { position: "absolute", top: 0, bottom: 0, width: 1 },
  center: { alignItems: "center", justifyContent: "center", flex: 1 },
  pinBubble: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.3,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  chip: {
    position: "absolute",
    bottom: spacing.sm,
    right: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
});

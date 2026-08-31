import React from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";

import { useTheme } from "@/src/theme/ThemeProvider";

// Single approved TrackMyRMC scene. It responds to the active theme via a tint
// overlay and blends into the page background on the bottom + side edges (no
// hard border), so it feels part of the UI in both light and dark mode.
const BRAND_HERO = require("../../assets/images/brand-hero.jpg");

type BrandHeroProps = {
  /** Extra padding pushed inside the top of the hero (e.g. safe-area inset). */
  topInset?: number;
  style?: StyleProp<ViewStyle>;
};

export function BrandHero({ topInset = 0, style }: BrandHeroProps) {
  const { colors } = useTheme();
  const bg = colors.surface;

  // Theme-responsive tint: lighten the (dark) scene in light mode, deepen it
  // slightly in dark mode, so it always matches the surrounding surface.
  const tint = colors.isDark ? "rgba(6,8,10,0.30)" : "rgba(255,255,255,0.30)";
  // Fully-transparent variant of the background for smooth edge fades.
  const bgClear = colors.isDark ? "rgba(6,8,10,0)" : "rgba(245,246,244,0)";
  const bgSolid = colors.isDark ? "#06080A" : bg;

  return (
    <View style={[styles.wrap, { backgroundColor: bgSolid }, style]}>
      <Image
        source={BRAND_HERO}
        style={StyleSheet.absoluteFill}
        contentFit="cover"
        contentPosition="center"
        transition={200}
      />

      {/* Theme tint keeps the scene legible and on-brand in both modes. */}
      <View pointerEvents="none" style={[StyleSheet.absoluteFill, { backgroundColor: tint }]} />

      {/* Bottom edge fades into the page background. */}
      <LinearGradient
        pointerEvents="none"
        colors={[bgClear, bgClear, bgSolid]}
        locations={[0, 0.62, 1]}
        style={StyleSheet.absoluteFill}
      />
      {/* Left edge fade. */}
      <LinearGradient
        pointerEvents="none"
        colors={[bgSolid, bgClear]}
        locations={[0, 0.22]}
        start={{ x: 0, y: 0.5 }}
        end={{ x: 1, y: 0.5 }}
        style={StyleSheet.absoluteFill}
      />
      {/* Right edge fade. */}
      <LinearGradient
        pointerEvents="none"
        colors={[bgClear, bgSolid]}
        locations={[0.78, 1]}
        start={{ x: 0, y: 0.5 }}
        end={{ x: 1, y: 0.5 }}
        style={StyleSheet.absoluteFill}
      />

      <View style={{ height: topInset }} />
    </View>
  );
}

const styles = StyleSheet.create({
  // Full width of the parent card, no gaps. aspectRatio keeps the scene crisp
  // (no stretch); maxHeight prevents it dominating tall/desktop viewports while
  // cover-fill guarantees the width is always filled edge to edge.
  // Fills the full width of the parent card on phones (no gaps) while the
  // aspectRatio keeps the whole approved scene — logo, wordmark and mixer —
  // crisp and un-cropped. On large/desktop viewports the width is capped and
  // centered so the hero never becomes a giant banner; the side/bottom fades
  // let the capped edges melt into the page background (no hard rectangle).
  wrap: {
    width: "100%",
    maxWidth: 600,
    alignSelf: "center",
    aspectRatio: 1.5,
    overflow: "hidden",
    justifyContent: "flex-start",
  },
});

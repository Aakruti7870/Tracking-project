import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import { Image } from "expo-image";

import { useTheme } from "@/src/theme/ThemeProvider";
import { radius } from "@/src/theme/tokens";

// Dedicated light / dark artwork so the post-login banner follows the active
// theme. Dark mode keeps the original dark scene; light mode uses a softly
// light-washed variant so it feels native to the light surface.
const HERO_LIGHT = require("../../assets/images/home-hero-light.jpg");
const HERO_DARK = require("../../assets/images/home-hero-dark.jpg");

type Props = {
  height?: number;
  style?: ViewStyle;
};

/**
 * Theme-aware "Track My RMC" brand banner shown at the top of every role home.
 * Uses contentFit="contain" so the full brand artwork (logo, mixer truck and
 * RMC plant) stays visible and never crops on any screen size, while the
 * matching backdrop colour keeps the edges seamless in both light and dark.
 */
export function HomeHero({ height = 176, style }: Props) {
  const { colors } = useTheme();
  const heroSource = colors.isDark ? HERO_DARK : HERO_LIGHT;

  return (
    <View
      style={[
        styles.wrap,
        {
          height,
          backgroundColor: colors.isDark ? "#080A0C" : "#EFF1EE",
          borderColor: colors.border,
        },
        style,
      ]}
    >
      <Image
        source={heroSource}
        style={StyleSheet.absoluteFill}
        contentFit="contain"
        contentPosition="center"
        transition={200}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    borderRadius: radius.xl,
    overflow: "hidden",
    borderWidth: 1,
  },
});

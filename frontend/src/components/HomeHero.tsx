import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import { Image } from "expo-image";

import { useTheme } from "@/src/theme/ThemeProvider";
import { radius } from "@/src/theme/tokens";

const HERO_LIGHT = require("../../assets/images/home-hero-light.jpg");
const HERO_DARK = require("../../assets/images/home-hero-dark.jpg");

type Props = {
  height?: number;
  style?: ViewStyle;
};

/**
 * Theme-aware 16:9 Track My RMC hero. The source artwork is always rendered
 * with `contain`, so the logo, text, mixer and plant remain fully visible on
 * phones, tablets and web without cropping. Local assets are given high
 * priority and no transition delay to avoid a perceived lazy-load flash.
 */
export function HomeHero({ height, style }: Props) {
  const { colors } = useTheme();
  const heroSource = colors.isDark ? HERO_DARK : HERO_LIGHT;

  return (
    <View
      style={[
        styles.wrap,
        height ? { height } : styles.ratio16x9,
        {
          backgroundColor: colors.isDark ? "#080A0C" : "#F7F8F6",
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
        priority="high"
        cachePolicy="memory-disk"
        transition={0}
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
  ratio16x9: {
    aspectRatio: 16 / 9,
  },
});

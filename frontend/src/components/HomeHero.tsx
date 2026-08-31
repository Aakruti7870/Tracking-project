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
 * Theme-aware 16:9 Track My RMC hero. The artwork always keeps its native
 * 16:9 frame, even when older callers still pass a legacy height value. This
 * prevents letterboxing/cropping and keeps the logo, text, mixer and plant
 * fully visible on phones, tablets and web. Local assets render immediately
 * from the Expo image cache with no transition flash.
 */
export function HomeHero({ style }: Props) {
  const { colors } = useTheme();
  const heroSource = colors.isDark ? HERO_DARK : HERO_LIGHT;

  return (
    <View
      style={[
        styles.wrap,
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
    aspectRatio: 16 / 9,
    borderRadius: radius.xl,
    overflow: "hidden",
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});

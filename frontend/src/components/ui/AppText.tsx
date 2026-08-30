import React from "react";
import { StyleSheet, Text, TextProps, TextStyle } from "react-native";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize } from "@/src/theme/tokens";

type Variant =
  | "display"
  | "title"
  | "heading"
  | "body"
  | "bodyMuted"
  | "label"
  | "caption";

type Props = TextProps & {
  variant?: Variant;
  color?: string;
  center?: boolean;
  children: React.ReactNode;
};

export function AppText({ variant = "body", color, center, style, children, ...rest }: Props) {
  const { colors } = useTheme();

  const variants: Record<Variant, TextStyle> = {
    display: {
      fontFamily: fonts.displayBold,
      fontSize: fontSize["3xl"],
      lineHeight: 36,
      letterSpacing: -0.6,
      color: colors.onSurface,
    },
    title: {
      fontFamily: fonts.display,
      fontSize: fontSize["2xl"],
      lineHeight: 30,
      letterSpacing: -0.3,
      color: colors.onSurface,
    },
    heading: {
      fontFamily: fonts.semibold,
      fontSize: fontSize.xl,
      lineHeight: 26,
      letterSpacing: -0.15,
      color: colors.onSurface,
    },
    body: {
      fontFamily: fonts.regular,
      fontSize: fontSize.base,
      lineHeight: 21,
      color: colors.onSurface,
    },
    bodyMuted: {
      fontFamily: fonts.regular,
      fontSize: fontSize.base,
      lineHeight: 21,
      color: colors.onSurfaceTertiary,
    },
    label: {
      fontFamily: fonts.semibold,
      fontSize: fontSize.sm,
      lineHeight: 17,
      letterSpacing: 0.05,
      color: colors.onSurfaceSecondary,
    },
    caption: {
      fontFamily: fonts.regular,
      fontSize: fontSize.sm,
      lineHeight: 18,
      color: colors.onSurfaceTertiary,
    },
  };

  return (
    <Text
      {...rest}
      style={[variants[variant], color ? { color } : null, center ? styles.center : null, style]}
    >
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({ center: { textAlign: "center" } });
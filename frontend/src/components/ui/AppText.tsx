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
    display: { fontFamily: fonts.displayBold, fontSize: fontSize["3xl"], color: colors.onSurface },
    title: { fontFamily: fonts.display, fontSize: fontSize["2xl"], color: colors.onSurface },
    heading: { fontFamily: fonts.semibold, fontSize: fontSize.xl, color: colors.onSurface },
    body: { fontFamily: fonts.regular, fontSize: fontSize.base, color: colors.onSurface },
    bodyMuted: { fontFamily: fonts.regular, fontSize: fontSize.base, color: colors.onSurfaceTertiary },
    label: { fontFamily: fonts.medium, fontSize: fontSize.sm, color: colors.onSurfaceSecondary },
    caption: { fontFamily: fonts.regular, fontSize: fontSize.sm, color: colors.onSurfaceTertiary },
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

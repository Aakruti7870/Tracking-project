import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";
import * as Haptics from "expo-haptics";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "md" | "sm";

type Props = {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  fullWidth?: boolean;
  style?: ViewStyle;
  testID?: string;
};

export function Button({
  label,
  onPress,
  variant = "primary",
  size = "md",
  loading,
  disabled,
  icon,
  fullWidth = true,
  style,
  testID,
}: Props) {
  const { colors } = useTheme();
  const isDisabled = disabled || loading;

  const bg = {
    primary: colors.brand,
    secondary: colors.surfaceTertiary,
    outline: "transparent",
    ghost: "transparent",
    danger: colors.error,
  }[variant];

  const fg = {
    primary: colors.onBrand,
    secondary: colors.onSurface,
    outline: colors.onSurface,
    ghost: colors.brand,
    danger: "#FFFFFF",
  }[variant];

  const border = variant === "outline" ? colors.borderStrong : "transparent";

  return (
    <Pressable
      testID={testID}
      onPress={() => {
        if (isDisabled) return;
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        onPress?.();
      }}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        size === "sm" ? styles.small : null,
        {
          backgroundColor: bg,
          borderColor: border,
          borderWidth: variant === "outline" ? 1 : 0,
          opacity: isDisabled ? 0.5 : pressed ? 0.85 : 1,
          alignSelf: fullWidth ? "stretch" : "flex-start",
          transform: [{ scale: pressed && !isDisabled ? 0.98 : 1 }],
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.content}>
          {icon}
          <Text style={[styles.label, size === "sm" ? styles.smallLabel : null, { color: fg }]}>{label}</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    height: 52,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  small: {
    height: 38,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
  },
  content: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  label: { fontFamily: fonts.semibold, fontSize: fontSize.lg },
  smallLabel: { fontSize: fontSize.sm },
});

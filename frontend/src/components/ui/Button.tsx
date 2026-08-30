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
  accessibilityLabel?: string;
  accessibilityHint?: string;
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
  accessibilityLabel,
  accessibilityHint,
}: Props) {
  const { colors } = useTheme();
  const isDisabled = Boolean(disabled || loading);

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
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel || label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: isDisabled, busy: Boolean(loading) }}
      hitSlop={size === "sm" ? 4 : 2}
      onPress={() => {
        if (isDisabled) return;
        void Haptics.impactAsync(
          variant === "danger" ? Haptics.ImpactFeedbackStyle.Medium : Haptics.ImpactFeedbackStyle.Light,
        );
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
          opacity: isDisabled ? 0.46 : pressed ? 0.90 : 1,
          alignSelf: fullWidth ? "stretch" : "flex-start",
          transform: [{ scale: pressed && !isDisabled ? 0.985 : 1 }],
          shadowColor: variant === "primary" ? colors.brand : "transparent",
          shadowOpacity: variant === "primary" && !isDisabled ? 0.18 : 0,
        },
        style,
      ]}
    >
      {loading ? (
        <View style={styles.content}>
          <ActivityIndicator color={fg} size="small" />
          <Text style={[styles.label, size === "sm" ? styles.smallLabel : null, { color: fg }]}>Working…</Text>
        </View>
      ) : (
        <View style={styles.content}>
          {icon}
          <Text numberOfLines={1} style={[styles.label, size === "sm" ? styles.smallLabel : null, { color: fg }]}>
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 54,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    shadowOffset: { width: 0, height: 7 },
    shadowRadius: 16,
    elevation: 3,
  },
  small: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    elevation: 0,
  },
  content: {
    minHeight: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  label: { fontFamily: fonts.semibold, fontSize: fontSize.lg, letterSpacing: 0.1 },
  smallLabel: { fontSize: fontSize.sm },
});

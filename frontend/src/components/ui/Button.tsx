import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleProp,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";
import * as Haptics from "expo-haptics";

import { useTheme } from "@/src/theme/ThemeProvider";
import { control, fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "lg" | "md" | "sm";

type Props = {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  loadingLabel?: string;
  disabled?: boolean;
  icon?: React.ReactNode;
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
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
  loadingLabel = "Working…",
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

  const baseBackground = {
    primary: colors.brand,
    secondary: colors.surfaceTertiary,
    outline: "transparent",
    ghost: "transparent",
    danger: colors.error,
  }[variant];

  const foreground = {
    primary: colors.onBrand,
    secondary: colors.onSurface,
    outline: colors.onSurface,
    ghost: colors.brand,
    danger: "#FFFFFF",
  }[variant];

  const borderColor = {
    primary: colors.brand,
    secondary: colors.border,
    outline: colors.borderStrong,
    ghost: "transparent",
    danger: colors.error,
  }[variant];

  const pressedBackground = {
    primary: colors.brandPressed,
    secondary: colors.surfaceElevated,
    outline: colors.surfaceTertiary,
    ghost: colors.brandSoft,
    danger: colors.isDark ? "#C6363B" : "#C83239",
  }[variant];

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
          variant === "danger"
            ? Haptics.ImpactFeedbackStyle.Medium
            : Haptics.ImpactFeedbackStyle.Light,
        );
        onPress?.();
      }}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        size === "lg" ? styles.large : size === "sm" ? styles.small : styles.medium,
        {
          backgroundColor: isDisabled ? colors.disabledSurface : pressed ? pressedBackground : baseBackground,
          borderColor: isDisabled ? colors.border : borderColor,
          opacity: 1,
          alignSelf: fullWidth ? "stretch" : "flex-start",
          transform: [{ scale: pressed && !isDisabled ? 0.985 : 1 }],
          shadowColor: variant === "primary" && !isDisabled ? colors.brand : colors.shadow,
          shadowOpacity: variant === "primary" && !isDisabled ? (colors.isDark ? 0.28 : 0.18) : 0,
          elevation: variant === "primary" && !isDisabled ? 3 : 0,
        },
        style,
      ]}
    >
      <View style={styles.content}>
        {loading ? <ActivityIndicator color={isDisabled ? colors.disabledContent : foreground} size="small" /> : icon}
        <Text
          numberOfLines={1}
          style={[
            styles.label,
            size === "lg" ? styles.largeLabel : size === "sm" ? styles.smallLabel : null,
            { color: isDisabled ? colors.disabledContent : foreground },
          ]}
        >
          {loading ? loadingLabel : label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    shadowOffset: { width: 0, height: 7 },
    shadowRadius: 16,
  },
  large: {
    minHeight: control.buttonHeightLarge,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.xl,
  },
  medium: {
    minHeight: control.buttonHeight,
    borderRadius: radius.md,
    paddingHorizontal: spacing.xl,
  },
  small: {
    minHeight: control.buttonHeightSmall,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
  },
  content: {
    minHeight: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  label: {
    fontFamily: fonts.semibold,
    fontSize: fontSize.lg,
    lineHeight: 22,
    letterSpacing: 0.05,
  },
  largeLabel: { fontFamily: fonts.bold, fontSize: fontSize.lg, letterSpacing: 0.1 },
  smallLabel: { fontSize: fontSize.sm, lineHeight: 17 },
});

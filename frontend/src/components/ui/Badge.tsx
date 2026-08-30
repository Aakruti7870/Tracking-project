import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing, statusColor } from "@/src/theme/tokens";

type Props = {
  label: string;
  status?: string;
  color?: string;
  solid?: boolean;
  testID?: string;
};

export function Badge({ label, status, color, solid = false, testID }: Props) {
  const { colors } = useTheme();
  const c = color || statusColor(colors, status || label);
  return (
    <View
      testID={testID}
      accessibilityRole="text"
      accessibilityLabel={label}
      style={[
        styles.badge,
        solid
          ? { backgroundColor: c }
          : { backgroundColor: c + "16", borderColor: c + "44", borderWidth: 1 },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: solid ? colors.onBrand : c }]} />
      <Text
        style={[
          styles.text,
          { color: solid ? (c === colors.brand ? colors.onBrand : "#FFFFFF") : c },
        ]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    minHeight: 26,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    alignSelf: "flex-start",
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: { fontFamily: fonts.semibold, fontSize: fontSize.sm, lineHeight: 16 },
});
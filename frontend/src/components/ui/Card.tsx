import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";

import { useTheme } from "@/src/theme/ThemeProvider";
import { radius, spacing } from "@/src/theme/tokens";

type Props = {
  children: React.ReactNode;
  style?: ViewStyle;
  padded?: boolean;
  testID?: string;
};

export function Card({ children, style, padded = true, testID }: Props) {
  const { colors } = useTheme();
  return (
    <View
      testID={testID}
      style={[
        styles.card,
        {
          backgroundColor: colors.surfaceSecondary,
          borderColor: colors.border,
          padding: padded ? spacing.lg : 0,
          shadowColor: colors.isDark ? "#000" : "#8A8A8A",
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: 1,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 2,
  },
});

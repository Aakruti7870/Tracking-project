import React from "react";
import { StatusBar } from "expo-status-bar";
import { StyleSheet, View, ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";
import { AppText } from "./AppText";

type Props = {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  right?: React.ReactNode;
  scroll?: boolean;
  padded?: boolean;
  style?: ViewStyle;
};

/** Safe-area aware screen shell with a sticky, consistent header. */
export function Screen({ children, title, subtitle, right, padded = true, style }: Props) {
  const { colors, scheme } = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.root, { backgroundColor: colors.surface }]}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      {title ? (
        <View style={[styles.header, { borderBottomColor: colors.divider }]}>
          <View style={{ flex: 1 }}>
            <AppText variant="title">{title}</AppText>
            {subtitle ? (
              <AppText variant="caption" style={{ marginTop: 2 }}>
                {subtitle}
              </AppText>
            ) : null}
          </View>
          {right}
        </View>
      ) : null}
      <View
        style={[
          styles.body,
          { paddingHorizontal: padded ? spacing.lg : 0 },
          style,
        ]}
      >
        {children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    paddingTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  body: { flex: 1 },
});

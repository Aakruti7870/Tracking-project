import React from "react";
import { StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";
import { AppText } from "./ui/AppText";
import { Button } from "./ui/Button";

export function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={styles.wrap} testID="error-view">
      <Ionicons name="cloud-offline-outline" size={40} color={colors.error} />
      <AppText variant="heading" center>Something went wrong</AppText>
      <AppText variant="bodyMuted" center>{message}</AppText>
      <Button label="Retry" onPress={onRetry} fullWidth={false} variant="outline" testID="retry-button" />
    </View>
  );
}

export function EmptyView({
  icon = "file-tray-outline",
  title,
  subtitle,
  cta,
  onCta,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  cta?: string;
  onCta?: () => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.wrap} testID="empty-view">
      <View style={[styles.iconBubble, { backgroundColor: colors.surfaceTertiary }]}>
        <Ionicons name={icon} size={32} color={colors.onSurfaceTertiary} />
      </View>
      <AppText variant="heading" center>{title}</AppText>
      {subtitle ? <AppText variant="bodyMuted" center>{subtitle}</AppText> : null}
      {cta && onCta ? (
        <Button label={cta} onPress={onCta} fullWidth={false} testID="empty-cta" />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", justifyContent: "center", gap: spacing.md, padding: spacing.xl, flexGrow: 1 },
  iconBubble: { width: 72, height: 72, borderRadius: 36, alignItems: "center", justifyContent: "center" },
});

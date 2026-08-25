import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Badge } from "@/src/components/ui/Badge";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const MODES: { key: "system" | "light" | "dark"; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "light", label: "Light", icon: "sunny-outline" },
  { key: "dark", label: "Dark", icon: "moon-outline" },
  { key: "system", label: "System", icon: "phone-portrait-outline" },
];

export function StaffMore() {
  const { colors, mode, setMode } = useTheme();
  const { user, signOut } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const doLogout = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }} showsVerticalScrollIndicator={false}>
        <AppText variant="title">More</AppText>

        <Card style={{ flexDirection: "row", alignItems: "center", gap: spacing.md }}>
          <View style={[styles.avatar, { backgroundColor: colors.brand }]}>
            <AppText style={{ fontFamily: fonts.displayBold, fontSize: fontSize.xl, color: colors.onBrand }}>
              {(user?.name || "U").charAt(0).toUpperCase()}
            </AppText>
          </View>
          <View style={{ flex: 1, gap: 4 }}>
            <AppText variant="heading" numberOfLines={1}>{user?.name}</AppText>
            <AppText variant="caption">{user?.email || user?.phone}</AppText>
            <View style={{ flexDirection: "row", gap: spacing.xs }}>
              <Badge label={user?.role_label || "Staff"} color={colors.brand} />
            </View>
          </View>
        </Card>

        <View style={{ gap: spacing.sm }}>
          <AppText variant="label">Appearance</AppText>
          <View style={styles.modeRow}>
            {MODES.map((m) => {
              const selected = mode === m.key;
              return (
                <Pressable
                  key={m.key}
                  testID={`theme-mode-${m.key}`}
                  onPress={() => setMode(m.key)}
                  style={[styles.mode, { backgroundColor: selected ? colors.brand : colors.surfaceSecondary, borderColor: selected ? colors.brand : colors.border }]}
                >
                  <Ionicons name={m.icon} size={18} color={selected ? colors.onBrand : colors.onSurfaceSecondary} />
                  <AppText style={{ fontFamily: fonts.medium, fontSize: fontSize.sm, color: selected ? colors.onBrand : colors.onSurfaceSecondary }}>{m.label}</AppText>
                </Pressable>
              );
            })}
          </View>
        </View>

        {user?.role === "authority" || user?.role === "central_admin" ? (
          <View style={{ gap: spacing.sm }}>
            <Pressable testID="authority-plans-promotions" onPress={() => router.push("/plans-promotions" as any)} style={[styles.manage, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
              <Ionicons name="diamond-outline" size={20} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText style={{ fontFamily: fonts.semibold, color: colors.onSurface }}>Plans &amp; Promotions</AppText>
                <AppText variant="caption">Premium, promoted listings and promo codes</AppText>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
            </Pressable>
            <Pressable testID="authority-payment-control" onPress={() => router.push("/authority/payment-control" as any)} style={[styles.manage, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
              <Ionicons name="card-outline" size={20} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText style={{ fontFamily: fonts.semibold, color: colors.onSurface }}>Payment &amp; Plan Control</AppText>
                <AppText variant="caption">Cashfree, activations, promo usage and audit</AppText>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>
        ) : null}

        <Pressable testID="logout-button" onPress={doLogout} style={[styles.logout, { borderColor: colors.error }]}>
          <Ionicons name="log-out-outline" size={20} color={colors.error} />
          <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.error }}>Logout</AppText>
        </Pressable>

        <AppText variant="caption" center>TrackMyRMC · v2.0.9 (67)</AppText>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { width: 56, height: 56, borderRadius: 28, alignItems: "center", justifyContent: "center" },
  modeRow: { flexDirection: "row", gap: spacing.sm },
  mode: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs, height: 44, borderRadius: radius.md, borderWidth: 1 },
  logout: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, height: 52, borderRadius: radius.md, borderWidth: 1 },
  manage: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 64, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
});

import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Pressable } from "react-native";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const SECTIONS: { key: string; label: string; icon: keyof typeof Ionicons.glyphMap; desc: string }[] = [
  { key: "production", label: "Production", icon: "cog-outline", desc: "Start & complete batching per order", route: "/owner/orders" },
  { key: "dispatch", label: "Dispatch", icon: "navigate-outline", desc: "Assign TM & driver, dispatch", route: "/owner/orders" },
  { key: "billing", label: "Billing & Ledger", icon: "wallet-outline", desc: "Invoices, payments & outstanding", route: "/owner/billing" },
  { key: "incidents", label: "Incidents / SOS", icon: "warning-outline", desc: "Driver emergencies & alerts", route: "/owner/incidents" },
  { key: "fleet", label: "Fleet", icon: "bus-outline", desc: "Transit mixers & status" },
  { key: "stock", label: "Stock", icon: "cube-outline", desc: "Cement, aggregates, diesel" },
];

export default function OwnerOperations() {
  const { colors } = useTheme();
  const toast = useToast();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <View style={styles.titleRow}>
        <AppText variant="title">Operations</AppText>
        <AppText variant="caption">Plant production, dispatch, fleet & stock</AppText>
      </View>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.sm }} showsVerticalScrollIndicator={false}>
        {SECTIONS.map((s: any) => (
          <Pressable
            key={s.key}
            testID={`ops-${s.key}`}
            onPress={() => (s.route ? router.push(s.route) : toast(`${s.label} arrives in the next phases`, "info"))}
            style={[styles.row, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
          >
            <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name={s.icon} size={20} color={colors.onBrandSoft} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{s.label}</AppText>
              <AppText variant="caption">{s.desc}</AppText>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  titleRow: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, gap: 2 },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  icon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});

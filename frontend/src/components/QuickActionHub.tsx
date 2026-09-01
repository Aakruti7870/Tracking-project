import React from "react";
import { Modal, Pressable, StyleSheet, View } from "react-native";
import { BlurView } from "expo-blur";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { AppText } from "@/src/components/ui/AppText";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";
import type { TabDef } from "@/src/components/GlassTabBar";

type Props = {
  visible: boolean;
  onClose: () => void;
  tabs: TabDef[];
  role?: string | null;
  navigation: any;
};

const ROLE_LABELS: Record<string, string> = {
  customer: "Customer",
  driver: "Driver",
  plant_owner: "Plant Owner",
  admin: "Admin",
  dispatcher: "Dispatcher",
  operator: "Operator",
  supervisor: "Supervisor",
  accountant: "Accounts",
  quality_engineer: "Quality",
  fleet_manager: "Fleet",
  store_manager: "Store",
};

export function QuickActionHub({ visible, onClose, tabs, role, navigation }: Props) {
  const { colors, scheme } = useTheme();
  const roleLabel = ROLE_LABELS[role || ""] || "Quick";

  const runAction = (tab: TabDef) => {
    void Haptics.selectionAsync();
    onClose();
    navigation.navigate(tab.name);
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.overlay}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close quick actions"
        />
        <BlurView
          intensity={scheme === "dark" ? 68 : 88}
          tint={scheme === "dark" ? "dark" : "light"}
          style={[
            styles.sheet,
            {
              backgroundColor: scheme === "dark" ? "rgba(16,18,20,0.96)" : "rgba(255,255,255,0.96)",
              borderColor: scheme === "dark" ? "rgba(255,255,255,0.10)" : "rgba(17,19,21,0.08)",
            },
          ]}
        >
          <View style={[styles.handle, { backgroundColor: colors.borderStrong }]} />
          <View style={styles.headingRow}>
            <View style={{ flex: 1, paddingRight: spacing.md }}>
              <AppText style={[styles.eyebrow, { color: colors.brand }]}>{roleLabel.toUpperCase()}</AppText>
              <AppText style={[styles.title, { color: colors.onSurface }]}>Quick Actions</AppText>
              <AppText style={[styles.subtitle, { color: colors.onSurfaceTertiary }]}>Jump to the task you need without hunting through menus.</AppText>
            </View>
            <Pressable
              onPress={onClose}
              accessibilityRole="button"
              accessibilityLabel="Close quick actions"
              hitSlop={6}
              style={({ pressed }) => [
                styles.closeButton,
                {
                  backgroundColor: pressed ? colors.brandSoft : colors.surfaceTertiary,
                  borderColor: colors.border,
                },
              ]}
            >
              <Ionicons name="close" size={20} color={colors.onSurface} />
            </Pressable>
          </View>

          <View style={styles.grid}>
            {tabs.map((tab) => (
              <Pressable
                key={tab.name}
                onPress={() => runAction(tab)}
                accessibilityRole="button"
                accessibilityLabel={`${tab.label} quick action`}
                accessibilityHint={`Open ${tab.label}`}
                style={({ pressed }) => [
                  styles.action,
                  {
                    backgroundColor: pressed ? colors.brandSoft : colors.surfaceSecondary,
                    borderColor: pressed ? colors.brand + "4A" : colors.border,
                    transform: [{ scale: pressed ? 0.985 : 1 }],
                  },
                ]}
              >
                <View style={[styles.actionIcon, { backgroundColor: colors.brandSoft, borderColor: colors.brand + "24" }]}> 
                  <Ionicons name={tab.active} size={23} color={colors.brand} />
                </View>
                <View style={styles.actionCopy}>
                  <AppText style={[styles.actionLabel, { color: colors.onSurface }]}>{tab.label}</AppText>
                  <Ionicons name="arrow-forward" size={16} color={colors.onSurfaceTertiary} />
                </View>
              </Pressable>
            ))}
          </View>
        </BlurView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.46)",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  sheet: {
    borderRadius: radius.xl,
    borderWidth: 1,
    overflow: "hidden",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.24,
    shadowRadius: 30,
    elevation: 20,
  },
  handle: {
    alignSelf: "center",
    width: 42,
    height: 4,
    borderRadius: 999,
    marginBottom: spacing.md,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  eyebrow: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 1.3, marginBottom: 4 },
  title: { fontFamily: fonts.displayBold, fontSize: 24 },
  subtitle: { fontFamily: fonts.regular, fontSize: 13, lineHeight: 19, marginTop: 4 },
  closeButton: {
    width: 42,
    height: 42,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: spacing.md,
  },
  action: {
    width: "48%",
    minHeight: 112,
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: spacing.md,
    justifyContent: "space-between",
  },
  actionIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  actionCopy: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  actionLabel: { fontFamily: fonts.semibold, fontSize: 14, flex: 1 },
});

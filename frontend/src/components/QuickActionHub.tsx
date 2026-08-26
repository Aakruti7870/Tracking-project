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
  authority: "Authority",
  central_admin: "Central Admin",
};

export function QuickActionHub({ visible, onClose, tabs, role, navigation }: Props) {
  const { colors, scheme } = useTheme();
  const roleLabel = ROLE_LABELS[role || ""] || "Quick";

  const runAction = (tab: TabDef) => {
    Haptics.selectionAsync();
    onClose();
    navigation.navigate(tab.name);
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close quick actions" />
        <BlurView
          intensity={scheme === "dark" ? 70 : 85}
          tint={scheme === "dark" ? "dark" : "light"}
          style={[
            styles.sheet,
            {
              backgroundColor: scheme === "dark" ? "rgba(10,28,24,0.88)" : "rgba(246,255,251,0.90)",
              borderColor: scheme === "dark" ? "rgba(127,255,211,0.22)" : "rgba(0,105,82,0.16)",
            },
          ]}
        >
          <View style={styles.handle} />
          <View style={styles.headingRow}>
            <View>
              <AppText style={[styles.title, { color: colors.onSurface }]}>{roleLabel} Quick Actions</AppText>
              <AppText style={[styles.subtitle, { color: colors.onSurfaceTertiary }]}>Choose where you want to go</AppText>
            </View>
            <Pressable
              onPress={onClose}
              accessibilityRole="button"
              accessibilityLabel="Close quick actions"
              style={[styles.closeButton, { backgroundColor: colors.surfaceTertiary }]}
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
                style={({ pressed }) => [
                  styles.action,
                  {
                    backgroundColor: pressed
                      ? colors.brandSoft
                      : scheme === "dark"
                        ? "rgba(255,255,255,0.07)"
                        : "rgba(255,255,255,0.72)",
                    borderColor: scheme === "dark" ? "rgba(255,255,255,0.10)" : "rgba(0,105,82,0.12)",
                  },
                ]}
              >
                <View style={[styles.actionIcon, { backgroundColor: colors.brandSoft }]}> 
                  <Ionicons name={tab.active} size={23} color={colors.brand} />
                </View>
                <AppText style={[styles.actionLabel, { color: colors.onSurface }]}>{tab.label}</AppText>
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
    backgroundColor: "rgba(0,0,0,0.38)",
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
    shadowOffset: { width: 0, height: 14 },
    shadowOpacity: 0.22,
    shadowRadius: 28,
    elevation: 18,
  },
  handle: {
    alignSelf: "center",
    width: 42,
    height: 4,
    borderRadius: 999,
    backgroundColor: "rgba(127,127,127,0.45)",
    marginBottom: spacing.md,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  title: { fontFamily: fonts.displayBold, fontSize: 20 },
  subtitle: { fontFamily: fonts.regular, fontSize: 13, marginTop: 2 },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: radius.pill,
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
    minHeight: 104,
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: spacing.md,
    justifyContent: "space-between",
  },
  actionIcon: {
    width: 42,
    height: 42,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  actionLabel: { fontFamily: fonts.semibold, fontSize: 14 },
});

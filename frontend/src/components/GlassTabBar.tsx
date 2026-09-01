import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { BlurView } from "expo-blur";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { AppText } from "@/src/components/ui/AppText";
import { QuickActionHub } from "@/src/components/QuickActionHub";
import { control, fonts, radius, spacing } from "@/src/theme/tokens";

export type TabDef = {
  name: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  active: keyof typeof Ionicons.glyphMap;
};

export function GlassTabBar({ state, navigation, tabs }: any & { tabs: TabDef[] }) {
  const { colors, scheme } = useTheme();
  const { user } = useAuth();
  const insets = useSafeAreaInsets();
  const [hubOpen, setHubOpen] = useState(false);

  const visibleRoutes = state.routes.filter((route: any) => tabs.some((tab: TabDef) => tab.name === route.name));
  const leftRoutes = visibleRoutes.slice(0, 2);
  const rightRoutes = visibleRoutes.slice(2, 4);

  const renderTab = (route: any) => {
    const tab = tabs.find((definition: TabDef) => definition.name === route.name)!;
    const index = state.routes.findIndex((candidate: any) => candidate.key === route.key);
    const focused = state.index === index;

    return (
      <Pressable
        key={route.key}
        testID={`tab-${tab.label.toLowerCase()}`}
        style={({ pressed }) => [
          styles.item,
          { opacity: pressed ? 0.76 : 1, transform: [{ scale: pressed ? 0.985 : 1 }] },
        ]}
        accessibilityRole="tab"
        accessibilityState={{ selected: focused }}
        accessibilityLabel={`${tab.label} tab`}
        hitSlop={4}
        onPress={() => {
          void Haptics.selectionAsync();
          const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
          if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
        }}
      >
        <View style={[styles.activeIndicator, { backgroundColor: focused ? colors.brand : "transparent" }]} />
        <View
          style={[
            styles.iconWrap,
            focused && {
              backgroundColor: colors.brandSoft,
              borderColor: colors.brand + "38",
            },
          ]}
        >
          <Ionicons name={focused ? tab.active : tab.icon} size={22} color={focused ? colors.brand : colors.onSurfaceTertiary} />
        </View>
        <AppText
          numberOfLines={1}
          style={{
            fontFamily: focused ? fonts.semibold : fonts.medium,
            fontSize: 11,
            lineHeight: 15,
            color: focused ? colors.onSurface : colors.onSurfaceTertiary,
          }}
        >
          {tab.label}
        </AppText>
      </Pressable>
    );
  };

  return (
    <>
      <View pointerEvents="box-none" style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
        <BlurView
          intensity={scheme === "dark" ? 66 : 86}
          tint={scheme === "dark" ? "dark" : "light"}
          style={[
            styles.bar,
            {
              borderColor: colors.isDark ? "rgba(255,255,255,0.11)" : "rgba(17,19,21,0.09)",
              backgroundColor: colors.isDark ? "rgba(15,17,19,0.95)" : "rgba(255,255,255,0.94)",
              shadowColor: colors.shadow,
            },
          ]}
        >
          {leftRoutes.map(renderTab)}

          <View style={styles.centerSlot}>
            <View style={[styles.centerHalo, { backgroundColor: colors.brandSoft, borderColor: colors.brand + "2F" }]}>
              <Pressable
                testID="tab-quick-actions"
                accessibilityRole="button"
                accessibilityLabel="Open quick actions"
                accessibilityHint="Shows the fastest actions for your current role"
                onPress={() => {
                  void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  setHubOpen(true);
                }}
                style={({ pressed }) => [
                  styles.centerButton,
                  {
                    backgroundColor: pressed ? colors.brandPressed : colors.brand,
                    borderColor: colors.isDark ? colors.surfaceTertiary : colors.surfaceSecondary,
                    transform: [{ scale: pressed ? 0.93 : 1 }],
                    shadowColor: colors.brand,
                  },
                ]}
              >
                <Ionicons name="add" size={30} color={colors.onBrand} />
              </Pressable>
            </View>
            <AppText style={[styles.centerLabel, { color: colors.onSurfaceSecondary }]}>Quick</AppText>
          </View>

          {rightRoutes.map(renderTab)}
        </BlurView>
      </View>

      <QuickActionHub visible={hubOpen} onClose={() => setHubOpen(false)} tabs={tabs} role={user?.role} navigation={navigation} />
    </>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.md,
  },
  bar: {
    minHeight: 72,
    flexDirection: "row",
    alignItems: "flex-end",
    borderRadius: radius.xl,
    borderWidth: 1,
    overflow: "visible",
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    paddingHorizontal: spacing.xs,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.19,
    shadowRadius: 28,
    elevation: 16,
  },
  item: {
    flex: 1,
    minHeight: 58,
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 4,
    paddingVertical: 2,
    minWidth: 0,
  },
  activeIndicator: {
    width: 18,
    height: 3,
    borderRadius: radius.pill,
    marginBottom: 1,
  },
  iconWrap: {
    width: 46,
    height: 34,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
  },
  centerSlot: {
    width: 72,
    minHeight: 60,
    alignItems: "center",
    justifyContent: "flex-end",
    marginTop: -34,
  },
  centerHalo: {
    width: 68,
    height: 68,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  centerButton: {
    width: 60,
    height: 60,
    minWidth: control.minTouch,
    minHeight: control.minTouch,
    borderRadius: radius.pill,
    borderWidth: 4,
    alignItems: "center",
    justifyContent: "center",
    shadowOffset: { width: 0, height: 9 },
    shadowOpacity: 0.28,
    shadowRadius: 16,
    elevation: 15,
  },
  centerLabel: {
    marginTop: 4,
    fontFamily: fonts.semibold,
    fontSize: 10,
    lineHeight: 14,
  },
});

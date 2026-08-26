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
import { fonts, radius, spacing } from "@/src/theme/tokens";

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

  const visibleRoutes = state.routes.filter((r: any) => tabs.some((t: TabDef) => t.name === r.name));
  const leftRoutes = visibleRoutes.slice(0, 2);
  const rightRoutes = visibleRoutes.slice(2, 4);

  const renderTab = (route: any) => {
    const tab = tabs.find((t: TabDef) => t.name === route.name)!;
    const index = state.routes.findIndex((r: any) => r.key === route.key);
    const focused = state.index === index;

    return (
      <Pressable
        key={route.key}
        testID={`tab-${tab.label.toLowerCase()}`}
        style={styles.item}
        accessibilityRole="button"
        accessibilityState={{ selected: focused }}
        accessibilityLabel={`${tab.label} tab`}
        onPress={() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
          if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
        }}
      >
        <View style={[styles.iconWrap, focused && { backgroundColor: colors.brandSoft }]}> 
          <Ionicons
            name={focused ? tab.active : tab.icon}
            size={22}
            color={focused ? colors.brand : colors.onSurfaceTertiary}
          />
        </View>
        <AppText
          style={{
            fontFamily: focused ? fonts.semibold : fonts.medium,
            fontSize: 11,
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
          intensity={scheme === "dark" ? 58 : 76}
          tint={scheme === "dark" ? "dark" : "light"}
          style={[
            styles.bar,
            {
              borderColor: scheme === "dark" ? "rgba(127,255,211,0.18)" : "rgba(0,105,82,0.14)",
              backgroundColor: scheme === "dark" ? "rgba(8,28,24,0.90)" : "rgba(248,255,252,0.90)",
            },
          ]}
        >
          {leftRoutes.map(renderTab)}

          <View style={styles.centerSlot}>
            <Pressable
              testID="tab-quick-actions"
              accessibilityRole="button"
              accessibilityLabel="Open quick actions"
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                setHubOpen(true);
              }}
              style={({ pressed }) => [
                styles.centerButton,
                {
                  backgroundColor: pressed ? colors.brandSoft : colors.brand,
                  borderColor: scheme === "dark" ? "rgba(255,255,255,0.22)" : "rgba(255,255,255,0.86)",
                },
              ]}
            >
              <Ionicons name="add" size={30} color={colors.onBrand} />
            </Pressable>
            <AppText style={[styles.centerLabel, { color: colors.onSurfaceTertiary }]}>Quick</AppText>
          </View>

          {rightRoutes.map(renderTab)}
        </BlurView>
      </View>

      <QuickActionHub
        visible={hubOpen}
        onClose={() => setHubOpen(false)}
        tabs={tabs}
        role={user?.role}
        navigation={navigation}
      />
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
    flexDirection: "row",
    alignItems: "flex-end",
    borderRadius: radius.xl,
    borderWidth: 1,
    overflow: "visible",
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    paddingHorizontal: spacing.xs,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 16,
  },
  item: {
    flex: 1,
    alignItems: "center",
    gap: 4,
    paddingVertical: 2,
    minWidth: 0,
  },
  iconWrap: {
    width: 40,
    height: 32,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  centerSlot: {
    width: 66,
    alignItems: "center",
    justifyContent: "flex-end",
    marginTop: -28,
  },
  centerButton: {
    width: 58,
    height: 58,
    borderRadius: radius.pill,
    borderWidth: 3,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.24,
    shadowRadius: 12,
    elevation: 14,
  },
  centerLabel: {
    marginTop: 4,
    fontFamily: fonts.medium,
    fontSize: 10,
  },
});

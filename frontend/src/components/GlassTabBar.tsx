import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { BlurView } from "expo-blur";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";

import { useTheme } from "@/src/theme/ThemeProvider";
import { AppText } from "@/src/components/ui/AppText";
import { fonts, radius, spacing } from "@/src/theme/tokens";

export type TabDef = {
  name: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  active: keyof typeof Ionicons.glyphMap;
};

export function GlassTabBar({ state, navigation, tabs }: any & { tabs: TabDef[] }) {
  const { colors, scheme } = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
      <BlurView
        intensity={scheme === "dark" ? 40 : 60}
        tint={scheme === "dark" ? "dark" : "light"}
        style={[styles.bar, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary + "E6" }]}
      >
        {state.routes
          .filter((r: any) => tabs.some((t: TabDef) => t.name === r.name))
          .map((route: any) => {
            const tab = tabs.find((t: TabDef) => t.name === route.name)!;
            const index = state.routes.findIndex((r: any) => r.key === route.key);
            const focused = state.index === index;
            return (
              <Pressable
                key={route.key}
                testID={`tab-${tab.label.toLowerCase()}`}
                style={styles.item}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
                  if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
                }}
              >
                <View style={[styles.iconWrap, focused && { backgroundColor: colors.brand }]}>
                  <Ionicons name={focused ? tab.active : tab.icon} size={22} color={focused ? colors.onBrand : colors.onSurfaceTertiary} />
                </View>
                <AppText style={{ fontFamily: focused ? fonts.semibold : fonts.medium, fontSize: 11, color: focused ? colors.onSurface : colors.onSurfaceTertiary }}>
                  {tab.label}
                </AppText>
              </Pressable>
            );
          })}
      </BlurView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: spacing.md },
  bar: { flexDirection: "row", borderRadius: radius.lg, borderWidth: 1, overflow: "hidden", paddingVertical: spacing.sm, paddingHorizontal: spacing.xs },
  item: { flex: 1, alignItems: "center", gap: 4, paddingVertical: 2 },
  iconWrap: { width: 40, height: 32, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
});

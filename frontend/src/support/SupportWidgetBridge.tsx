import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { usePathname, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";

/**
 * Global support entry point with a strict authentication boundary:
 * - before login: static login/account guidance only, no customer APIs;
 * - after login: only authenticated customers can open the full Support Agent.
 */
export function SupportWidgetBridge() {
  const { hydrating, token, user } = useAuth();
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const [publicHelpOpen, setPublicHelpOpen] = useState(false);

  useEffect(() => {
    setPublicHelpOpen(false);
  }, [pathname, token, user?.role]);

  const showPublicLoginHelp = !hydrating && !token && !user && pathname === "/login";
  const showCustomerSupport = !hydrating && Boolean(token) && user?.role === "customer" && pathname !== "/support";

  if (!showPublicLoginHelp && !showCustomerSupport) return null;

  if (showCustomerSupport) {
    return (
      <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
        <View style={[styles.customerAnchor, { bottom: Math.max(insets.bottom + 92, 104) }]}>
          <Pressable
            testID="customer-support-widget"
            accessibilityRole="button"
            accessibilityLabel="Open TrackMyRMC Support"
            accessibilityHint="Opens authenticated customer support, support cases, tracking help and assisted ordering"
            onPress={() => router.push("/support" as never)}
            style={({ pressed }) => [
              styles.customerButton,
              {
                backgroundColor: colors.brand,
                borderColor: colors.brand,
                opacity: pressed ? 0.84 : 1,
              },
            ]}
          >
            <Ionicons name="chatbubble-ellipses-outline" size={22} color={colors.onBrand} />
            <AppText style={[styles.customerLabel, { color: colors.onBrand }]}>Support</AppText>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
      <View style={[styles.publicAnchor, { bottom: Math.max(insets.bottom + 24, 32) }]}>
        {publicHelpOpen ? (
          <View
            testID="login-help-panel"
            accessibilityLiveRegion="polite"
            style={[styles.publicPanel, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
          >
            <View style={styles.panelHeader}>
              <View style={{ flex: 1, gap: 2 }}>
                <AppText variant="heading">Login help</AppText>
                <AppText variant="caption">Safe help before sign-in. No customer, order, tracking or payment data is available here.</AppText>
              </View>
              <Pressable
                testID="login-help-close"
                accessibilityRole="button"
                accessibilityLabel="Close login help"
                hitSlop={10}
                onPress={() => setPublicHelpOpen(false)}
                style={[styles.closeButton, { borderColor: colors.border }]}
              >
                <Ionicons name="close" size={18} color={colors.onSurface} />
              </Pressable>
            </View>

            <View style={styles.guidanceBlock}>
              <View style={styles.guidanceRow}>
                <Ionicons name="phone-portrait-outline" size={18} color={colors.brand} />
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText variant="label">User login</AppText>
                  <AppText variant="caption">Use your registered 10-digit mobile number and the 6-digit SMS OTP.</AppText>
                </View>
              </View>
              <View style={styles.guidanceRow}>
                <Ionicons name="business-outline" size={18} color={colors.brand} />
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText variant="label">Plant Staff login</AppText>
                  <AppText variant="caption">Use your approved work email. Your account may require email OTP, Authenticator or Passkey verification.</AppText>
                </View>
              </View>
              <View style={styles.guidanceRow}>
                <Ionicons name="shield-checkmark-outline" size={18} color={colors.brand} />
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText variant="label">Keep credentials private</AppText>
                  <AppText variant="caption">Never share an OTP, password, passkey, recovery code, PIN or payment credential.</AppText>
                </View>
              </View>
            </View>

            <Pressable
              testID="login-help-onboarding"
              accessibilityRole="button"
              onPress={() => router.push("/plant-onboarding" as never)}
              style={({ pressed }) => [styles.actionRow, { borderColor: colors.border, opacity: pressed ? 0.78 : 1 }]}
            >
              <Ionicons name="business-outline" size={18} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText variant="label">Plant email not approved?</AppText>
                <AppText variant="caption">Open the verified onboarding request.</AppText>
              </View>
              <Ionicons name="chevron-forward" size={17} color={colors.onSurfaceTertiary} />
            </Pressable>

            <Pressable
              testID="login-help-delete-account"
              accessibilityRole="button"
              onPress={() => router.push("/account-deletion-public" as never)}
              style={({ pressed }) => [styles.actionRow, { borderColor: colors.border, opacity: pressed ? 0.78 : 1 }]}
            >
              <Ionicons name="person-remove-outline" size={18} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText variant="label">Delete Account</AppText>
                <AppText variant="caption">Start the public ownership-verification flow.</AppText>
              </View>
              <Ionicons name="chevron-forward" size={17} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>
        ) : null}

        <Pressable
          testID="login-help-widget"
          accessibilityRole="button"
          accessibilityLabel="Need help logging in?"
          accessibilityState={{ expanded: publicHelpOpen }}
          onPress={() => setPublicHelpOpen((value) => !value)}
          style={({ pressed }) => [
            styles.publicButton,
            {
              backgroundColor: colors.surfaceSecondary,
              borderColor: colors.border,
              opacity: pressed ? 0.84 : 1,
            },
          ]}
        >
          <Ionicons name="help-circle-outline" size={21} color={colors.brand} />
          <AppText style={[styles.publicButtonLabel, { color: colors.onSurface }]}>Need help?</AppText>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  customerAnchor: { position: "absolute", right: spacing.lg },
  customerButton: {
    minHeight: 52,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 8,
  },
  customerLabel: { fontFamily: fonts.semibold, fontSize: 14 },
  publicAnchor: { position: "absolute", right: spacing.md, alignItems: "flex-end", gap: spacing.sm },
  publicPanel: {
    width: 310,
    maxWidth: "92%",
    borderWidth: 1,
    borderRadius: radius.xl,
    padding: spacing.md,
    gap: spacing.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 22,
    elevation: 10,
  },
  panelHeader: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  closeButton: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  guidanceBlock: { gap: spacing.md },
  guidanceRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  actionRow: {
    minHeight: 58,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  publicButton: {
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.14,
    shadowRadius: 12,
    elevation: 6,
  },
  publicButtonLabel: { fontFamily: fonts.semibold, fontSize: 13 },
});

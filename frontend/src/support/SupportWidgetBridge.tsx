import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { usePathname, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";

const CUSTOMER_WIDGET_PATHS = new Set(["/customer", "/customer/orders", "/customer/plants", "/customer/more"]);

/**
 * Global support entry point with a strict authentication boundary:
 * - before login: static login/account guidance only, no customer APIs;
 * - after login: authenticated customers get a compact Support Agent card on
 *   the four tab-shell screens that already reserve bottom-navigation space.
 *
 * The floating control uses the bundled Ionicons font rather than a raster
 * image so it renders consistently without image decoding/cropping issues.
 * All overlay wrappers use box-none so only visible support controls receive touches.
 */
export function SupportWidgetBridge() {
  const { hydrating, token, user } = useAuth();
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { height: viewportHeight, width: viewportWidth } = useWindowDimensions();
  const [publicHelpOpen, setPublicHelpOpen] = useState(false);
  const [customerHelpOpen, setCustomerHelpOpen] = useState(false);

  useEffect(() => {
    setPublicHelpOpen(false);
    setCustomerHelpOpen(false);
  }, [pathname, token, user?.role]);

  const normalizedPath = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const showPublicLoginHelp = !hydrating && !token && !user && normalizedPath === "/login";
  const showCustomerSupport =
    !hydrating && Boolean(token) && user?.role === "customer" && CUSTOMER_WIDGET_PATHS.has(normalizedPath);

  if (!showPublicLoginHelp && !showCustomerSupport) return null;

  if (showCustomerSupport) {
    const anchorBottom = Math.max(insets.bottom + 104, 120);
    const panelWidth = Math.min(360, Math.max(0, viewportWidth - 24));
    const panelMaxHeight = Math.min(520, Math.max(160, viewportHeight - anchorBottom - 76));

    return (
      <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
        <View
          pointerEvents="box-none"
          style={[styles.customerAnchor, { bottom: anchorBottom }]}
        >
          {customerHelpOpen ? (
            <ScrollView
              testID="customer-support-panel"
              accessibilityLiveRegion="polite"
              style={[styles.supportPanel, { width: panelWidth, maxHeight: panelMaxHeight, backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
              contentContainerStyle={styles.panelContent}
              nestedScrollEnabled
              showsVerticalScrollIndicator={panelMaxHeight < 520}
            >
              <View style={styles.panelHeader}>
                <View style={[styles.panelIcon, { backgroundColor: colors.brandSoft, borderColor: colors.brand + "44" }]}>
                  <Ionicons name="chatbubbles-outline" size={24} color={colors.brand} />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText variant="heading">TrackMyRMC Support</AppText>
                  <AppText variant="caption">Quick help from this screen. Open the full support center only when you need detailed issue steps or your case history.</AppText>
                </View>
                <Pressable
                  testID="customer-support-close"
                  accessibilityRole="button"
                  accessibilityLabel="Close TrackMyRMC Support"
                  hitSlop={10}
                  onPress={() => setCustomerHelpOpen(false)}
                  style={[styles.closeButton, { borderColor: colors.border }]}
                >
                  <Ionicons name="close" size={18} color={colors.onSurface} />
                </Pressable>
              </View>

              <Pressable
                testID="customer-support-place-order"
                accessibilityRole="button"
                onPress={() => router.push("/new-order?assistant=1" as never)}
                style={({ pressed }) => [styles.actionRow, { borderColor: colors.border, opacity: pressed ? 0.78 : 1 }]}
              >
                <Ionicons name="cart-outline" size={19} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <AppText variant="label">Place Order with Agent</AppText>
                  <AppText variant="caption">Prepare an assisted order, then confirm it yourself.</AppText>
                </View>
                <Ionicons name="chevron-forward" size={17} color={colors.onSurfaceTertiary} />
              </Pressable>

              <Pressable
                testID="customer-support-track-delivery"
                accessibilityRole="button"
                onPress={() => router.push("/customer/orders" as never)}
                style={({ pressed }) => [styles.actionRow, { borderColor: colors.border, opacity: pressed ? 0.78 : 1 }]}
              >
                <Ionicons name="navigate-outline" size={19} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <AppText variant="label">Track Delivery</AppText>
                  <AppText variant="caption">Open your orders and live delivery tracking.</AppText>
                </View>
                <Ionicons name="chevron-forward" size={17} color={colors.onSurfaceTertiary} />
              </Pressable>

              <Pressable
                testID="customer-support-open-center"
                accessibilityRole="button"
                onPress={() => router.push("/support" as never)}
                style={({ pressed }) => [styles.actionRow, { borderColor: colors.border, opacity: pressed ? 0.78 : 1 }]}
              >
                <Ionicons name="help-circle-outline" size={19} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <AppText variant="label">All Issues & My Support Cases</AppText>
                  <AppText variant="caption">Login, KYC, order, payment, account, onboarding and other support.</AppText>
                </View>
                <Ionicons name="chevron-forward" size={17} color={colors.onSurfaceTertiary} />
              </Pressable>
            </ScrollView>
          ) : null}

          <View pointerEvents="box-none" style={styles.customerLauncher}>
            <Pressable
              testID="customer-support-widget"
              accessibilityRole="button"
              accessibilityLabel="Open TrackMyRMC Support"
              accessibilityHint="Expands a compact support card without leaving this screen"
              accessibilityState={{ expanded: customerHelpOpen }}
              onPress={() => setCustomerHelpOpen((value) => !value)}
              style={({ pressed }) => [
                styles.supportButton,
                {
                  backgroundColor: colors.surfaceSecondary,
                  borderColor: colors.brand,
                  opacity: pressed ? 0.84 : 1,
                },
              ]}
            >
              <Ionicons name="chatbubbles-outline" size={30} color={colors.brand} />
            </Pressable>
            <View pointerEvents="none" style={[styles.customerBadge, { backgroundColor: colors.brand }]}> 
              <AppText style={[styles.badgeText, { color: colors.onBrand }]}>Support</AppText>
            </View>
          </View>
        </View>
      </View>
    );
  }

  const anchorTop = Math.max(insets.top + spacing.sm, 16);
  const panelWidth = Math.min(360, Math.max(0, viewportWidth - 24));
  const panelMaxHeight = Math.min(520, Math.max(160, viewportHeight - anchorTop - 76));

  return (
    <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
      <View
        pointerEvents="box-none"
        style={[styles.publicAnchor, { top: anchorTop }]}
      >
        {publicHelpOpen ? (
          <ScrollView
            testID="login-help-panel"
            accessibilityLiveRegion="polite"
            style={[styles.supportPanel, { width: panelWidth, maxHeight: panelMaxHeight, backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
            contentContainerStyle={styles.panelContent}
            nestedScrollEnabled
            showsVerticalScrollIndicator={panelMaxHeight < 520}
          >
            <View style={styles.panelHeader}>
              <View style={[styles.panelIcon, { backgroundColor: colors.brandSoft, borderColor: colors.brand + "44" }]}>
                <Ionicons name="chatbubbles-outline" size={24} color={colors.brand} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <AppText variant="heading">Need help logging in?</AppText>
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
          </ScrollView>
        ) : null}

        <Pressable
          testID="login-help-widget"
          accessibilityRole="button"
          accessibilityLabel="Need help logging in?"
          accessibilityHint="Opens safe login help without accessing customer, order, tracking or payment data"
          accessibilityState={{ expanded: publicHelpOpen }}
          onPress={() => setPublicHelpOpen((value) => !value)}
          style={({ pressed }) => [
            styles.supportButton,
            {
              backgroundColor: colors.surfaceSecondary,
              borderColor: colors.brand,
              opacity: pressed ? 0.84 : 1,
            },
          ]}
        >
          <Ionicons name="chatbubbles-outline" size={30} color={colors.brand} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  customerAnchor: {
    position: "absolute",
    right: spacing.md,
    alignItems: "flex-end",
    gap: spacing.sm,
  },
  customerLauncher: { alignItems: "center" },
  publicAnchor: {
    position: "absolute",
    right: spacing.sm,
    alignItems: "flex-end",
    gap: spacing.sm,
    flexDirection: "column-reverse",
  },
  supportButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.16,
    shadowRadius: 12,
    elevation: 7,
  },
  customerBadge: {
    minHeight: 24,
    minWidth: 54,
    marginTop: -5,
    paddingHorizontal: 8,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { fontFamily: fonts.semibold, fontSize: 10 },
  supportPanel: {
    borderWidth: 1,
    borderRadius: radius.xl,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 22,
    elevation: 10,
  },
  panelContent: {
    padding: spacing.md,
    gap: spacing.md,
  },
  panelHeader: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  panelIcon: { width: 46, height: 46, borderRadius: 23, borderWidth: 1, alignItems: "center", justifyContent: "center" },
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
});

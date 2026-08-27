import React, { useEffect, useState } from "react";
import { Modal, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, spacing } from "@/src/theme/tokens";

// Imperative bridge so the non-React location module (tripTracking.ts) can show
// the Google Play "prominent disclosure" BEFORE the OS background-location
// permission prompt. Play policy requires an in-app disclosure that: names the
// data collected, explains the purpose, uses "in the background / when the app
// is closed" phrasing, requires affirmative action, and does not auto-dismiss.
type Resolver = (granted: boolean) => void;
let pendingResolver: Resolver | null = null;
let showFn: (() => void) | null = null;

export function requestBackgroundLocationConsent(): Promise<boolean> {
  return new Promise((resolve) => {
    if (!showFn) {
      // Provider not mounted (e.g. web) -> no explicit consent captured.
      resolve(false);
      return;
    }
    pendingResolver = resolve;
    showFn();
  });
}

const DISCLOSURE_POINTS: { icon: React.ComponentProps<typeof Ionicons>["name"]; text: string }[] = [
  {
    icon: "navigate-circle-outline",
    text:
      "TrackMyRMC collects this device's location to share live mixer tracking and delivery ETA with your plant and customer during an active delivery trip.",
  },
  {
    icon: "moon-outline",
    text:
      "Location is collected in the background — even when the app is closed or not in use — so tracking continues if you lock your phone or switch apps while driving.",
  },
  {
    icon: "notifications-outline",
    text:
      "While tracking runs, an ongoing notification is shown. Location is only collected while a trip is active and stops automatically when the trip ends.",
  },
];

export function BackgroundLocationConsentProvider() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    showFn = () => setVisible(true);
    return () => {
      showFn = null;
    };
  }, []);

  const settle = (granted: boolean) => {
    setVisible(false);
    const resolve = pendingResolver;
    pendingResolver = null;
    resolve?.(granted);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={() => settle(false)}
    >
      <View style={styles.backdrop}>
        <View
          style={[
            styles.sheet,
            {
              backgroundColor: colors.surface,
              borderColor: colors.border,
              paddingBottom: insets.bottom + spacing.lg,
            },
          ]}
        >
          <View style={[styles.iconWrap, { backgroundColor: colors.brand + "1A" }]}>
            <Ionicons name="location-outline" size={30} color={colors.brand} />
          </View>
          <AppText variant="heading" center>
            Allow background location?
          </AppText>
          <AppText variant="bodyMuted" center style={styles.intro}>
            Before Android asks for permission, here is exactly how TrackMyRMC uses your location.
          </AppText>

          <View style={styles.points}>
            {DISCLOSURE_POINTS.map((point) => (
              <View key={point.text} style={styles.pointRow}>
                <Ionicons name={point.icon} size={20} color={colors.brand} style={styles.pointIcon} />
                <AppText variant="body" style={styles.pointText}>
                  {point.text}
                </AppText>
              </View>
            ))}
          </View>

          <View style={styles.actions}>
            <Button
              testID="bg-location-allow"
              label="Allow background tracking"
              onPress={() => settle(true)}
              icon={<Ionicons name="shield-checkmark-outline" size={18} color={colors.onBrand} />}
            />
            <Button
              testID="bg-location-deny"
              label="Not now"
              variant="ghost"
              onPress={() => settle(false)}
            />
          </View>
          <AppText variant="caption" center style={styles.footer}>
            You can change this anytime in your device Settings. Declining keeps tracking on only while
            the app is open.
          </AppText>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    justifyContent: "flex-end",
  },
  sheet: {
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    gap: spacing.md,
  },
  iconWrap: {
    alignSelf: "center",
    width: 60,
    height: 60,
    borderRadius: 30,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  intro: {
    marginTop: -spacing.xs,
  },
  points: {
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  pointRow: {
    flexDirection: "row",
    gap: spacing.md,
    alignItems: "flex-start",
  },
  pointIcon: {
    marginTop: 2,
  },
  pointText: {
    flex: 1,
    lineHeight: fontSize.base * 1.4,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  footer: {
    marginTop: spacing.xs,
    fontFamily: fonts.regular,
  },
});

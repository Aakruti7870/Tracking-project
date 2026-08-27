import React, { useEffect, useState } from "react";
import { Linking, Modal, Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, spacing } from "@/src/theme/tokens";

// Imperative bridge so the non-React location module (tripTracking.ts) can show
// the Google Play "Prominent Disclosure and Consent" screen BEFORE the OS
// permission prompts. Play policy (Location Permissions -> Prominent
// Disclosure) requires that the in-app disclosure:
//   - Clearly names the app that is requesting access.
//   - Explicitly names the data ("precise location, latitude and longitude")
//     and features it powers ("live delivery tracking, ETA").
//   - Uses "in the background, even when the app is closed or not in use"
//     phrasing for background access.
//   - Requires affirmative user action (a real button, not just dismiss).
//   - Is shown BEFORE requesting the runtime OS permission.
//   - Links to the Privacy Policy.
// If the driver declines, tripTracking.ts falls back to foreground-only.
type Resolver = (granted: boolean) => void;
type Scope = "foreground" | "background";
type Payload = { scope: Scope; resolver: Resolver };

let showFn: ((payload: Payload) => void) | null = null;

function requestConsent(scope: Scope): Promise<boolean> {
  return new Promise((resolve) => {
    if (!showFn) {
      // Provider not mounted (e.g. web / unit test) -> no explicit consent captured.
      resolve(false);
      return;
    }
    showFn({ scope, resolver: resolve });
  });
}

export function requestBackgroundLocationConsent(): Promise<boolean> {
  return requestConsent("background");
}

export function requestForegroundLocationConsent(): Promise<boolean> {
  return requestConsent("foreground");
}

const PRIVACY_URL = "https://trackmyrmc.com/privacy";

type Point = { icon: React.ComponentProps<typeof Ionicons>["name"]; text: string };

const FOREGROUND_POINTS: Point[] = [
  {
    icon: "navigate-circle-outline",
    text:
      "TrackMyRMC will collect this device's precise location (latitude and longitude) so your plant and customer can see where the mixer is during an active delivery trip.",
  },
  {
    icon: "time-outline",
    text:
      "Location is collected only while the app is open and a delivery trip is active. It stops automatically when the trip ends or when you sign out.",
  },
  {
    icon: "shield-checkmark-outline",
    text:
      "Location data is sent to the TrackMyRMC servers of your plant to power live tracking and ETA. It is not sold to advertisers.",
  },
];

const BACKGROUND_POINTS: Point[] = [
  {
    icon: "navigate-circle-outline",
    text:
      "TrackMyRMC needs precise location (latitude and longitude) so your plant and customer can see live mixer position and ETA for the active delivery.",
  },
  {
    icon: "moon-outline",
    text:
      "This location is collected in the background — even when the app is closed or not in use — so tracking keeps working after you lock the phone or switch to another app while driving.",
  },
  {
    icon: "notifications-outline",
    text:
      "While a trip is active, an ongoing Android notification shows that tracking is running. Background location is only collected during that trip and stops automatically at Proof of Delivery.",
  },
  {
    icon: "shield-checkmark-outline",
    text:
      "Location is used only for delivery tracking, dispatch and ETA between the driver, plant and customer. It is never sold to advertisers.",
  },
];

export function BackgroundLocationConsentProvider() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [state, setState] = useState<{ visible: boolean; scope: Scope; resolver: Resolver | null }>({
    visible: false,
    scope: "background",
    resolver: null,
  });

  useEffect(() => {
    showFn = ({ scope, resolver }) => {
      setState({ visible: true, scope, resolver });
    };
    return () => {
      showFn = null;
    };
  }, []);

  const settle = (granted: boolean) => {
    const { resolver } = state;
    setState({ visible: false, scope: state.scope, resolver: null });
    resolver?.(granted);
  };

  const isBackground = state.scope === "background";
  const points = isBackground ? BACKGROUND_POINTS : FOREGROUND_POINTS;
  const title = isBackground
    ? "Allow background location for delivery tracking?"
    : "Allow TrackMyRMC to use location for delivery tracking?";
  const intro = isBackground
    ? "Before Android asks for permission, here is exactly what TrackMyRMC does with your location."
    : "Before Android asks for permission, here is exactly what TrackMyRMC does with your location.";
  const allowLabel = isBackground ? "Allow background tracking" : "Allow location for delivery";
  const declineFooter = isBackground
    ? "You can change this anytime in Android Settings. If you decline, live tracking still works while the app is open."
    : "You can change this anytime in Android Settings. Without location, delivery tracking and ETA will not work.";

  return (
    <Modal
      visible={state.visible}
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
            <Ionicons
              name={isBackground ? "location-outline" : "navigate-outline"}
              size={30}
              color={colors.brand}
            />
          </View>
          <AppText variant="heading" center>
            {title}
          </AppText>
          <AppText variant="bodyMuted" center style={styles.intro}>
            {intro}
          </AppText>

          <View style={styles.points}>
            {points.map((point) => (
              <View key={point.text} style={styles.pointRow}>
                <Ionicons
                  name={point.icon}
                  size={20}
                  color={colors.brand}
                  style={styles.pointIcon}
                />
                <AppText variant="body" style={styles.pointText}>
                  {point.text}
                </AppText>
              </View>
            ))}
          </View>

          <Pressable
            accessibilityRole="link"
            onPress={() => {
              void Linking.openURL(PRIVACY_URL);
            }}
            style={styles.privacyLink}
          >
            <Ionicons name="open-outline" size={14} color={colors.brand} />
            <AppText variant="caption" color={colors.brand}>
              Read the TrackMyRMC Privacy Policy
            </AppText>
          </Pressable>

          <View style={styles.actions}>
            <Button
              testID="bg-location-allow"
              label={allowLabel}
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
            {declineFooter}
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
  privacyLink: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    marginTop: spacing.xs,
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

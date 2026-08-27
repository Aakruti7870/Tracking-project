import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { PlayReviewRole } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { roleRouteFor } from "@/src/auth/roleRoutes";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { useTheme } from "@/src/theme/ThemeProvider";
import { radius, spacing } from "@/src/theme/tokens";

const ROLES: { role: PlayReviewRole; label: string; description: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { role: "customer", label: "User / Customer", description: "Customer ordering and delivery experience", icon: "person-outline" },
  { role: "plant_owner", label: "Plant Owner", description: "Plant operations and owner dashboard", icon: "business-outline" },
  { role: "authority", label: "Authority", description: "Verification and authority workflow", icon: "shield-checkmark-outline" },
  { role: "driver", label: "Driver", description: "Trip, live delivery tracking and POD", icon: "car-outline" },
];

export default function ReviewAccess() {
  const { colors, scheme } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { verifyPlayReview } = useAuth();
  const [role, setRole] = useState<PlayReviewRole>("customer");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async () => {
    setError(null);
    if (code.trim().length < 10) {
      setError("Enter the reusable review access code supplied in Google Play Console.");
      return;
    }
    setBusy(true);
    try {
      const me = await verifyPlayReview(role, code.trim());
      router.replace(roleRouteFor(me.role) as any);
    } catch (e: any) {
      setError(e.detail || "Reviewer access failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable onPress={() => router.back()} style={[styles.back, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <AppText variant="title">Google Play Review Access</AppText>
          <AppText variant="caption">Reusable reviewer login — no OTP or Google account required</AppText>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg, paddingBottom: 60 }}>
        <Card style={{ gap: spacing.sm }}>
          <AppText variant="heading">Choose a review role</AppText>
          <AppText variant="bodyMuted">
            These isolated accounts contain review-only demo data and are available only with the access code supplied to Google Play reviewers.
          </AppText>
        </Card>

        <View style={{ gap: spacing.sm }}>
          {ROLES.map((item) => {
            const selected = role === item.role;
            return (
              <Pressable
                key={item.role}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
                onPress={() => {
                  setRole(item.role);
                  setError(null);
                }}
                style={[
                  styles.roleCard,
                  {
                    borderColor: selected ? colors.brand : colors.border,
                    backgroundColor: selected ? colors.brandSoft : colors.surfaceSecondary,
                  },
                ]}
              >
                <Ionicons name={item.icon} size={22} color={selected ? colors.onBrandSoft : colors.brand} />
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText variant="label">{item.label}</AppText>
                  <AppText variant="caption">{item.description}</AppText>
                </View>
                <Ionicons
                  name={selected ? "radio-button-on" : "radio-button-off"}
                  size={20}
                  color={selected ? colors.brand : colors.onSurfaceTertiary}
                />
              </Pressable>
            );
          })}
        </View>

        <Input
          label="Review access code"
          value={code}
          onChangeText={(value) => {
            setCode(value);
            setError(null);
          }}
          placeholder="Code from Play Console app access"
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          error={error || undefined}
        />
        <Button label={`Open ${ROLES.find((item) => item.role === role)?.label}`} onPress={login} loading={busy} />

        <AppText variant="caption" center>
          Review access is restricted to Google Play testing. Normal users should use User Login or Plant User Login.
        </AppText>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  back: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  roleCard: {
    minHeight: 72,
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
});
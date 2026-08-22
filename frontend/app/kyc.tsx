import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Button } from "@/src/components/ui/Button";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const STATE_META: Record<string, { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; tone: "success" | "warning" | "error" | "info" }> = {
  VERIFIED: { icon: "shield-checkmark", title: "KYC Verified", body: "You can place orders using the app.", tone: "success" },
  PENDING: { icon: "hourglass-outline", title: "Verification in progress", body: "We're reviewing your submitted documents.", tone: "warning" },
  REJECTED: { icon: "close-circle", title: "Verification rejected", body: "Something didn't match. Please retry.", tone: "error" },
  REQUIRES_REVERIFICATION: { icon: "refresh", title: "Re-verification required", body: "Please re-submit your KYC to continue.", tone: "warning" },
  NOT_STARTED: { icon: "id-card-outline", title: "Verify your identity", body: "Complete KYC to unlock live concrete ordering.", tone: "info" },
};

const STEPS = [
  "Verify your identity via DigiLocker / approved KYC",
  "We confirm your details against government records",
  "Get verified and start ordering instantly",
];

export default function KycScreen() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { token, refreshMe } = useAuth();
  const { data, loading, error, reload } = useGet<{ status: string }>("/customer/kyc");
  const [submitting, setSubmitting] = useState(false);

  const status = data?.status || "NOT_STARTED";
  const meta = STATE_META[status] || STATE_META.NOT_STARTED;
  const tone = { success: colors.success, warning: colors.warning, error: colors.error, info: colors.brand }[meta.tone];

  const startKyc = async () => {
    if (!token) return;
    setSubmitting(true);
    try {
      await apiPost("/customer/kyc/start", token);
      toast("KYC submitted for review", "success");
      await refreshMe();
      reload();
    } catch (e: any) {
      toast(e.detail || "Could not start KYC", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const ctaLabel = status === "NOT_STARTED" ? "Start KYC" : status === "PENDING" ? "Refresh Status" : status === "VERIFIED" ? "Back to Home" : "Retry KYC";
  const onCta = status === "VERIFIED" ? () => router.back() : status === "PENDING" ? () => reload() : startKyc;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="kyc-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">KYC Verification</AppText>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }} showsVerticalScrollIndicator={false}>
        {loading && !data ? (
          <Skeleton height={200} style={{ borderRadius: radius.lg }} />
        ) : (
          <>
            <Card style={{ alignItems: "center", gap: spacing.md, paddingVertical: spacing.xl, backgroundColor: tone + "14", borderColor: tone + "44" }}>
              <View style={[styles.statusIcon, { backgroundColor: tone }]}>
                <Ionicons name={meta.icon} size={34} color={scheme === "dark" ? "#121212" : "#FFFFFF"} />
              </View>
              <AppText variant="heading" center>{meta.title}</AppText>
              <AppText variant="bodyMuted" center>{meta.body}</AppText>
              {status === "VERIFIED" ? (
                <View style={[styles.verifiedPill, { backgroundColor: colors.success }]}>
                  <Ionicons name="checkmark-circle" size={16} color="#121212" />
                  <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.sm, color: "#121212" }}>
                    YOU CAN PLACE ORDERS USING APP
                  </AppText>
                </View>
              ) : null}
            </Card>

            {status !== "VERIFIED" ? (
              <View style={{ gap: spacing.md }}>
                <AppText variant="heading">How it works</AppText>
                {STEPS.map((s, i) => (
                  <View key={i} style={styles.step}>
                    <View style={[styles.stepNum, { backgroundColor: colors.brandSoft }]}>
                      <AppText style={{ fontFamily: fonts.bold, color: colors.onBrandSoft, fontSize: fontSize.sm }}>{i + 1}</AppText>
                    </View>
                    <AppText variant="body" style={{ flex: 1 }}>{s}</AppText>
                  </View>
                ))}
                <Card style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
                  <Ionicons name="lock-closed-outline" size={18} color={colors.onSurfaceTertiary} />
                  <AppText variant="caption" style={{ flex: 1 }}>
                    Your documents are encrypted and used only for verification.
                  </AppText>
                </Card>
              </View>
            ) : null}

            {error ? <AppText variant="caption" color={colors.error}>{error}</AppText> : null}

            <Button testID="kyc-cta" label={ctaLabel} onPress={onCta} loading={submitting} />
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  statusIcon: { width: 72, height: 72, borderRadius: 36, alignItems: "center", justifyContent: "center" },
  verifiedPill: { flexDirection: "row", alignItems: "center", gap: spacing.xs, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill },
  step: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  stepNum: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});

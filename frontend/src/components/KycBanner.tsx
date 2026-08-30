import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";
import { AppText } from "./ui/AppText";

const CONFIG: Record<
  string,
  { icon: keyof typeof Ionicons.glyphMap; title: string; sub: string; tone: "verified" | "warning" | "error" }
> = {
  VERIFIED: { icon: "checkmark-circle", title: "KYC VERIFIED", sub: "You can place orders using the app", tone: "verified" },
  PENDING: { icon: "hourglass-outline", title: "KYC Under Review", sub: "We're verifying your details", tone: "warning" },
  REJECTED: { icon: "close-circle-outline", title: "KYC Rejected", sub: "Please retry your verification", tone: "error" },
  REQUIRES_REVERIFICATION: { icon: "refresh-outline", title: "Re-verification Needed", sub: "Update your KYC to continue", tone: "warning" },
  NOT_STARTED: { icon: "id-card-outline", title: "Complete your KYC", sub: "Verify to unlock live ordering", tone: "error" },
};

export function KycBanner({ status }: { status: string }) {
  const { colors } = useTheme();
  const router = useRouter();
  const cfg = CONFIG[status] || CONFIG.NOT_STARTED;
  const tone = { verified: colors.verified, warning: colors.warning, error: colors.error }[cfg.tone];
  const isVerified = status === "VERIFIED";

  return (
    <Pressable
      testID="kyc-banner"
      onPress={() => router.push("/kyc")}
      style={[
        styles.wrap,
        {
          backgroundColor: isVerified ? tone + "12" : colors.surfaceSecondary,
          borderColor: isVerified ? tone + "66" : colors.border,
        },
      ]}
    >
      <View style={[styles.icon, { backgroundColor: isVerified ? tone : colors.surfaceTertiary }]}>
        <Ionicons name={cfg.icon} size={20} color={isVerified ? "#FFFFFF" : tone} />
      </View>
      <View style={{ flex: 1 }}>
        <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: isVerified ? tone : colors.onSurface }}>
          {cfg.title}
        </AppText>
        <AppText variant="caption">{cfg.sub}</AppText>
      </View>
      {!isVerified ? <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} /> : <Ionicons name="checkmark" size={18} color={tone} />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 11,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  icon: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
});

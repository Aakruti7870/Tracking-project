import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";
import { AppText } from "./ui/AppText";

const CONFIG: Record<
  string,
  { icon: keyof typeof Ionicons.glyphMap; title: string; sub: string; tone: "success" | "warning" | "error" }
> = {
  VERIFIED: { icon: "shield-checkmark", title: "KYC Verified", sub: "You can place orders using the app", tone: "success" },
  PENDING: { icon: "hourglass-outline", title: "KYC Under Review", sub: "We're verifying your details", tone: "warning" },
  REJECTED: { icon: "close-circle-outline", title: "KYC Rejected", sub: "Please retry your verification", tone: "error" },
  REQUIRES_REVERIFICATION: { icon: "refresh-outline", title: "Re-verification Needed", sub: "Update your KYC to continue", tone: "warning" },
  NOT_STARTED: { icon: "id-card-outline", title: "Complete your KYC", sub: "Verify to unlock live ordering", tone: "error" },
};

export function KycBanner({ status }: { status: string }) {
  const { colors } = useTheme();
  const router = useRouter();
  const cfg = CONFIG[status] || CONFIG.NOT_STARTED;
  const tone = { success: colors.success, warning: colors.warning, error: colors.error }[cfg.tone];

  return (
    <Pressable
      testID="kyc-banner"
      onPress={() => router.push("/kyc")}
      style={[styles.wrap, { backgroundColor: tone + "1A", borderColor: tone + "55" }]}
    >
      <View style={[styles.icon, { backgroundColor: tone }]}>
        <Ionicons name={cfg.icon} size={20} color={colors.isDark ? "#121212" : "#FFFFFF"} />
      </View>
      <View style={{ flex: 1 }}>
        <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: colors.onSurface }}>
          {cfg.title}
        </AppText>
        <AppText variant="caption">{cfg.sub}</AppText>
      </View>
      {status !== "VERIFIED" ? <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  icon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});

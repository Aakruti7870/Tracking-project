import React, { useEffect } from "react";
import { View } from "react-native";
import { useRouter } from "expo-router";

import { AppText } from "@/src/components/ui/AppText";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

export default function KycReturnScreen() {
  const router = useRouter();
  const { colors } = useTheme();

  useEffect(() => {
    const timer = setTimeout(() => router.replace("/kyc"), 250);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm, backgroundColor: colors.surface, padding: spacing.xl }}>
      <AppText variant="heading">Returning to TrackMyRMC</AppText>
      <AppText variant="caption" style={{ textAlign: "center" }}>
        Checking your DigiLocker consent status securely…
      </AppText>
    </View>
  );
}

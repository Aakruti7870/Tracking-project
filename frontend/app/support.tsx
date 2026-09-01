import React from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

export default function Support() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return <View style={{ flex: 1, backgroundColor: colors.surface }}>
    <View style={{ height: insets.top }} />
    <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
      <AppText variant="title">Support & Contact</AppText>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Account access</AppText>
        <AppText variant="bodyMuted">Use your registered mobile number or email on the sign-in screen to receive an OTP. Plant owners and operational staff accounts must already be provisioned by the relevant organization.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Account deletion</AppText>
        <AppText variant="bodyMuted">You do not need to sign in to begin account deletion. Use Delete Account on the sign-in screen and verify ownership with the OTP sent to your registered mobile number or email.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Operational support</AppText>
        <AppText variant="bodyMuted">For plant, dispatch, billing, order or staff-account assistance, contact the plant or organization administrator responsible for your TrackMyRMC account. This screen intentionally does not publish an unverified support address.</AppText>
      </Card>
    </ScrollView>
  </View>;
}

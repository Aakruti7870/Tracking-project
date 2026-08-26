import React from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

export default function Terms() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return <View style={{ flex: 1, backgroundColor: colors.surface }}>
    <View style={{ height: insets.top }} />
    <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
      <AppText variant="title">Terms of Service</AppText>
      <AppText variant="caption">Last updated: 26 August 2026</AppText>
      <Card style={{ gap: spacing.sm }}><AppText variant="heading">Use of the service</AppText><AppText variant="bodyMuted">TrackMyRMC provides role-based tools for ready-mix concrete ordering, plant operations, dispatch, delivery, billing and related workflows. You must use the service only for authorized and lawful business purposes.</AppText></Card>
      <Card style={{ gap: spacing.sm }}><AppText variant="heading">Account responsibility</AppText><AppText variant="bodyMuted">Keep access to your registered mobile number, email and devices secure. OTP verification is used to confirm access. Do not attempt to access another user's account or role.</AppText></Card>
      <Card style={{ gap: spacing.sm }}><AppText variant="heading">Operational records</AppText><AppText variant="bodyMuted">Orders, delivery records, challans, invoices, KYC and other business records may be relied upon for operational, contractual, statutory or accounting purposes. Users are responsible for submitting accurate information.</AppText></Card>
      <Card style={{ gap: spacing.sm }}><AppText variant="heading">Availability and changes</AppText><AppText variant="bodyMuted">Features may change as the service evolves. Temporary interruption may occur for maintenance, connectivity, provider outages or security reasons.</AppText></Card>
      <Card style={{ gap: spacing.sm }}><AppText variant="heading">Account deletion</AppText><AppText variant="bodyMuted">You may request deletion from the sign-in screen without logging in, after OTP ownership verification, or from account settings while signed in. Records that must be retained for legal or accounting obligations may remain in anonymized form.</AppText></Card>
    </ScrollView>
  </View>;
}

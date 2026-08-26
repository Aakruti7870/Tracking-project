import React from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

export default function PrivacyPolicy() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return <View style={{ flex: 1, backgroundColor: colors.surface }}>
    <View style={{ height: insets.top }} />
    <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
      <AppText variant="title">Privacy Policy</AppText>
      <AppText variant="caption">Last updated: 26 August 2026</AppText>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Information used by TrackMyRMC</AppText>
        <AppText variant="bodyMuted">The service uses account identifiers such as mobile number or email for OTP authentication, profile and role information for access control, and operational data needed for ready-mix concrete ordering, dispatch, delivery, billing, KYC, attendance and support workflows.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Location, camera and files</AppText>
        <AppText variant="bodyMuted">Location may be used for plant discovery, delivery tracking, driver operations or attendance where those features are enabled. Camera or file access may be used when you choose to provide KYC documents, delivery proof, signatures or other operational records.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Sharing and service providers</AppText>
        <AppText variant="bodyMuted">Data may be processed by infrastructure, mapping, notification, payment, KYC or authentication providers only as needed to deliver enabled product features. TrackMyRMC does not claim to sell personal data.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Retention and deletion</AppText>
        <AppText variant="bodyMuted">You may request account deletion from the sign-in screen or from your account settings. Personal sign-in identity and profile data are removed when deletion is completed. Statutory transaction records such as orders, challans or invoices may be retained in anonymized form where required for legal or accounting obligations.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Security</AppText>
        <AppText variant="bodyMuted">TrackMyRMC uses OTP-based authentication, role-based access controls and revocable sessions. No security method can guarantee absolute protection, so access should be limited to authorized users and devices.</AppText>
      </Card>
    </ScrollView>
  </View>;
}

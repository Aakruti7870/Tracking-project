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
      <AppText variant="title">TrackMyRMC Privacy Policy</AppText>
      <AppText variant="caption">Last updated: 27 August 2026</AppText>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Who operates this app</AppText>
        <AppText variant="bodyMuted">TrackMyRMC / Concrete King is operated by GOLD-e Tech. Privacy and account-deletion questions can be sent to support@goldetech.com.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Account and operational information</AppText>
        <AppText variant="bodyMuted">We use mobile number or email for authentication, and profile, role, plant assignment and KYC status for access control. Operational records may include ready-mix concrete orders, sites, dispatches, delivery trips, challans, proof of delivery, signatures, invoices, payments, attendance, incidents and support records when you use those features.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Location</AppText>
        <AppText variant="bodyMuted">Foreground location may be used for location-aware features such as attendance, nearby-plant or delivery operations when you initiate those features. For an assigned Driver delivery only, TrackMyRMC may collect precise location in the background to enable live mixer delivery tracking even when the app is closed or not in use. During that active trip, location is sent to TrackMyRMC and may be shown to the assigned plant and the authorized customer tracking view. Background tracking stops when the delivery is completed. Location is not used for advertising.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Camera, photos and files</AppText>
        <AppText variant="bodyMuted">Camera access is requested only when a Driver chooses to capture a proof-of-delivery site photo. Where the Android system photo picker is available, selecting an existing photo does not require broad storage access. KYC document and consent flows use approved verification providers such as DigiLocker where enabled. We do not request broad photo, video or external-storage access for normal app operation.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Notifications</AppText>
        <AppText variant="bodyMuted">If you choose to enable notifications, the app registers a device push token so it can deliver account-relevant alerts such as order approvals, dispatch and delivery updates, assigned trips, KYC decisions and safety alerts. Notification permission is optional and can be declined without blocking the app.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Sharing and service providers</AppText>
        <AppText variant="bodyMuted">Data is shared only as needed for the service and according to role permissions. For example, an assigned plant and customer can receive delivery status and authorized tracking information. Infrastructure, mapping, notification, payment, KYC and authentication providers may process the minimum data needed to provide their enabled features. TrackMyRMC does not sell personal data and does not use location for advertising.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Retention and account deletion</AppText>
        <AppText variant="bodyMuted">You can request account deletion from the sign-in screen without being logged in or from account settings after sign-in. After verified deletion is completed, sign-in identifiers, profile data, sessions, saved customer sites, app notifications and registered push tokens are removed or anonymized. Certain statutory transaction records such as orders, challans or invoices may be retained only where required for legal, tax, fraud-prevention or accounting obligations; retained records are separated from the deleted login identity as far as operationally possible.</AppText>
      </Card>
      <Card style={{ gap: spacing.sm }}>
        <AppText variant="heading">Security and choices</AppText>
        <AppText variant="bodyMuted">TrackMyRMC uses authenticated sessions and role-based access controls. Sensitive Android permissions are requested in the feature that needs them. You can decline optional permissions, revoke them in Android settings, or stop an active delivery to end background location tracking.</AppText>
      </Card>
    </ScrollView>
  </View>;
}
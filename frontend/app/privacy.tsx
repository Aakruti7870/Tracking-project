import React, { useEffect } from "react";
import { Linking, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

const PRIVACY_URL = "https://trackmyrmc.com/privacy_policy";

export default function PrivacyPolicy() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();

  const openPrivacy = () => Linking.openURL(PRIVACY_URL);

  useEffect(() => {
    void openPrivacy();
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
        <Card style={{ gap: spacing.md }}>
          <AppText variant="title">Privacy Policy</AppText>
          <AppText variant="bodyMuted">
            The official TrackMyRMC Privacy Policy opens at {PRIVACY_URL}.
          </AppText>
          <Button label="Open Privacy Policy" onPress={openPrivacy} />
        </Card>

        <Card style={{ gap: spacing.sm }}>
          <AppText variant="heading">Location and live delivery tracking</AppText>
          <AppText variant="bodyMuted">
            Foreground location may be used for location-aware features such as attendance, nearby-plant or delivery operations when you initiate those features. For an assigned Driver delivery only, TrackMyRMC may collect precise location in the background to enable live mixer delivery tracking even when the app is closed or not in use. During that active trip, location may be shown to the assigned plant and the authorized customer tracking view. Background tracking stops when the delivery is completed. Location is not used for advertising.
          </AppText>
        </Card>

        <Card style={{ gap: spacing.sm }}>
          <AppText variant="heading">Privacy and support contact</AppText>
          <AppText variant="bodyMuted">
            TrackMyRMC / Concrete King is operated by GOLD-e Tech. Privacy and account-deletion questions can be sent to support@goldetech.com.
          </AppText>
        </Card>
      </ScrollView>
    </View>
  );
}

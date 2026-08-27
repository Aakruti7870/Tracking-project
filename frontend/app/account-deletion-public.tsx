import React, { useEffect } from "react";
import { Linking, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

const DELETE_ACCOUNT_URL = "https://trackmyrmc.com/account-deletion";

export default function PublicAccountDeletion() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();

  const openDeletionPage = () => Linking.openURL(DELETE_ACCOUNT_URL);

  useEffect(() => {
    void openDeletionPage();
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
        <Card style={{ gap: spacing.md }}>
          <AppText variant="title">Delete Account</AppText>
          <AppText variant="bodyMuted">
            You can request deletion without signing in. The official TrackMyRMC account-deletion page opens in your browser and verifies account ownership before accepting the request.
          </AppText>
          <Button label="Open Delete Account Page" onPress={openDeletionPage} />
          <AppText variant="caption" center>{DELETE_ACCOUNT_URL}</AppText>
        </Card>

        <Card style={{ gap: spacing.sm }}>
          <AppText variant="heading">What happens after verification</AppText>
          <AppText variant="bodyMuted">
            After a verified deletion request is completed, your sign-in identity, personal profile and active sessions are removed or anonymized. Orders, challans, invoices and other statutory transaction records may be retained only where legally required.
          </AppText>
        </Card>
      </ScrollView>
    </View>
  );
}

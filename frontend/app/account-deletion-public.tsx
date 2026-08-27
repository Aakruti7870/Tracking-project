import React, { useEffect } from "react";
import { Linking, View } from "react-native";
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
      <View style={{ flex: 1, justifyContent: "center", padding: spacing.lg }}>
        <Card style={{ gap: spacing.lg }}>
          <View style={{ gap: spacing.sm }}>
            <AppText variant="title">Delete Account</AppText>
            <AppText variant="bodyMuted">
              Opening the official TrackMyRMC account-deletion page in your browser.
            </AppText>
          </View>
          <Button label="Open Delete Account Page" onPress={openDeletionPage} />
          <AppText variant="caption" center>{DELETE_ACCOUNT_URL}</AppText>
        </Card>
      </View>
    </View>
  );
}

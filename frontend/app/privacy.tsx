import React, { useEffect } from "react";
import { Linking, View } from "react-native";
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
      <View style={{ flex: 1, justifyContent: "center", padding: spacing.lg }}>
        <Card style={{ gap: spacing.lg }}>
          <View style={{ gap: spacing.sm }}>
            <AppText variant="title">Privacy Policy</AppText>
            <AppText variant="bodyMuted">
              Opening the official TrackMyRMC Privacy Policy in your browser.
            </AppText>
          </View>
          <Button label="Open Privacy Policy" onPress={openPrivacy} />
          <AppText variant="caption" center>{PRIVACY_URL}</AppText>
        </Card>
      </View>
    </View>
  );
}

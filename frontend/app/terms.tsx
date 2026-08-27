import React, { useEffect } from "react";
import { Linking, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

const TERMS_URL = "https://trackmyrmc.com/terms";

export default function Terms() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();

  const openTerms = () => Linking.openURL(TERMS_URL);

  useEffect(() => {
    void openTerms();
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <View style={{ flex: 1, justifyContent: "center", padding: spacing.lg }}>
        <Card style={{ gap: spacing.lg }}>
          <View style={{ gap: spacing.sm }}>
            <AppText variant="title">Terms & Conditions</AppText>
            <AppText variant="bodyMuted">
              Opening the official TrackMyRMC Terms & Conditions in your browser.
            </AppText>
          </View>
          <Button label="Open Terms & Conditions" onPress={openTerms} />
          <AppText variant="caption" center>{TERMS_URL}</AppText>
        </Card>
      </View>
    </View>
  );
}

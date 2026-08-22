import { Redirect } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";

// Roles with a fully-built dashboard. Others land on the role placeholder.
const ROUTED_ROLES: Record<string, string> = {
  customer: "/(customer)",
  plant_owner: "/(owner)",
};

export default function Index() {
  const { hydrating, token, user } = useAuth();
  const { colors } = useTheme();

  if (hydrating) {
    return (
      <View testID="boot-loader" style={[styles.center, { backgroundColor: colors.surface }]}>
        <ActivityIndicator color={colors.brand} size="large" />
      </View>
    );
  }

  if (!token || !user) {
    return <Redirect href="/login" />;
  }

  const dest = ROUTED_ROLES[user.role];
  if (dest) return <Redirect href={dest as any} />;

  return <Redirect href="/role-home" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});

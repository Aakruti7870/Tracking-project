import React, { useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { StaffCollection } from "@/src/screens/StaffCollection";
import { useGet } from "@/src/hooks/useApi";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type RecoveryItem = {
  id: string;
  name: string;
  contact?: string | null;
  purpose: string;
  status: "IN_PROGRESS";
  provider?: string | null;
  provider_status?: string | null;
  updated_at?: string | null;
};

type RecoveryResponse = {
  title: string;
  items: RecoveryItem[];
};

export default function Screen() {
  const { colors } = useTheme();
  const { token } = useAuth();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { data, loading, error, refetch } = useGet<RecoveryResponse>("/staff/kyc-recovery");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await refetch();
    } finally {
      setRefreshing(false);
    }
  };

  const resetForRetry = async (item: RecoveryItem) => {
    if (!token) return;
    setBusyId(item.id);
    try {
      await apiPost(`/staff/kyc-recovery/${item.id}/reset`, token);
      toast("KYC reset for retry", "success");
      await refetch();
    } catch (e: any) {
      toast(e.detail || "Could not reset KYC", "error");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.brand} />}
      >
        <View style={{ gap: spacing.xs }}>
          <AppText variant="title">KYC Requests</AppText>
          <AppText variant="bodyMuted">
            Approve or reject only KYC where DigiLocker consent has completed. Incomplete sessions can only be reset so the user can retry.
          </AppText>
        </View>

        <View style={{ gap: spacing.md }}>
          <AppText variant="heading">Awaiting Authority review</AppText>
          <StaffCollection kind="kyc" embedded />
        </View>

        <View style={{ gap: spacing.md }}>
          <View style={{ gap: 2 }}>
            <AppText variant="heading">Incomplete DigiLocker sessions</AppText>
            <AppText variant="caption">
              These users started DigiLocker but did not reach Authority review. Resetting does not approve or reject KYC.
            </AppText>
          </View>

          {loading && !data ? (
            <>
              <Skeleton height={110} style={{ borderRadius: radius.lg }} />
              <Skeleton height={110} style={{ borderRadius: radius.lg }} />
            </>
          ) : error ? (
            <Card style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
              <Ionicons name="warning-outline" size={18} color={colors.error} />
              <AppText variant="caption" color={colors.error} style={{ flex: 1 }}>{error}</AppText>
            </Card>
          ) : (data?.items || []).length === 0 ? (
            <Card style={{ alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl }}>
              <Ionicons name="checkmark-circle-outline" size={28} color={colors.success} />
              <AppText variant="bodyMuted">No incomplete DigiLocker sessions</AppText>
            </Card>
          ) : (
            (data?.items || []).map((item) => (
              <Card key={item.id} style={{ gap: spacing.md }}>
                <View style={styles.row}>
                  <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
                    <Ionicons name="id-card-outline" size={19} color={colors.onBrandSoft} />
                  </View>
                  <View style={{ flex: 1, gap: 2 }}>
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>
                      {item.name}
                    </AppText>
                    {item.contact ? <AppText variant="caption">{item.contact}</AppText> : null}
                    <AppText style={{ fontFamily: fonts.regular, fontSize: 11, color: colors.onSurfaceTertiary }}>
                      {item.purpose.replace(/_/g, " ")} · DigiLocker in progress
                    </AppText>
                  </View>
                </View>
                <Button
                  testID={`kyc-reset-${item.id}`}
                  label="Reset for Retry"
                  variant="outline"
                  onPress={() => resetForRetry(item)}
                  loading={busyId === item.id}
                />
              </Card>
            ))
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, paddingBottom: 120, gap: spacing.xl },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  icon: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
});

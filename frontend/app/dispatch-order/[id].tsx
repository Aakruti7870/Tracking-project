import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { ErrorView } from "@/src/components/StateViews";
import { OwnerDispatchPanel } from "@/src/components/OwnerDispatchPanel";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type OrderDetail = {
  id: string;
  order_number: string;
  customer_name?: string;
  grade: string;
  quantity: number;
  site_name?: string;
  site_address?: string;
  status: string;
  tm_number?: string | null;
  driver_name?: string | null;
  challan_number?: string | null;
  invoice_number?: string | null;
};

export default function DispatchOrder() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, loading, error, refetch, reload } = useGet<{ order: OrderDetail }>(`/staff/orders/${id}`);
  const o = data?.order;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="disp-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">Dispatch Order</AppText>
      </View>

      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : loading && !data ? (
        <View style={{ padding: spacing.lg, gap: spacing.md }}>
          <Skeleton height={120} style={{ borderRadius: radius.lg }} />
          <Skeleton height={220} style={{ borderRadius: radius.lg }} />
        </View>
      ) : o ? (
        <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing["3xl"] }} showsVerticalScrollIndicator={false}>
          <Card style={{ gap: spacing.xs }}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <AppText variant="heading">{o.order_number}</AppText>
              <Badge label={(o.status || "").replace(/_/g, " ")} status={o.status} />
            </View>
            <AppText style={{ fontFamily: fonts.displayBold, fontSize: fontSize["2xl"], color: colors.onSurface }}>
              {o.grade} · {o.quantity} m³
            </AppText>
            {o.customer_name ? <AppText variant="caption">Customer: {o.customer_name}</AppText> : null}
            {o.site_name ? <AppText variant="caption">Site: {o.site_name}</AppText> : null}
            {o.site_address ? <AppText variant="caption">{o.site_address}</AppText> : null}
          </Card>

          <OwnerDispatchPanel
            orderId={o.id}
            status={o.status}
            quantity={o.quantity}
            tmNumber={o.tm_number}
            driverName={o.driver_name}
            challanNumber={o.challan_number}
            invoiceNumber={o.invoice_number}
            onChanged={refetch}
            onViewChallan={() => router.push(`/challan/${o.id}` as any)}
            basePath="/staff"
            showProduction={false}
            showInvoice={false}
          />
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
});

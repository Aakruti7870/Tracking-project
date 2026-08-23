import React from "react";
import { RefreshControl, ScrollView, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { useGet } from "@/src/hooks/useApi";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, spacing } from "@/src/theme/tokens";

type Quote = {
  id: string;
  quotation_number: string;
  plant_id: string;
  customer_name: string;
  site_name: string;
  site_address: string;
  grade: string;
  quantity_m3: number;
  rate_per_m3: number;
  total: number;
  valid_until: string;
  status: string;
};

export default function CustomerQuotations() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { data, loading, refetch } = useGet<{ quotations: Quote[] }>("/ops/customer/quotations");

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }} refreshControl={<RefreshControl refreshing={false} onRefresh={refetch} tintColor={colors.brand} />}>
        <View><AppText variant="title">Quotations</AppText><AppText variant="caption">Commercial offers issued to your account</AppText></View>
        {loading && !data ? <><Skeleton height={100} /><Skeleton height={100} /></> : null}
        {data?.quotations.map((q) => (
          <Card key={q.id} style={{ gap: spacing.sm }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
              <Ionicons name="document-text-outline" size={20} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{q.quotation_number}</AppText>
                <AppText variant="caption">{q.grade} · {q.quantity_m3} m³ · {q.site_name}</AppText>
              </View>
              <AppText style={{ fontFamily: fonts.semibold, color: colors.onSurface }}>₹{Math.round(q.total || 0)}</AppText>
            </View>
            <AppText variant="caption">{q.site_address}</AppText>
            <AppText variant="caption">Rate ₹{q.rate_per_m3}/m³ · Valid until {q.valid_until} · {q.status}</AppText>
          </Card>
        ))}
        {data && data.quotations.length === 0 ? <Card><AppText variant="bodyMuted">No quotations issued yet.</AppText></Card> : null}
      </ScrollView>
    </View>
  );
}

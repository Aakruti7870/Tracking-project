import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, spacing } from "@/src/theme/tokens";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { AppText } from "./ui/AppText";

export type OrderData = {
  id: string;
  order_number: string;
  plant_name: string;
  grade: string;
  quantity: number;
  site_name: string;
  site_address?: string;
  delivery_date: string;
  delivery_time?: string;
  status: string;
  payment_status: string;
};

export function OrderCard({ order, onPress }: { order: OrderData; onPress?: () => void }) {
  const { colors } = useTheme();
  return (
    <Pressable onPress={onPress} testID={`order-card-${order.order_number}`}>
      <Card style={{ gap: spacing.md }}>
        <View style={styles.row}>
          <View style={{ flex: 1 }}>
            <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.lg, color: colors.onSurface }}>
              {order.order_number}
            </AppText>
            <AppText variant="caption" numberOfLines={1}>
              {order.plant_name}
            </AppText>
          </View>
          <Badge label={order.status.replace(/_/g, " ")} status={order.status} />
        </View>

        <View style={[styles.metaRow, { borderColor: colors.divider }]}>
          <Meta icon="layers-outline" label="Grade" value={order.grade} colors={colors} />
          <Meta icon="cube-outline" label="Qty" value={`${order.quantity} m³`} colors={colors} />
          <Meta
            icon="calendar-outline"
            label="Delivery"
            value={order.delivery_time ? `${order.delivery_date.slice(5)} · ${order.delivery_time}` : order.delivery_date.slice(5)}
            colors={colors}
          />
        </View>

        <View style={styles.row}>
          <View style={styles.siteRow}>
            <Ionicons name="location-outline" size={14} color={colors.onSurfaceTertiary} />
            <AppText variant="caption" numberOfLines={1} style={{ flex: 1 }}>
              {order.site_name}
            </AppText>
          </View>
          <Badge label={order.payment_status} status={order.payment_status} />
        </View>
      </Card>
    </Pressable>
  );
}

function Meta({ icon, label, value, colors }: any) {
  return (
    <View style={styles.meta}>
      <Ionicons name={icon} size={14} color={colors.brand} />
      <View>
        <AppText style={{ fontFamily: fonts.regular, fontSize: 10, color: colors.onSurfaceTertiary }}>
          {label}
        </AppText>
        <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }}>
          {value}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: spacing.sm,
  },
  meta: { flexDirection: "row", alignItems: "center", gap: 6 },
  siteRow: { flexDirection: "row", alignItems: "center", gap: 4, flex: 1, marginRight: spacing.sm },
});

import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import type { Order } from "@/src/domain/order";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, spacing } from "@/src/theme/tokens";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { AppText } from "./ui/AppText";

export type { Order as OrderData } from "@/src/domain/order";

type MetaProps = {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  value: string;
  colors: ReturnType<typeof useTheme>["colors"];
};

export function OrderCard({ order, onPress }: { order: Order; onPress?: () => void }) {
  const { colors } = useTheme();
  const interactive = Boolean(onPress);
  return (
    <Pressable
      onPress={onPress}
      disabled={!interactive}
      testID={`order-card-${order.order_number}`}
      accessibilityRole={interactive ? "button" : undefined}
      accessibilityLabel={`Order ${order.order_number}. ${order.grade}, ${order.quantity} cubic metres. ${order.status.replace(/_/g, " ")}.`}
      accessibilityHint={interactive ? "Opens order details" : undefined}
      style={({ pressed }) => ({ opacity: pressed && interactive ? 0.9 : 1, transform: [{ scale: pressed && interactive ? 0.992 : 1 }] })}
    >
      <Card style={{ gap: spacing.md }}>
        <View style={styles.row}>
          <View style={{ flex: 1, gap: 2 }}>
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
            <Ionicons name="location-outline" size={15} color={colors.onSurfaceTertiary} />
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

function Meta({ icon, label, value, colors }: MetaProps) {
  return (
    <View style={styles.meta}>
      <View style={[styles.metaIcon, { backgroundColor: colors.brandSoft }]}>
        <Ionicons name={icon} size={14} color={colors.brand} />
      </View>
      <View style={{ gap: 1 }}>
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
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: spacing.sm,
  },
  meta: { flex: 1, minWidth: 0, flexDirection: "row", alignItems: "center", gap: 6 },
  metaIcon: { width: 28, height: 28, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  siteRow: { flexDirection: "row", alignItems: "center", gap: 4, flex: 1, marginRight: spacing.sm },
});
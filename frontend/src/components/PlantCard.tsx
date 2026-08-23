import React from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";
import { Card } from "./ui/Card";
import { AppText } from "./ui/AppText";

export type PlantData = {
  id: string;
  name: string;
  city: string;
  district?: string;
  address: string;
  lat?: number | null;
  lng?: number | null;
  grades: string[];
  contact_phone: string;
  service_area_km: number;
  status?: string;
  verified: boolean;
  order_enabled?: boolean;
};

function readableStatus(value?: string) {
  const status = (value || "active").trim().toLowerCase();
  if (status === "active") return "Active";
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function PlantCard({ plant, onOrder }: { plant: PlantData; onOrder?: () => void }) {
  const { colors } = useTheme();
  const status = (plant.status || "active").toLowerCase();
  const orderEnabled = plant.order_enabled ?? (status === "active" && plant.verified);

  const openDirections = () => {
    const destination =
      plant.lat != null && plant.lng != null ? `${plant.lat},${plant.lng}` : plant.address;
    const url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
    Linking.openURL(url);
  };

  return (
    <Card style={{ gap: spacing.md }}>
      <View style={styles.row}>
        <View style={{ flex: 1, gap: 4 }}>
          <View style={styles.nameRow}>
            <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.lg, color: colors.onSurface }} numberOfLines={1}>
              {plant.name}
            </AppText>
            {plant.verified ? (
              <Ionicons name="shield-checkmark" size={16} color={colors.success} />
            ) : null}
          </View>
          <AppText variant="caption" numberOfLines={1}>
            {plant.city}
            {plant.district ? ` · ${plant.district}` : ""}
          </AppText>
          <View style={styles.metaRow}>
            <View style={[styles.statusDot, { backgroundColor: status === "active" ? colors.success : colors.warning }]} />
            <AppText variant="caption">{readableStatus(status)}</AppText>
            {plant.verified ? (
              <AppText variant="caption" color={colors.success}>Verified</AppText>
            ) : (
              <AppText variant="caption">Verification pending</AppText>
            )}
          </View>
        </View>
      </View>

      <View style={styles.grades}>
        {plant.grades.slice(0, 5).map((g) => (
          <View key={g} style={[styles.gradeChip, { backgroundColor: colors.surfaceTertiary }]}>
            <AppText style={{ fontFamily: fonts.semibold, fontSize: 11, color: colors.onSurfaceSecondary }}>
              {g}
            </AppText>
          </View>
        ))}
      </View>

      <View style={styles.actions}>
        <Action
          icon="call-outline"
          label="Call"
          colors={colors}
          onPress={() => plant.contact_phone && Linking.openURL(`tel:${plant.contact_phone}`)}
        />
        <Action icon="navigate-outline" label="Directions" colors={colors} onPress={openDirections} />
        <Pressable
          onPress={orderEnabled ? onOrder : undefined}
          disabled={!orderEnabled}
          testID={`plant-order-${plant.id}`}
          accessibilityState={{ disabled: !orderEnabled }}
          style={[
            styles.orderBtn,
            { backgroundColor: orderEnabled ? colors.brand : colors.surfaceTertiary, opacity: orderEnabled ? 1 : 0.72 },
          ]}
        >
          <Ionicons
            name={orderEnabled ? "add-circle-outline" : "time-outline"}
            size={16}
            color={orderEnabled ? colors.onBrand : colors.onSurfaceTertiary}
          />
          <AppText
            style={{
              fontFamily: fonts.semibold,
              fontSize: fontSize.sm,
              color: orderEnabled ? colors.onBrand : colors.onSurfaceTertiary,
            }}
          >
            {orderEnabled ? "Order Now" : "Unavailable"}
          </AppText>
        </Pressable>
      </View>
    </Card>
  );
}

function Action({ icon, label, colors, onPress }: any) {
  return (
    <Pressable onPress={onPress} style={[styles.action, { borderColor: colors.border }]}>
      <Ionicons name={icon} size={16} color={colors.onSurfaceSecondary} />
      <AppText style={{ fontFamily: fonts.medium, fontSize: fontSize.sm, color: colors.onSurfaceSecondary }}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  metaRow: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 6 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  grades: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  gradeChip: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  actions: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  action: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  orderBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    marginLeft: "auto",
  },
});

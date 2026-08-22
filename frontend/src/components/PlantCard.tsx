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
  grades: string[];
  contact_phone: string;
  service_area_km: number;
  verified: boolean;
};

export function PlantCard({ plant, onOrder }: { plant: PlantData; onOrder?: () => void }) {
  const { colors } = useTheme();

  return (
    <Card style={{ gap: spacing.md }}>
      <View style={styles.row}>
        <View style={{ flex: 1, gap: 2 }}>
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
            {plant.district ? ` · ${plant.district}` : ""} · {plant.service_area_km} km range
          </AppText>
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
          onPress={() => Linking.openURL(`tel:${plant.contact_phone}`)}
        />
        <Action icon="navigate-outline" label="Directions" colors={colors} onPress={() => {}} />
        <Pressable
          onPress={onOrder}
          testID={`plant-order-${plant.id}`}
          style={[styles.orderBtn, { backgroundColor: colors.brand }]}
        >
          <Ionicons name="add-circle-outline" size={16} color={colors.onBrand} />
          <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onBrand }}>
            Order Now
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
  grades: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  gradeChip: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  actions: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
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

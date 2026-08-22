import React, { useEffect } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { LiveMap } from "@/src/components/LiveMap";
import { ErrorView } from "@/src/components/StateViews";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Track = {
  active: boolean;
  status: string;
  tm_number?: string;
  driver_name?: string;
  driver_mobile?: string;
  destination: { site_name: string; address?: string; lat?: number; lng?: number };
  location: { lat: number; lng: number; at: string } | null;
  route?: {
    eta_seconds: number;
    eta_text: string;
    distance_m: number;
    distance_text: string;
    polyline?: string;
  } | null;
};

export default function TrackScreen() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, loading, error, refetch, reload } = useGet<Track>(`/customer/orders/${id}/tracking`);

  // Poll every 15s while the delivery is active.
  useEffect(() => {
    if (!data?.active) return;
    const t = setInterval(refetch, 15000);
    return () => clearInterval(t);
  }, [data?.active]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="track-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">Live Tracking</AppText>
      </View>
      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : loading && !data ? (
        <View style={{ padding: spacing.lg }}><Skeleton height={320} style={{ borderRadius: radius.lg }} /></View>
      ) : data ? (
        <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }} showsVerticalScrollIndicator={false}>
          <LiveMap
            destination={data.destination.lat != null ? { lat: data.destination.lat, lng: data.destination.lng! } : null}
            mixer={data.location ? { lat: data.location.lat, lng: data.location.lng } : null}
            polyline={data.route?.polyline}
            ended={data.status === "DELIVERED"}
            style={{ minHeight: 240 }}
          />

          {data.active && data.route ? (
            <View style={styles.etaRow}>
              <View style={[styles.etaCard, { backgroundColor: colors.brand }]}>
                <AppText style={{ fontFamily: fonts.displayBold, fontSize: fontSize["2xl"], color: colors.onBrand }}>{data.route.eta_text}</AppText>
                <AppText style={{ fontFamily: fonts.medium, fontSize: 11, color: colors.onBrand }}>Live ETA</AppText>
              </View>
              <View style={[styles.etaCard, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border, borderWidth: 1 }]}>
                <AppText style={{ fontFamily: fonts.displayBold, fontSize: fontSize["2xl"], color: colors.onSurface }}>{data.route.distance_text}</AppText>
                <AppText style={{ fontFamily: fonts.medium, fontSize: 11, color: colors.onSurfaceTertiary }}>Distance to site</AppText>
              </View>
            </View>
          ) : null}

          <Card style={{ gap: spacing.md }}>
            <View style={styles.rowBetween}>
              <AppText variant="heading">{data.status === "DELIVERED" ? "Delivery complete" : data.active ? "On the way" : "Not dispatched yet"}</AppText>
              <Badge label={data.status.replace(/_/g, " ")} status={data.status} />
            </View>
            <Row icon="business-outline" label="Destination" value={`${data.destination.site_name}${data.destination.address ? " — " + data.destination.address : ""}`} colors={colors} />
            {data.tm_number ? <Row icon="bus-outline" label="Transit Mixer" value={data.tm_number} colors={colors} /> : null}
            {data.driver_name ? <Row icon="person-outline" label="Driver" value={data.driver_name} colors={colors} /> : null}
            {data.location ? <Row icon="navigate-outline" label="Mixer location" value={`${data.location.lat.toFixed(5)}, ${data.location.lng.toFixed(5)}`} colors={colors} /> : null}
            <Row icon="pulse-outline" label="Last GPS update" value={data.location ? new Date(data.location.at).toLocaleTimeString() : "Awaiting driver location"} colors={colors} />
          </Card>

          {!data.location && data.active ? (
            <View style={[styles.note, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name="information-circle-outline" size={16} color={colors.onBrandSoft} />
              <AppText style={{ flex: 1, fontFamily: fonts.medium, fontSize: fontSize.sm, color: colors.onBrandSoft }}>
                The live map activates once the driver shares GPS. ETA appears as soon as the mixer moves.
              </AppText>
            </View>
          ) : null}

          {data.active && data.driver_mobile ? (
            <Button testID="track-call-driver" label="Call Driver" onPress={() => Linking.openURL(`tel:${data.driver_mobile}`)} icon={<Ionicons name="call-outline" size={18} color={colors.onBrand} />} />
          ) : null}
        </ScrollView>
      ) : null}
    </View>
  );
}

function Row({ icon, label, value, colors }: any) {
  return (
    <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" }}>
      <Ionicons name={icon} size={16} color={colors.brand} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <AppText style={{ fontFamily: fonts.regular, fontSize: 11, color: colors.onSurfaceTertiary }}>{label}</AppText>
        <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{value}</AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  etaRow: { flexDirection: "row", gap: spacing.md },
  etaCard: { flex: 1, borderRadius: radius.lg, padding: spacing.md, gap: 2, alignItems: "flex-start" },
  note: { flexDirection: "row", gap: spacing.sm, alignItems: "center", padding: spacing.md, borderRadius: radius.md },
});

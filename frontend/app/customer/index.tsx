import React from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Badge } from "@/src/components/ui/Badge";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { MapPlaceholder } from "@/src/components/ui/MapPlaceholder";
import { KycBanner } from "@/src/components/KycBanner";
import { OrderCard, OrderData } from "@/src/components/OrderCard";
import { ErrorView } from "@/src/components/StateViews";
import { PlantData } from "@/src/components/PlantCard";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type HomeData = {
  name: string;
  kyc_status: string;
  active_order: OrderData | null;
  recent_orders: OrderData[];
  nearby_plants: PlantData[];
  unread_notifications: number;
};

const ACTIONS: { key: string; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "new", label: "New Order", icon: "add-circle-outline" },
  { key: "track", label: "Track Order", icon: "navigate-circle-outline" },
  { key: "kyc", label: "Complete KYC", icon: "id-card-outline" },
  { key: "challan", label: "View Challan", icon: "document-text-outline" },
];

export default function CustomerHome() {
  const { colors, toggle, scheme } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { data, loading, error, refetch, reload } = useGet<HomeData>("/customer/home");

  const onAction = (key: string) => {
    if (key === "kyc") return router.push("/kyc");
    if (key === "track") {
      if (data?.active_order) return toast("Live tracking arrives in the dispatch phase", "info");
      return toast("No active order to track", "info");
    }
    if (key === "new") {
      if (data?.kyc_status !== "VERIFIED") {
        toast("Complete KYC to place an order", "info");
        return router.push("/kyc");
      }
      return router.push("/new-order");
    }
    if (key === "challan") return toast("Challans arrive in the dispatch phase", "info");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <AppText variant="caption">Welcome back</AppText>
          <AppText variant="title" numberOfLines={1}>
            {user?.name || "Customer"}
          </AppText>
        </View>
        <Pressable testID="theme-toggle" onPress={toggle} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name={scheme === "dark" ? "sunny-outline" : "moon-outline"} size={20} color={colors.onSurface} />
        </Pressable>
        <Pressable testID="notifications-bell" style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="notifications-outline" size={20} color={colors.onSurface} />
          {data && data.unread_notifications > 0 ? (
            <View style={[styles.dot, { backgroundColor: colors.brand }]} />
          ) : null}
        </Pressable>
      </View>

      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : (
        <ScrollView
          testID="customer-home-scroll"
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={false} onRefresh={refetch} tintColor={colors.brand} />}
        >
          {loading && !data ? (
            <>
              <Skeleton height={68} style={{ borderRadius: radius.md }} />
              <Skeleton height={220} style={{ borderRadius: radius.lg }} />
              <Skeleton height={90} style={{ borderRadius: radius.lg }} />
            </>
          ) : data ? (
            <>
              <KycBanner status={data.kyc_status} />

              {/* Active order / live tracking */}
              <View style={{ gap: spacing.sm }}>
                <AppText variant="heading">Active Delivery</AppText>
                {data.active_order ? (
                  <Card style={{ gap: spacing.md, padding: spacing.md }}>
                    <MapPlaceholder pins={0} label="Transit mixer en route" style={{ minHeight: 150 }} />
                    <View style={styles.rowBetween}>
                      <View>
                        <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.lg, color: colors.onSurface }}>
                          {data.active_order.order_number}
                        </AppText>
                        <AppText variant="caption">
                          {data.active_order.grade} · {data.active_order.quantity} m³ · {data.active_order.site_name}
                        </AppText>
                      </View>
                      <Badge label={data.active_order.status.replace(/_/g, " ")} status={data.active_order.status} />
                    </View>
                    <Pressable
                      testID="track-active-order"
                      onPress={() => router.push(`/track/${data.active_order!.id}` as any)}
                      style={[styles.trackBtn, { backgroundColor: colors.brand }]}
                    >
                      <Ionicons name="navigate" size={16} color={colors.onBrand} />
                      <AppText style={{ fontFamily: fonts.semibold, color: colors.onBrand }}>Track Order</AppText>
                    </Pressable>
                  </Card>
                ) : (
                  <Card style={{ alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl }}>
                    <Ionicons name="cube-outline" size={32} color={colors.onSurfaceTertiary} />
                    <AppText variant="bodyMuted" center>No active deliveries right now</AppText>
                  </Card>
                )}
              </View>

              {/* Quick actions */}
              <View style={styles.actionGrid}>
                {ACTIONS.map((a) => (
                  <Pressable
                    key={a.key}
                    testID={`action-${a.key}`}
                    onPress={() => onAction(a.key)}
                    style={[styles.action, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
                  >
                    <View style={[styles.actionIcon, { backgroundColor: colors.brandSoft }]}>
                      <Ionicons name={a.icon} size={20} color={colors.onBrandSoft} />
                    </View>
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }}>
                      {a.label}
                    </AppText>
                  </Pressable>
                ))}
              </View>

              {/* Nearby plants */}
              {data.nearby_plants.length > 0 ? (
                <View style={{ gap: spacing.sm }}>
                  <View style={styles.rowBetween}>
                    <AppText variant="heading">Nearby Plants</AppText>
                    <Pressable onPress={() => router.push("/customer/plants")}>
                      <AppText variant="label" color={colors.brand}>See all</AppText>
                    </Pressable>
                  </View>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
                    {data.nearby_plants.map((p) => (
                      <View key={p.id} style={[styles.plantChip, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
                        <View style={styles.rowBetween}>
                          <Ionicons name="business" size={16} color={colors.brand} />
                          {p.verified ? (
                            <Ionicons name="shield-checkmark" size={14} color={colors.success} />
                          ) : (
                            <Ionicons name="time-outline" size={14} color={colors.warning} />
                          )}
                        </View>
                        <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }} numberOfLines={2}>
                          {p.name}
                        </AppText>
                        <AppText variant="caption" numberOfLines={1}>
                          {p.city} · {(p.status || "active").replace(/_/g, " ")}
                        </AppText>
                      </View>
                    ))}
                  </ScrollView>
                </View>
              ) : null}

              {/* Recent orders */}
              <View style={{ gap: spacing.sm }}>
                <View style={styles.rowBetween}>
                  <AppText variant="heading">Recent Orders</AppText>
                  <Pressable onPress={() => router.push("/customer/orders")}>
                    <AppText variant="label" color={colors.brand}>View all</AppText>
                  </Pressable>
                </View>
                {data.recent_orders.length === 0 ? (
                  <Card style={{ alignItems: "center", paddingVertical: spacing.xl }}>
                    <AppText variant="bodyMuted">No orders yet</AppText>
                  </Card>
                ) : (
                  <View style={{ gap: spacing.md }}>
                    {data.recent_orders.slice(0, 3).map((o) => (
                      <OrderCard key={o.id} order={o} onPress={() => router.push(`/order/${o.id}` as any)} />
                    ))}
                  </View>
                )}
              </View>
            </>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    paddingTop: spacing.sm,
  },
  iconBtn: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  dot: { position: "absolute", top: 10, right: 10, width: 8, height: 8, borderRadius: 4 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  trackBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    height: 44,
    borderRadius: radius.md,
  },
  actionGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  action: {
    width: "48%",
    flexGrow: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  actionIcon: { width: 36, height: 36, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  plantChip: { width: 150, gap: 4, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
});

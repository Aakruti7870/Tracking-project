import React from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { KycBanner } from "@/src/components/KycBanner";
import { ErrorView } from "@/src/components/StateViews";
import { CustomerHeroCarousel } from "@/src/components/CustomerHeroCarousel";
import { OrderData } from "@/src/components/OrderCard";
import { PlantData } from "@/src/components/PlantCard";
import { fonts, fontSize, radius, spacing, statusColor } from "@/src/theme/tokens";

type HomeData = {
  name: string;
  kyc_status: string;
  active_order: OrderData | null;
  recent_orders: OrderData[];
  nearby_plants: PlantData[];
  unread_notifications: number;
};

type ServiceKey = "new" | "track" | "plants" | "orders";
type ToolKey = "quantity" | "estimate" | "grade" | "compare" | "saved" | "checklist";

const SERVICES: { key: ServiceKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "new", label: "Order RMC", icon: "add-circle-outline" },
  { key: "track", label: "Track TM", icon: "navigate-outline" },
  { key: "plants", label: "Nearby Plants", icon: "business-outline" },
  { key: "orders", label: "My Orders", icon: "receipt-outline" },
];

const TOOLS: { key: ToolKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "quantity", label: "Calculate Quantity", icon: "calculator-outline" },
  { key: "estimate", label: "Estimate Cost", icon: "cash-outline" },
  { key: "grade", label: "Grade Guide", icon: "layers-outline" },
  { key: "compare", label: "Compare Plants", icon: "git-compare-outline" },
  { key: "saved", label: "Saved Calculations", icon: "bookmark-outline" },
  { key: "checklist", label: "Site Checklist", icon: "checkbox-outline" },
];

export default function CustomerHome() {
  const { colors } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { data, loading, error, refetch, reload } = useGet<HomeData>("/customer/home");

  const go = (path: string) => {
    void Haptics.selectionAsync();
    router.push(path as any);
  };

  const openActiveTracking = () => {
    if (!data?.active_order) {
      toast("No active delivery to track", "info");
      return;
    }
    go(`/track/${data.active_order.id}`);
  };

  const onService = (key: ServiceKey) => {
    if (key === "track") return openActiveTracking();
    if (key === "plants") return go("/customer/plants");
    if (key === "orders") return go("/customer/orders");
    if (data?.kyc_status !== "VERIFIED") {
      toast("Complete KYC to place an order", "info");
      return go("/kyc");
    }
    return go("/new-order");
  };

  const onTool = (key: ToolKey) => {
    if (key === "compare") return go("/customer/compare-plants");
    if (key === "checklist") return go("/customer/receiving-guide");
    return go("/customer/free-tools");
  };

  const onHeroAction = (id: "live" | "order" | "plants" | "challan") => {
    if (id === "live") return data?.active_order ? openActiveTracking() : go("/customer/orders");
    if (id === "order") return onService("new");
    if (id === "plants") return go("/customer/plants");
    return go("/customer/documents");
  };

  return (
    <View style={[styles.root, { backgroundColor: colors.surface }]} testID="customer-home-screen">
      <View style={{ height: insets.top }} />

      <View style={[styles.header, { borderBottomColor: colors.divider, backgroundColor: colors.surface }]}> 
        <Pressable testID="home-profile" onPress={() => go("/customer/more")} style={styles.brandRow} hitSlop={6}>
          <View style={[styles.brandMark, { backgroundColor: colors.brand }]}> 
            <Ionicons name="cube" size={22} color={colors.onBrand} />
          </View>
          <View>
            <AppText style={[styles.brandKicker, { color: colors.onSurfaceTertiary }]}>TRACK MY</AppText>
            <AppText style={[styles.brandWord, { color: colors.onSurface }]}>RMC<AppText style={{ color: colors.brand }}> ●</AppText></AppText>
          </View>
        </Pressable>

        <View style={styles.headerRight}>
          <Pressable
            testID="notifications-bell"
            onPress={() => go("/notifications")}
            style={[styles.iconBtn, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
          >
            <Ionicons name="notifications-outline" size={20} color={colors.onSurface} />
            {data && data.unread_notifications > 0 ? <View style={[styles.notificationDot, { backgroundColor: colors.brand }]} /> : null}
          </Pressable>
          <Pressable
            testID="home-help"
            onPress={() => go("/support")}
            style={[styles.iconBtn, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
          >
            <Ionicons name="help-circle-outline" size={21} color={colors.onSurface} />
          </Pressable>
        </View>
      </View>

      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : (
        <ScrollView
          testID="customer-home-scroll"
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={false} onRefresh={refetch} tintColor={colors.brand} />}
          contentContainerStyle={styles.scrollContent}
        >
          {loading && !data ? (
            <>
              <Skeleton height={190} style={{ borderRadius: radius.lg }} />
              <Skeleton height={110} style={{ borderRadius: radius.lg }} />
              <Skeleton height={180} style={{ borderRadius: radius.lg }} />
            </>
          ) : data ? (
            <>
              <CustomerHeroCarousel onAction={onHeroAction} />

              {data.kyc_status !== "VERIFIED" ? <KycBanner status={data.kyc_status} /> : null}

              <SectionTitle title="RMC Services" colors={colors} />
              <View style={styles.serviceRow}>
                {SERVICES.map((service) => (
                  <Pressable
                    key={service.key}
                    testID={`home-service-${service.key}`}
                    onPress={() => onService(service.key)}
                    style={styles.serviceItem}
                  >
                    <View style={[styles.serviceCircle, { backgroundColor: colors.brandSoft }]}> 
                      <Ionicons name={service.icon} size={25} color={colors.brand} />
                    </View>
                    <AppText numberOfLines={2} style={[styles.serviceLabel, { color: colors.onSurface }]}>{service.label}</AppText>
                  </Pressable>
                ))}
              </View>

              <SectionTitle title="Tools" colors={colors} />
              <View style={styles.toolsGrid}>
                {TOOLS.map((tool) => (
                  <Pressable
                    key={tool.key}
                    testID={`home-tool-${tool.key}`}
                    onPress={() => onTool(tool.key)}
                    style={({ pressed }) => [
                      styles.toolTile,
                      {
                        backgroundColor: colors.surfaceSecondary,
                        borderColor: colors.border,
                        opacity: pressed ? 0.8 : 1,
                      },
                    ]}
                  >
                    <View style={[styles.toolIcon, { backgroundColor: colors.surfaceTertiary }]}> 
                      <Ionicons name={tool.icon} size={21} color={colors.brand} />
                    </View>
                    <AppText numberOfLines={2} style={[styles.toolLabel, { color: colors.onSurface }]}>{tool.label}</AppText>
                  </Pressable>
                ))}
              </View>

              <SectionTitle title="Live Delivery" colors={colors} />
              {data.active_order ? (
                <Card style={styles.liveCard} testID="home-live-delivery">
                  <View style={styles.liveTop}>
                    <View style={{ flex: 1 }}>
                      <AppText style={[styles.orderNumber, { color: colors.onSurface }]}>Order #{data.active_order.order_number}</AppText>
                      <AppText variant="caption">Mix Design · {data.active_order.grade} · {data.active_order.quantity} m³</AppText>
                    </View>
                    <View style={[styles.statusPill, { backgroundColor: colors.brandSoft }]}> 
                      <View style={[styles.statusDot, { backgroundColor: colors.brand }]} />
                      <AppText style={[styles.statusText, { color: colors.onBrandSoft }]}>{data.active_order.status.replace(/_/g, " ")}</AppText>
                    </View>
                  </View>

                  <View style={styles.routeRow}>
                    <View style={styles.routeRail}>
                      <View style={[styles.routeStart, { borderColor: colors.brand }]} />
                      <View style={[styles.routeLine, { backgroundColor: colors.brand }]} />
                      <Ionicons name="location" size={14} color={colors.brand} />
                    </View>
                    <View style={styles.routeLabels}>
                      <AppText variant="label">{data.active_order.plant_name}</AppText>
                      <AppText variant="label" style={{ marginTop: 13 }}>{data.active_order.site_name}</AppText>
                    </View>
                  </View>

                  <View style={[styles.liveMetrics, { borderTopColor: colors.divider }]}> 
                    <View style={styles.metric}>
                      <Ionicons name="time-outline" size={16} color={colors.brand} />
                      <View><AppText variant="caption">STATUS</AppText><AppText style={styles.metricValue}>{data.active_order.status.replace(/_/g, " ")}</AppText></View>
                    </View>
                    <View style={[styles.metricDivider, { backgroundColor: colors.divider }]} />
                    <View style={styles.metric}>
                      <Ionicons name="cube-outline" size={16} color={colors.brand} />
                      <View><AppText variant="caption">QUANTITY</AppText><AppText style={styles.metricValue}>{data.active_order.quantity} m³</AppText></View>
                    </View>
                    <Pressable testID="track-active-order" onPress={openActiveTracking} style={[styles.trackButton, { backgroundColor: colors.brand }]}> 
                      <AppText style={styles.trackButtonText}>Track</AppText>
                      <Ionicons name="arrow-forward" size={15} color="#FFFFFF" />
                    </Pressable>
                  </View>
                </Card>
              ) : (
                <Card style={styles.emptyCard}>
                  <View style={[styles.emptyIcon, { backgroundColor: colors.surfaceTertiary }]}><Ionicons name="navigate-outline" size={24} color={colors.brand} /></View>
                  <View style={{ flex: 1 }}><AppText variant="label">No live delivery</AppText><AppText variant="caption">Your dispatched transit mixer will appear here.</AppText></View>
                  <Pressable onPress={() => onService("new")} hitSlop={8}><Ionicons name="add-circle" size={30} color={colors.brand} /></Pressable>
                </Card>
              )}

              <SectionTitle title="Recent Orders" action="View all" onAction={() => go("/customer/orders")} colors={colors} />
              <View style={styles.recentList}>
                {data.recent_orders.slice(0, 3).map((order) => {
                  const tone = statusColor(colors, order.status);
                  return (
                    <Pressable
                      key={order.id}
                      testID={`home-recent-${order.id}`}
                      onPress={() => go(`/order/${order.id}`)}
                      style={[styles.recentRow, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
                    >
                      <View style={[styles.recentIcon, { backgroundColor: colors.surfaceTertiary }]}><Ionicons name="cube" size={19} color={colors.brand} /></View>
                      <View style={{ flex: 1 }}>
                        <AppText style={[styles.recentTitle, { color: colors.onSurface }]}>{order.grade} · {order.quantity} m³</AppText>
                        <AppText variant="caption">#{order.order_number} · {order.delivery_date}</AppText>
                      </View>
                      <View style={[styles.recentStatus, { backgroundColor: `${tone}18` }]}><AppText style={[styles.recentStatusText, { color: tone }]}>{order.status.replace(/_/g, " ")}</AppText></View>
                      <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceTertiary} />
                    </Pressable>
                  );
                })}
                {data.recent_orders.length === 0 ? <AppText variant="caption">No recent orders yet.</AppText> : null}
              </View>

              <SectionTitle title="Nearby Plants" action="See all" onAction={() => go("/customer/plants")} colors={colors} />
              {data.nearby_plants.length > 0 ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.plantScroller}>
                  {data.nearby_plants.slice(0, 6).map((plant) => (
                    <Pressable
                      key={plant.id}
                      onPress={() => go("/customer/plants")}
                      style={[styles.plantCard, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}
                    >
                      <View style={styles.plantTop}>
                        <View style={[styles.plantBadge, { backgroundColor: colors.brandSoft }]}><Ionicons name="business" size={20} color={colors.brand} /></View>
                        {plant.verified ? <Ionicons name="checkmark-circle" size={18} color={colors.verified} /> : null}
                      </View>
                      <AppText numberOfLines={2} style={styles.plantName}>{plant.name}</AppText>
                      <View style={styles.plantMeta}><Ionicons name="location-outline" size={13} color={colors.onSurfaceTertiary} /><AppText variant="caption" numberOfLines={1} style={{ flex: 1 }}>{plant.city}</AppText></View>
                    </Pressable>
                  ))}
                </ScrollView>
              ) : <AppText variant="caption">Nearby approved plants will appear here.</AppText>}

              <SectionTitle title="Offers & Updates" colors={colors} />
              <Pressable testID="home-offers" onPress={() => go("/notifications")}>
                <View style={styles.offerCard}>
                  <View style={styles.offerCopy}>
                    <AppText style={styles.offerEyebrow}>TRACK MY RMC</AppText>
                    <AppText style={styles.offerTitle}>Offers & service updates</AppText>
                    <AppText style={styles.offerSubtitle}>Check current announcements, delivery updates and available benefits.</AppText>
                  </View>
                  <Ionicons name="ticket-outline" size={66} color="rgba(255,255,255,0.20)" />
                </View>
              </Pressable>
            </>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

function SectionTitle({ title, action, onAction, colors }: { title: string; action?: string; onAction?: () => void; colors: ReturnType<typeof useTheme>["colors"] }) {
  return (
    <View style={styles.sectionHeader}>
      <AppText style={[styles.sectionTitle, { color: colors.onSurface }]}>{title}</AppText>
      {action ? <Pressable onPress={onAction} hitSlop={8}><AppText variant="label" color={colors.brand}>{action}</AppText></Pressable> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: { minHeight: 62, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  brandRow: { flexDirection: "row", alignItems: "center" },
  brandMark: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center", marginRight: spacing.sm },
  brandKicker: { fontFamily: fonts.semibold, fontSize: 9, letterSpacing: 1.8, lineHeight: 12 },
  brandWord: { fontFamily: fonts.displayBold, fontSize: 21, lineHeight: 23 },
  headerRight: { flexDirection: "row", gap: spacing.sm },
  iconBtn: { width: 44, height: 44, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  notificationDot: { position: "absolute", right: 8, top: 8, width: 7, height: 7, borderRadius: 4 },
  scrollContent: { paddingTop: spacing.lg, paddingBottom: 126, gap: spacing.lg },
  sectionHeader: { paddingHorizontal: spacing.lg, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.xs },
  sectionTitle: { fontFamily: fonts.displayBold, fontSize: fontSize.lg },
  serviceRow: { paddingHorizontal: spacing.lg, flexDirection: "row", justifyContent: "space-between" },
  serviceItem: { width: "23%", alignItems: "center", gap: spacing.sm },
  serviceCircle: { width: 58, height: 58, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  serviceLabel: { fontFamily: fonts.medium, fontSize: fontSize.xs, lineHeight: 16, textAlign: "center" },
  toolsGrid: { paddingHorizontal: spacing.lg, flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  toolTile: { width: "31.4%", minHeight: 104, borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center", padding: spacing.sm, gap: spacing.sm },
  toolIcon: { width: 44, height: 44, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  toolLabel: { fontFamily: fonts.medium, fontSize: fontSize.xs, textAlign: "center", lineHeight: 16 },
  liveCard: { marginHorizontal: spacing.lg, gap: spacing.md, borderRadius: radius.lg },
  liveTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  orderNumber: { fontFamily: fonts.bold, fontSize: fontSize.base },
  statusPill: { flexDirection: "row", alignItems: "center", gap: 5, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 6 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontFamily: fonts.semibold, fontSize: 10, textTransform: "capitalize" },
  routeRow: { flexDirection: "row", minHeight: 58 },
  routeRail: { width: 18, alignItems: "center" },
  routeStart: { width: 10, height: 10, borderRadius: 5, borderWidth: 2 },
  routeLine: { width: 2, flex: 1, marginVertical: 2 },
  routeLabels: { flex: 1, paddingLeft: spacing.sm },
  liveMetrics: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: spacing.md, flexDirection: "row", alignItems: "center", gap: spacing.md },
  metric: { flexDirection: "row", alignItems: "center", gap: 6 },
  metricValue: { fontFamily: fonts.semibold, fontSize: fontSize.xs, maxWidth: 90 },
  metricDivider: { width: 1, height: 28 },
  trackButton: { marginLeft: "auto", height: 44, borderRadius: radius.pill, paddingHorizontal: spacing.md, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 5 },
  trackButtonText: { color: "#FFFFFF", fontFamily: fonts.semibold, fontSize: fontSize.sm },
  emptyCard: { marginHorizontal: spacing.lg, flexDirection: "row", alignItems: "center", gap: spacing.md },
  emptyIcon: { width: 46, height: 46, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  recentList: { paddingHorizontal: spacing.lg, gap: spacing.sm },
  recentRow: { minHeight: 70, borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, padding: spacing.md, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  recentIcon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  recentTitle: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  recentStatus: { maxWidth: 92, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 5 },
  recentStatusText: { fontFamily: fonts.semibold, fontSize: 9, textTransform: "capitalize" },
  plantScroller: { paddingHorizontal: spacing.lg, gap: spacing.md },
  plantCard: { width: 180, minHeight: 126, borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, padding: spacing.md, gap: spacing.sm },
  plantTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  plantBadge: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  plantName: { fontFamily: fonts.semibold, fontSize: fontSize.sm, minHeight: 34 },
  plantMeta: { flexDirection: "row", alignItems: "center", gap: 4 },
  offerCard: { marginHorizontal: spacing.lg, minHeight: 132, borderRadius: radius.lg, backgroundColor: "#FF6A00", padding: spacing.lg, flexDirection: "row", alignItems: "center", overflow: "hidden" },
  offerCopy: { flex: 1, paddingRight: spacing.sm },
  offerEyebrow: { color: "rgba(255,255,255,0.78)", fontFamily: fonts.semibold, fontSize: 10, letterSpacing: 1.2 },
  offerTitle: { color: "#FFFFFF", fontFamily: fonts.displayBold, fontSize: fontSize.lg, marginTop: 3 },
  offerSubtitle: { color: "rgba(255,255,255,0.88)", fontFamily: fonts.regular, fontSize: fontSize.xs, lineHeight: 17, marginTop: 3 },
});

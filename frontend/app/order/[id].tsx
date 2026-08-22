import React, { useState } from "react";
import { Image, Linking, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { fileSource } from "@/src/api/upload";
import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { ErrorView } from "@/src/components/StateViews";
import { OrderTimeline, HistoryEntry } from "@/src/components/OrderTimeline";
import { OwnerDispatchPanel } from "@/src/components/OwnerDispatchPanel";
import { OrderData } from "@/src/components/OrderCard";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Detail = {
  order: OrderData & { customer_name?: string };
  contact_person?: string;
  contact_mobile?: string;
  notes?: string;
  pod?: {
    receiver_name?: string;
    delivered_quantity?: number;
    remarks?: string;
    photo_path?: string;
    signature?: string;
    at?: string;
  } | null;
  history: HistoryEntry[];
};

const CANCELLABLE = ["DRAFT", "PENDING", "ACCEPTED", "SCHEDULED"];

export default function OrderDetail() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { token, user } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();

  const isOwner = user?.role === "plant_owner";
  const base = isOwner ? "/owner/orders/" : "/customer/orders/";
  const { data, loading, error, reload } = useGet<Detail>(`${base}${id}`);

  const [busy, setBusy] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");

  const act = async (path: string, body?: any, msg?: string) => {
    setBusy(true);
    try {
      await apiPost(path, token!, body);
      toast(msg || "Done", "success");
      reload();
      setShowReject(false);
      setReason("");
    } catch (e: any) {
      toast(e.detail || "Action failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const o = data?.order;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="order-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">{o?.order_number || "Order"}</AppText>
      </View>

      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : loading && !data ? (
        <View style={{ padding: spacing.lg, gap: spacing.md }}>
          <Skeleton height={120} style={{ borderRadius: radius.lg }} />
          <Skeleton height={200} style={{ borderRadius: radius.lg }} />
        </View>
      ) : data && o ? (
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 40, gap: spacing.lg }} showsVerticalScrollIndicator={false}>
          {/* Status */}
          <Card style={{ gap: spacing.md }}>
            <View style={styles.rowBetween}>
              <View>
                <AppText variant="caption">Current status</AppText>
                <AppText style={{ fontFamily: fonts.displayBold, fontSize: fontSize["2xl"], color: colors.onSurface }}>
                  {o.status.replace(/_/g, " ")}
                </AppText>
              </View>
              <Badge label={o.payment_status} status={o.payment_status} />
            </View>
          </Card>

          {/* Summary */}
          <Card style={{ gap: spacing.sm }}>
            {isOwner && data.order.customer_name ? (
              <Row icon="person-outline" label="Customer" value={data.order.customer_name} colors={colors} />
            ) : null}
            <Row icon="business-outline" label="Plant" value={o.plant_name} colors={colors} />
            <Row icon="layers-outline" label="Grade" value={o.grade} colors={colors} />
            <Row icon="cube-outline" label="Quantity" value={`${o.quantity} m³`} colors={colors} />
            <Row icon="calendar-outline" label="Delivery" value={`${o.delivery_date}${o.delivery_time ? " · " + o.delivery_time : ""}`} colors={colors} />
            <Row icon="location-outline" label="Site" value={`${o.site_name}${o.site_address ? " — " + o.site_address : ""}`} colors={colors} />
            {data.contact_person ? <Row icon="call-outline" label="Contact" value={`${data.contact_person}${data.contact_mobile ? " · " + data.contact_mobile : ""}`} colors={colors} /> : null}
            {o.tm_number ? <Row icon="bus-outline" label="Transit Mixer" value={o.tm_number} colors={colors} /> : null}
            {o.driver_name ? <Row icon="person-outline" label="Driver" value={`${o.driver_name}${o.driver_mobile ? " · " + o.driver_mobile : ""}`} colors={colors} /> : null}
            {o.challan_number ? <Row icon="document-text-outline" label="Challan" value={o.challan_number} colors={colors} /> : null}
            {data.notes ? <Row icon="reader-outline" label="Notes" value={data.notes} colors={colors} /> : null}
          </Card>

          {/* Timeline */}
          <View style={{ gap: spacing.md }}>
            <AppText variant="heading">Order Timeline</AppText>
            <Card>
              <OrderTimeline history={data.history} />
            </Card>
          </View>

          {/* Proof of Delivery — shown to customer & owner once delivered */}
          {data.pod ? (
            <View style={{ gap: spacing.sm }}>
              <AppText variant="heading">Proof of Delivery</AppText>
              <Card style={{ gap: spacing.md }}>
                {data.pod.photo_path && token ? (
                  <Image
                    testID="pod-photo"
                    source={fileSource(data.pod.photo_path, token)}
                    style={styles.podPhoto}
                    resizeMode="cover"
                  />
                ) : null}
                <Row icon="person-outline" label="Received by" value={data.pod.receiver_name || "—"} colors={colors} />
                <Row icon="cube-outline" label="Delivered quantity" value={`${data.pod.delivered_quantity ?? o.quantity} m³`} colors={colors} />
                {data.pod.at ? <Row icon="time-outline" label="Delivered at" value={new Date(data.pod.at).toLocaleString()} colors={colors} /> : null}
                {data.pod.remarks ? <Row icon="chatbubble-ellipses-outline" label="Remarks" value={data.pod.remarks} colors={colors} /> : null}
                {data.pod.signature ? (
                  <View style={{ gap: 4 }}>
                    <AppText style={{ fontFamily: fonts.regular, fontSize: 11, color: colors.onSurfaceTertiary }}>Receiver signature</AppText>
                    <Image testID="pod-signature" source={{ uri: data.pod.signature }} style={[styles.podSign, { borderColor: colors.border }]} resizeMode="contain" />
                  </View>
                ) : null}
              </Card>
            </View>
          ) : null}

          {/* Actions */}
          {isOwner ? (
            o.status === "PENDING" ? (
              showReject ? (
                <Card style={{ gap: spacing.md }}>
                  <AppText variant="heading">Reject order</AppText>
                  <Input testID="reject-reason" label="Reason" value={reason} onChangeText={setReason} placeholder="Why are you rejecting?" autoCapitalize="sentences" />
                  <View style={{ flexDirection: "row", gap: spacing.sm }}>
                    <View style={{ flex: 1 }}>
                      <Button testID="reject-cancel" label="Back" variant="secondary" onPress={() => setShowReject(false)} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Button testID="reject-confirm" label="Confirm Reject" variant="danger" loading={busy} onPress={() => reason.trim() ? act(`/owner/orders/${id}/reject`, { reason: reason.trim() }, "Order rejected") : toast("Enter a reason", "error")} />
                    </View>
                  </View>
                </Card>
              ) : (
                <View style={{ flexDirection: "row", gap: spacing.sm }}>
                  <View style={{ flex: 1 }}>
                    <Button testID="owner-reject" label="Reject" variant="outline" onPress={() => setShowReject(true)} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Button testID="owner-approve" label="Approve" loading={busy} onPress={() => act(`/owner/orders/${id}/approve`, undefined, "Order approved")} icon={<Ionicons name="checkmark-circle-outline" size={18} color={colors.onBrand} />} />
                  </View>
                </View>
              )
            ) : (
              <OwnerDispatchPanel
                orderId={String(id)}
                status={o.status}
                quantity={o.quantity}
                tmNumber={o.tm_number}
                driverName={o.driver_name}
                challanNumber={o.challan_number}
                invoiceNumber={(o as any).invoice_number}
                onChanged={reload}
                onViewChallan={() => router.push(`/challan/${id}` as any)}
              />
            )
          ) : (
            <View style={{ gap: spacing.sm }}>
              {["DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING"].includes(o.status) ? (
                <Card style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center", backgroundColor: colors.brandSoft, borderColor: colors.brand + "55" }}>
                  <Ionicons name="navigate" size={18} color={colors.onBrandSoft} />
                  <AppText style={{ flex: 1, fontFamily: fonts.medium, fontSize: fontSize.sm, color: colors.onBrandSoft }}>
                    Your transit mixer is on the way. Live map tracking activates with the Maps key.
                  </AppText>
                </Card>
              ) : null}
              {["DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING"].includes(o.status) ? (
                <Button testID="order-track-live" label="Track Live" onPress={() => router.push(`/track/${id}` as any)} icon={<Ionicons name="navigate" size={18} color={colors.onBrand} />} />
              ) : null}
              {o.driver_mobile ? (
                <Button testID="order-call-driver" label="Call Driver" variant="secondary" onPress={() => Linking.openURL(`tel:${o.driver_mobile}`)} icon={<Ionicons name="call-outline" size={18} color={colors.onSurface} />} />
              ) : null}
              {o.challan_number ? (
                <Button testID="order-view-challan" label="View Challan" onPress={() => router.push(`/challan/${id}` as any)} icon={<Ionicons name="document-text-outline" size={18} color={colors.onBrand} />} />
              ) : null}
              {CANCELLABLE.includes(o.status) ? (
                <Button testID="order-cancel" label="Cancel Order" variant="outline" loading={busy} onPress={() => act(`/customer/orders/${id}/cancel`, undefined, "Order cancelled")} />
              ) : null}
            </View>
          )}
        </ScrollView>
      ) : null}
    </View>
  );
}

function Row({ icon, label, value, colors }: any) {
  return (
    <View style={styles.detailRow}>
      <Ionicons name={icon} size={16} color={colors.brand} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <AppText style={{ fontFamily: fonts.regular, fontSize: 11, color: colors.onSurfaceTertiary }}>{label}</AppText>
        <AppText style={{ fontFamily: fonts.medium, fontSize: fontSize.base, color: colors.onSurface }}>{value}</AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  detailRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  podPhoto: { width: "100%", height: 200, borderRadius: radius.md, backgroundColor: "#0002" },
  podSign: { width: "100%", height: 90, borderRadius: radius.sm, borderWidth: 1, backgroundColor: "#fff" },
});

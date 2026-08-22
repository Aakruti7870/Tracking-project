import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { apiGet, apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { useRouter } from "expo-router";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Vehicle = { id: string; tm_number: string; capacity_m3: number; status: string };
type Driver = { id: string; name: string; phone: string };

// Progressive dispatch workflow shown on the owner's order detail.
export function OwnerDispatchPanel({
  orderId,
  status,
  quantity,
  tmNumber,
  driverName,
  challanNumber,
  invoiceNumber,
  onChanged,
  onViewChallan,
}: {
  orderId: string;
  status: string;
  quantity?: number;
  tmNumber?: string | null;
  driverName?: string | null;
  challanNumber?: string | null;
  invoiceNumber?: string | null;
  onChanged: () => void;
  onViewChallan: () => void;
}) {
  const { colors } = useTheme();
  const { token } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [busy, setBusy] = useState(false);

  const needTm = status === "ACCEPTED" || status === "SCHEDULED" || status === "PRODUCTION_COMPLETE";
  const needDriver = status === "TM_ASSIGNED";
  const needChallan = status === "DRIVER_ASSIGNED";
  const needDispatch = status === "READY_TO_DISPATCH";

  useEffect(() => {
    if (!token) return;
    if (needTm) apiGet<{ vehicles: Vehicle[] }>("/owner/fleet", token).then((r) => setVehicles(r.vehicles)).catch(() => {});
    if (needDriver) apiGet<{ drivers: Driver[] }>("/owner/drivers", token).then((r) => setDrivers(r.drivers)).catch(() => {});
  }, [status, token]);

  const call = async (path: string, body: any, msg: string) => {
    setBusy(true);
    try {
      await apiPost(path, token!, body);
      toast(msg, "success");
      onChanged();
    } catch (e: any) {
      toast(e.detail || "Action failed", "error");
    } finally {
      setBusy(false);
    }
  };

  if (status === "PENDING" || status === "REJECTED" || status === "CANCELLED" || status === "DRAFT") return null;

  const inProduction = status === "IN_PRODUCTION";
  const delivered = ["DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING", "DELIVERED"].includes(status);

  return (
    <View style={{ gap: spacing.md }}>
      <AppText variant="heading">Dispatch</AppText>

      {/* Progress summary */}
      <Card style={{ gap: spacing.sm }}>
        <StepLine done={!!tmNumber} label="Transit Mixer" value={tmNumber || "Not assigned"} colors={colors} />
        <StepLine done={!!driverName} label="Driver" value={driverName || "Not assigned"} colors={colors} />
        <StepLine done={!!challanNumber} label="Challan" value={challanNumber || "Not generated"} colors={colors} />
        <StepLine done={delivered} label="Dispatched" value={delivered ? "Yes — tracking live" : "Pending"} colors={colors} />
      </Card>

      {/* Production board (optional path before assigning a mixer) */}
      {status === "ACCEPTED" ? (
        <Button testID="start-production" label="Start Production" variant="outline" loading={busy} onPress={() => call(`/owner/orders/${orderId}/production/start`, {}, "Production started")} icon={<Ionicons name="cog-outline" size={18} color={colors.onSurface} />} />
      ) : null}
      {inProduction ? (
        <Card style={{ gap: spacing.sm }}>
          <AppText variant="label">Production in progress</AppText>
          <Button testID="add-batch" label={`Add Batch${quantity ? ` (${quantity} m³)` : ""}`} variant="secondary" loading={busy} onPress={() => call(`/owner/orders/${orderId}/production/batch`, { quantity: quantity || 1 }, "Batch recorded")} icon={<Ionicons name="add-outline" size={18} color={colors.onSurface} />} />
          <Button testID="complete-production" label="Complete Production" loading={busy} onPress={() => call(`/owner/orders/${orderId}/production/complete`, {}, "Production complete")} />
        </Card>
      ) : null}

      {needTm ? (
        <Card style={{ gap: spacing.sm }}>
          <AppText variant="label">Select a Transit Mixer</AppText>
          {vehicles.length === 0 ? <AppText variant="caption">Loading fleet…</AppText> : null}
          {vehicles.map((v) => {
            const avail = v.status === "available";
            return (
              <Pressable
                key={v.id}
                testID={`assign-tm-${v.id}`}
                disabled={!avail || busy}
                onPress={() => call(`/owner/orders/${orderId}/assign-tm`, { vehicle_id: v.id }, `${v.tm_number} assigned`)}
                style={[styles.pick, { borderColor: colors.border, opacity: avail ? 1 : 0.45 }]}
              >
                <Ionicons name="bus-outline" size={20} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{v.tm_number}</AppText>
                  <AppText variant="caption">{v.capacity_m3} m³ · {v.status}</AppText>
                </View>
                {avail ? <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} /> : null}
              </Pressable>
            );
          })}
        </Card>
      ) : null}

      {needDriver ? (
        <Card style={{ gap: spacing.sm }}>
          <AppText variant="label">Assign a Driver</AppText>
          {drivers.length === 0 ? <AppText variant="caption">No drivers linked to this plant</AppText> : null}
          {drivers.map((d) => (
            <Pressable
              key={d.id}
              testID={`assign-driver-${d.id}`}
              disabled={busy}
              onPress={() => call(`/owner/orders/${orderId}/assign-driver`, { driver_id: d.id }, `${d.name} assigned`)}
              style={[styles.pick, { borderColor: colors.border }]}
            >
              <Ionicons name="person-outline" size={20} color={colors.brand} />
              <View style={{ flex: 1 }}>
                <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{d.name}</AppText>
                <AppText variant="caption">{d.phone}</AppText>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
            </Pressable>
          ))}
        </Card>
      ) : null}

      {needChallan ? (
        <Button testID="generate-challan" label="Generate Challan" loading={busy} onPress={() => call(`/owner/orders/${orderId}/challan`, {}, "Challan generated")} icon={<Ionicons name="document-text-outline" size={18} color={colors.onBrand} />} />
      ) : null}

      {needDispatch ? (
        <View style={{ gap: spacing.sm }}>
          <Button testID="view-challan" label="View Challan" variant="secondary" onPress={onViewChallan} />
          <Button testID="dispatch-order" label="Dispatch" loading={busy} onPress={() => call(`/owner/orders/${orderId}/dispatch`, undefined, "Dispatched — tracking is live")} icon={<Ionicons name="rocket-outline" size={18} color={colors.onBrand} />} />
        </View>
      ) : null}

      {delivered && challanNumber ? (
        <Button testID="view-challan" label="View Challan" variant="secondary" onPress={onViewChallan} icon={<Ionicons name="document-text-outline" size={18} color={colors.onSurface} />} />
      ) : null}

      {status === "DELIVERED" ? (
        <View style={{ gap: spacing.sm }}>
          {invoiceNumber ? (
            <Button testID="view-billing" label={`View Billing (${invoiceNumber})`} onPress={() => router.push("/owner/billing")} icon={<Ionicons name="wallet-outline" size={18} color={colors.onBrand} />} />
          ) : (
            <Button testID="generate-invoice" label="Generate Invoice" loading={busy} onPress={() => call(`/owner/orders/${orderId}/invoice`, {}, "Invoice generated")} icon={<Ionicons name="receipt-outline" size={18} color={colors.onBrand} />} />
          )}
        </View>
      ) : null}
    </View>
  );
}

function StepLine({ done, label, value, colors }: any) {
  return (
    <View style={styles.step}>
      <Ionicons name={done ? "checkmark-circle" : "ellipse-outline"} size={18} color={done ? colors.success : colors.onSurfaceTertiary} />
      <AppText style={{ fontFamily: fonts.medium, fontSize: fontSize.sm, color: colors.onSurfaceSecondary, width: 110 }}>{label}</AppText>
      <AppText style={{ flex: 1, fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }} numberOfLines={1}>{value}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  pick: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  step: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
});

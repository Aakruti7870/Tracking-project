import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiGet } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Card } from "@/src/components/ui/Card";
import { ErrorView } from "@/src/components/StateViews";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Online = { order_number: string; plant_name: string; product: string; plan: string; status: string; payable: number; discount: number; promo_code?: string; payment_reference?: string; created_at?: string; paid_at?: string };
type Activation = { id: string; plant_name: string; product: string; plan: string; status: string; activation_mode: string; price: number; discount: number; payable: number; promo_code?: string; payment_reference?: string; reason?: string; activated_by?: string; starts_at?: string; ends_at?: string; created_at?: string };
type Promo = { id: string; code: string; product: string; discount_type: string; discount_value: number; uses: number; max_uses?: number; active: boolean; ends_at?: string; created_by?: string };
type Audit = { id: string; actor_id?: string; action: string; plant_name?: string; meta: Record<string, unknown>; created_at?: string };
type Data = { online_payments: Online[]; activations: Activation[]; promo_codes: Promo[]; audit: Audit[] };
type Tab = "ONLINE" | "ACTIVATIONS" | "PROMOS" | "AUDIT";
type Status = "ALL" | "PAID" | "PAYMENT_PENDING" | "FAILED" | "USER_DROPPED";

const money = (value: number) => `₹${Number(value || 0).toLocaleString("en-IN")}`;
const pretty = (value?: string) => (value || "").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (m) => m.toUpperCase());
const date = (value?: string) => value ? new Date(value).toLocaleString("en-IN") : "—";
const badgeStatus = (status: string) => status === "PAID" || status === "ACTIVE" ? "DELIVERED" : status === "FAILED" || status === "USER_DROPPED" || status === "SUPERSEDED" ? "CANCELLED" : "PENDING";

export default function AuthorityPaymentControl() {
  const { colors } = useTheme();
  const { token } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<Tab>("ONLINE");
  const [status, setStatus] = useState<Status>("ALL");
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (refresh = false) => {
    if (!token) return;
    refresh ? setRefreshing(true) : setLoading(true);
    setError("");
    try { setData(await apiGet<Data>("/plant-plans/authority-control", token)); }
    catch (e: any) { setError(e.detail || "Could not load Authority payment control"); }
    finally { setLoading(false); setRefreshing(false); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const online = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.online_payments || []).filter((row) =>
      (status === "ALL" || row.status === status) &&
      (!q || [row.plant_name, row.order_number, row.payment_reference, row.product, row.plan].some((v) => v?.toLowerCase().includes(q)))
    );
  }, [data, query, status]);
  const activations = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.activations || []).filter((row) => !q || [row.plant_name, row.payment_reference, row.activation_mode, row.product, row.plan].some((v) => v?.toLowerCase().includes(q)));
  }, [data, query]);
  const paidTotal = (data?.online_payments || []).filter((p) => p.status === "PAID").reduce((sum, p) => sum + p.payable, 0);
  const pending = (data?.online_payments || []).filter((p) => p.status === "PAYMENT_PENDING").length;

  if (error && !data) return <ErrorView message={error} onRetry={() => load()} />;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <View style={styles.header}>
        <Pressable testID="authority-payment-back" onPress={() => router.back()} hitSlop={10}><Ionicons name="arrow-back" size={24} color="#FFFFFF" /></Pressable>
        <View style={{ flex: 1 }}><AppText style={styles.headerTitle}>Payment & Plan Control</AppText><AppText style={styles.headerSub}>Authority financial oversight</AppText></View>
        <Ionicons name="shield-checkmark-outline" size={26} color="#FF6A00" />
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 90, gap: spacing.lg }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.brand} />}>
        <View style={styles.summary}>
          <Card style={{ flex: 1, gap: 4 }}><AppText variant="caption">Cashfree verified</AppText><AppText style={[styles.total, { color: colors.success }]}>{money(paidTotal)}</AppText></Card>
          <Card style={{ flex: 1, gap: 4 }}><AppText variant="caption">Pending</AppText><AppText style={[styles.total, { color: colors.warning }]}>{pending}</AppText></Card>
        </View>

        <View style={[styles.safety, { borderColor: colors.border }]}>
          <Ionicons name="lock-closed-outline" size={18} color={colors.brand} />
          <AppText variant="caption" style={{ flex: 1 }}>Read-only financial control. Online Cashfree orders can become Paid only through a verified signed webhook.</AppText>
        </View>

        <View style={[styles.search, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
          <Ionicons name="search-outline" size={19} color={colors.onSurfaceTertiary} />
          <TextInput value={query} onChangeText={setQuery} placeholder="Search plant, order or transaction ID" placeholderTextColor={colors.onSurfaceTertiary} style={{ flex: 1, color: colors.onSurface, fontFamily: fonts.medium }} />
          {query ? <Pressable onPress={() => setQuery("")}><Ionicons name="close-circle" size={19} color={colors.onSurfaceTertiary} /></Pressable> : null}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
          {([
            ["ONLINE", "Online Payments"], ["ACTIVATIONS", "Plan Activations"], ["PROMOS", "Promo Usage"], ["AUDIT", "Audit History"],
          ] as [Tab, string][]).map(([key, label]) => <Chip key={key} label={label} selected={tab === key} onPress={() => setTab(key)} />)}
        </ScrollView>

        {tab === "ONLINE" ? (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
              {(["ALL", "PAID", "PAYMENT_PENDING", "FAILED", "USER_DROPPED"] as Status[]).map((value) => <Chip key={value} label={pretty(value)} selected={status === value} onPress={() => setStatus(value)} />)}
            </ScrollView>
            {loading && !data ? <><Skeleton height={150} /><Skeleton height={150} /></> : online.length ? online.map((row) => (
              <Card key={row.order_number} style={{ gap: spacing.md }}>
                <View style={styles.line}><View style={{ flex: 1 }}><AppText variant="heading" numberOfLines={1}>{row.plant_name}</AppText><AppText variant="caption">{pretty(row.product)} · {pretty(row.plan)}</AppText></View><Badge label={pretty(row.status)} status={badgeStatus(row.status)} /></View>
                <View style={[styles.amountBox, { backgroundColor: colors.surfaceTertiary }]}><AppText style={styles.amount}>{money(row.payable)}</AppText>{row.discount ? <AppText style={{ color: colors.success }}>−{money(row.discount)} discount</AppText> : null}</View>
                <Detail label="Order ID" value={row.order_number} />
                <Detail label="Created" value={date(row.created_at)} />
                {row.paid_at ? <Detail label="Cashfree verified" value={date(row.paid_at)} /> : null}
                {row.payment_reference ? <Detail label="Transaction reference" value={row.payment_reference} /> : null}
                {row.promo_code ? <Detail label="Promo code" value={row.promo_code} /> : null}
              </Card>
            )) : <Empty label="No online payments found" />}
          </>
        ) : tab === "ACTIVATIONS" ? (
          activations.length ? activations.map((row) => (
            <Card key={row.id} style={{ gap: spacing.md }}>
              <View style={styles.line}><View style={{ flex: 1 }}><AppText variant="heading" numberOfLines={1}>{row.plant_name}</AppText><AppText variant="caption">{pretty(row.product)} · {pretty(row.plan)}</AppText></View><Badge label={pretty(row.activation_mode)} status={row.status === "ACTIVE" ? "DELIVERED" : "PENDING"} /></View>
              <Detail label="Plan status" value={pretty(row.status)} />
              <Detail label="Start" value={date(row.starts_at)} />
              <Detail label="Expiry" value={date(row.ends_at)} />
              <Detail label="Payable" value={money(row.payable)} />
              {row.payment_reference ? <Detail label="Payment reference" value={row.payment_reference} /> : null}
              {row.reason ? <Detail label="Authority reason" value={row.reason} /> : null}
              {row.promo_code ? <Detail label="Promo code" value={row.promo_code} /> : null}
              <Detail label="Activated by" value={row.activated_by || "—"} />
            </Card>
          )) : <Empty label="No plan activations found" />
        ) : tab === "PROMOS" ? (
          (data?.promo_codes || []).length ? data!.promo_codes.filter((row) => !query || row.code.toLowerCase().includes(query.toLowerCase())).map((row) => (
            <Card key={row.id} style={{ gap: spacing.sm }}>
              <View style={styles.line}><AppText variant="heading">{row.code}</AppText><Badge label={row.active ? "Active" : "Inactive"} status={row.active ? "DELIVERED" : "CANCELLED"} /></View>
              <Detail label="Product" value={pretty(row.product)} />
              <Detail label="Discount" value={row.discount_type === "PERCENT" ? `${row.discount_value}%` : money(row.discount_value)} />
              <Detail label="Usage" value={`${row.uses} / ${row.max_uses ?? "Unlimited"}`} />
              <Detail label="Expiry" value={date(row.ends_at)} />
            </Card>
          )) : <Empty label="No promo codes found" />
        ) : (
          (data?.audit || []).length ? data!.audit.filter((row) => !query || [row.plant_name, row.actor_id, row.action].some((v) => v?.toLowerCase().includes(query.toLowerCase()))).map((row) => (
            <Card key={row.id} style={{ gap: spacing.sm }}>
              <View style={styles.line}><AppText variant="heading">{pretty(row.action)}</AppText><Ionicons name="document-text-outline" size={20} color={colors.brand} /></View>
              {row.plant_name ? <Detail label="Plant" value={row.plant_name} /> : null}
              <Detail label="Actor" value={row.actor_id || "System"} />
              <Detail label="Time" value={date(row.created_at)} />
            </Card>
          )) : <Empty label="No payment audit records found" />
        )}
      </ScrollView>
    </View>
  );
}

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress(): void }) {
  const { colors } = useTheme();
  return <Pressable onPress={onPress} style={[styles.chip, { backgroundColor: selected ? colors.brand : colors.surfaceSecondary, borderColor: selected ? colors.brand : colors.border }]}><AppText style={{ fontFamily: fonts.semibold, color: selected ? colors.onBrand : colors.onSurface }}>{label}</AppText></Pressable>;
}
function Detail({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return <View style={styles.line}><AppText variant="caption">{label}</AppText><AppText selectable style={{ maxWidth: "62%", textAlign: "right", color: colors.onSurface, fontFamily: fonts.medium, fontSize: fontSize.sm }}>{value}</AppText></View>;
}
function Empty({ label }: { label: string }) {
  const { colors } = useTheme();
  return <Card style={{ alignItems: "center", gap: spacing.sm, paddingVertical: spacing["2xl"] }}><Ionicons name="file-tray-outline" size={32} color={colors.onSurfaceTertiary} /><AppText variant="heading">{label}</AppText></Card>;
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, paddingTop: spacing.md, backgroundColor: "#01153E" },
  headerTitle: { color: "#FFFFFF", fontFamily: fonts.displayBold, fontSize: fontSize.xl },
  headerSub: { color: "rgba(255,255,255,.7)", fontFamily: fonts.regular, fontSize: 12 },
  summary: { flexDirection: "row", gap: spacing.sm },
  total: { fontFamily: fonts.displayBold, fontSize: fontSize.xl },
  safety: { flexDirection: "row", gap: spacing.sm, borderWidth: 1, borderRadius: radius.md, padding: spacing.md },
  search: { height: 48, flexDirection: "row", alignItems: "center", gap: spacing.sm, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md },
  chip: { minHeight: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  line: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  amountBox: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: spacing.md, borderRadius: radius.md },
  amount: { fontFamily: fonts.displayBold, fontSize: fontSize["2xl"] },
});

import React, { useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { apiErrorDetail, apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import type { OrderData } from "@/src/components/OrderCard";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";
import { supportActionRoute, type SupportAction } from "@/src/support/routes";

type Category = "LOGIN" | "KYC" | "ORDER" | "TRACKING" | "PAYMENT" | "ACCOUNT_DELETION" | "PLANT_ONBOARDING" | "GENERAL";
type Reply = { category: Category; guidance: string; action: SupportAction; order?: OrderData; case_id?: string; case_number?: string; case_status?: string };
type CaseMessage = { message: string; author: string; created_at?: string };
type SupportCase = { id: string; case_number: string; category: Category; status: string; created_at: string; order_id?: string; latest_note?: string; messages?: CaseMessage[] };

const ISSUES: { category: Category; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
  { category: "LOGIN", label: "Login Issue", icon: "log-in-outline" }, { category: "KYC", label: "KYC Issue", icon: "id-card-outline" },
  { category: "ORDER", label: "Order Issue", icon: "cube-outline" }, { category: "TRACKING", label: "Track Delivery", icon: "navigate-outline" },
  { category: "PAYMENT", label: "Payment Issue", icon: "card-outline" }, { category: "ACCOUNT_DELETION", label: "Account Issue", icon: "person-outline" },
  { category: "PLANT_ONBOARDING", label: "Plant Onboarding", icon: "business-outline" }, { category: "GENERAL", label: "Other Issue", icon: "help-circle-outline" },
];

const newEscalationId = () => `support-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export default function Support() {
  const { colors } = useTheme(); const insets = useSafeAreaInsets(); const router = useRouter(); const { token } = useAuth();
  const [category, setCategory] = useState<Category | null>(null); const [message, setMessage] = useState("");
  const [orderId, setOrderId] = useState<string | null>(null); const [reply, setReply] = useState<Reply | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null); const [caseReply, setCaseReply] = useState("");
  const [replying, setReplying] = useState(false); const [caseError, setCaseError] = useState<string | null>(null);
  const escalationId = useRef(newEscalationId());
  const orders = useGet<{ orders: OrderData[] }>(token && (category === "ORDER" || category === "TRACKING") ? "/customer/orders" : null);
  const cases = useGet<{ cases: SupportCase[] }>(token ? "/assistant/support/cases" : null);
  const caseDetail = useGet<{ case: SupportCase }>(token && selectedCaseId ? `/assistant/support/cases/${selectedCaseId}` : null);
  const selectedOrder = useMemo(() => orders.data?.orders.find((o) => o.id === orderId), [orders.data, orderId]);
  const actionRoute = reply ? supportActionRoute(reply.action, orderId) : null;

  async function send(escalate = false) {
    if (!token || !category || !message.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const result = await apiPost<Reply>("/assistant/support", token, { category, message: message.trim(), order_id: orderId, escalate,
        request_id: escalate ? escalationId.current : undefined });
      setReply(result);
      if (escalate) {
        // Keep the same key across retries, but rotate it immediately after a
        // successful case creation so the next distinct issue creates a new case.
        escalationId.current = newEscalationId();
        await cases.refetch();
      }
    } catch (e) { setError(apiErrorDetail(e, "Unable to reach support. Check your connection and retry.")); }
    finally { setBusy(false); }
  }
  function openAction() { if (actionRoute) router.push(actionRoute as never); }
  async function sendCaseReply() {
    if (!token || !selectedCaseId || !caseReply.trim() || replying) return;
    setReplying(true); setCaseError(null);
    try {
      await apiPost(`/assistant/support/cases/${selectedCaseId}/replies`, token, { message: caseReply.trim(), internal: false });
      setCaseReply(""); await Promise.all([caseDetail.refetch(), cases.refetch()]);
    } catch (e) { setCaseError(apiErrorDetail(e, "Unable to send your reply. Check your connection and retry.")); }
    finally { setReplying(false); }
  }

  return <View style={{ flex: 1, backgroundColor: colors.surface }}><View style={{ height: insets.top }} />
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.page}>
      <View style={{ gap: spacing.sm }}><AppText variant="title">TrackMyRMC Support</AppText><AppText variant="bodyMuted">How can we help you today?</AppText>
        <Button testID="support-place-order" label="Place Order with Agent" variant="outline" onPress={() => router.push("/new-order?assistant=1" as never)}
          accessibilityHint="Prepares an order for review and requires explicit confirmation before placement" />
      </View>
      <View style={styles.grid}>{ISSUES.map((item) => <Pressable key={item.category} testID={`support-category-${item.category}`}
        accessibilityRole="button" onPress={() => { setCategory(item.category); setReply(null); setError(null); setOrderId(null); }}
        style={[styles.issue, { backgroundColor: category === item.category ? colors.brandSoft : colors.surfaceSecondary, borderColor: category === item.category ? colors.brand : colors.border }]}>
        <Ionicons name={item.icon} size={22} color={colors.brand} /><AppText variant="label">{item.label}</AppText></Pressable>)}</View>

      {(category === "ORDER" || category === "TRACKING") && <Card style={{ gap: spacing.sm }}><AppText variant="heading">Choose one of your orders</AppText>
        {orders.loading ? <AppText variant="bodyMuted">Loading your orders…</AppText> : orders.error ? <Button label="Retry loading orders" variant="outline" onPress={orders.reload} /> :
          orders.data?.orders.map((order) => <Pressable key={order.id} testID={`support-order-${order.id}`} onPress={() => setOrderId(order.id)}
            style={[styles.order, { borderColor: orderId === order.id ? colors.brand : colors.border, backgroundColor: colors.surfaceSecondary }]}>
            <AppText variant="label">{order.order_number} · {order.grade} · {order.quantity} m³</AppText>
            <AppText variant="caption">{order.plant_name} · {order.status.replace(/_/g, " ")} · {order.payment_status}</AppText></Pressable>)}</Card>}

      {category && <Card style={{ gap: spacing.md }}><AppText variant="heading">Tell us what happened</AppText>
        <TextInput testID="support-message" value={message} onChangeText={setMessage} multiline maxLength={1000}
          placeholder="Do not include passwords, OTPs, passkeys, recovery codes or payment credentials."
          placeholderTextColor={colors.onSurfaceTertiary} style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
        {error && <AppText style={{ color: colors.error }}>{error}</AppText>}
        <Button testID="support-send" label="Ask Support Agent" loading={busy} disabled={!message.trim() || ((category === "ORDER" || category === "TRACKING") && !orderId)} onPress={() => send(false)} />
      </Card>}

      {reply && <View style={[styles.agentBubble, { backgroundColor: colors.brandSoft }]}><AppText variant="eyebrow">SUPPORT AGENT</AppText>
        <AppText>{reply.guidance}</AppText>{selectedOrder && <AppText variant="caption">Authorized order: {selectedOrder.order_number} · {selectedOrder.status}</AppText>}
        {actionRoute ? <Button testID="support-open-secure-screen" label="Open secure screen" variant="outline" onPress={openAction} /> : null}
        {!reply.case_id ? <Button testID="support-escalate" label="Create Support Case" loading={busy} onPress={() => send(true)} /> :
          <Card testID="support-case-confirmation"><AppText variant="heading">Support case created</AppText><AppText>{reply.case_number || reply.case_id}</AppText><AppText variant="caption">{reply.category} · {reply.case_status || "OPEN"}</AppText></Card>}
      </View>}

      <View style={{ gap: spacing.sm }}><AppText variant="heading">My Support Cases</AppText>
        {cases.loading ? <AppText variant="bodyMuted">Loading cases…</AppText> : cases.error ? <Button label="Retry" variant="outline" onPress={cases.reload} /> :
          cases.data?.cases.length ? cases.data.cases.map((item) => <Pressable key={item.id} testID={`support-case-${item.id}`} onPress={() => { setSelectedCaseId(item.id); setCaseError(null); }}><Card style={{ gap: 4 }}><AppText variant="label">{item.case_number}</AppText>
            <AppText variant="caption">{item.category.replace(/_/g, " ")} · {item.status.replace(/_/g, " ")}</AppText>
            <AppText variant="caption">{new Date(item.created_at).toLocaleString()}</AppText>{item.latest_note ? <AppText numberOfLines={2}>{item.latest_note}</AppText> : null}</Card></Pressable>) :
          <AppText variant="bodyMuted">You have no support cases.</AppText>}</View>

      {selectedCaseId && <Card testID="support-case-detail" style={{ gap: spacing.md }}>
        {caseDetail.loading ? <AppText variant="bodyMuted">Loading conversation…</AppText> : caseDetail.error ? <Button label="Retry conversation" variant="outline" onPress={caseDetail.reload} /> : caseDetail.data ? <>
          <AppText variant="heading">{caseDetail.data.case.case_number}</AppText>
          <AppText variant="caption">{caseDetail.data.case.category.replace(/_/g, " ")} · {caseDetail.data.case.status.replace(/_/g, " ")}</AppText>
          <AppText variant="caption">Created {new Date(caseDetail.data.case.created_at).toLocaleString()}</AppText>
          {caseDetail.data.case.order_id ? <AppText variant="caption">Related order: {caseDetail.data.case.order_id}</AppText> : null}
          {(caseDetail.data.case.messages || []).map((item, index) => <View key={`${item.created_at || index}-${index}`} style={[styles.messageBubble, { backgroundColor: colors.surfaceSecondary }]}>
            <AppText variant="eyebrow">{item.author === "CUSTOMER" ? "YOU" : "SUPPORT"}</AppText><AppText>{item.message}</AppText>
          </View>)}
          {caseDetail.data.case.status === "OPEN" || caseDetail.data.case.status === "IN_PROGRESS" ? <>
            <TextInput testID="support-case-reply" value={caseReply} onChangeText={setCaseReply} multiline maxLength={1000} placeholder="Reply without sharing credentials" placeholderTextColor={colors.onSurfaceTertiary}
              style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
            {caseError ? <AppText style={{ color: colors.error }}>{caseError}</AppText> : null}
            <Button testID="support-case-send-reply" label="Send Reply" loading={replying} disabled={!caseReply.trim() || replying} onPress={sendCaseReply} />
          </> : <AppText testID="support-case-reply-disabled" variant="bodyMuted">This case is closed for replies.</AppText>}
        </> : null}
      </Card>}
    </ScrollView></View>;
}

const styles = StyleSheet.create({ page: { padding: spacing.lg, paddingBottom: 100, gap: spacing.lg }, grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  issue: { width: "48%", minHeight: 72, padding: spacing.md, borderWidth: 1, borderRadius: radius.lg, gap: spacing.xs, justifyContent: "center" },
  order: { padding: spacing.md, borderWidth: 1, borderRadius: radius.md, gap: 3 }, input: { minHeight: 112, borderWidth: 1, borderRadius: radius.md, padding: spacing.md, textAlignVertical: "top", fontFamily: fonts.regular },
  agentBubble: { alignSelf: "stretch", padding: spacing.lg, borderRadius: radius.xl, gap: spacing.md }, messageBubble: { padding: spacing.md, borderRadius: radius.md, gap: spacing.xs } });

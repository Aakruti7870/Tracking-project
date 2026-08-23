import React, { useState } from "react";
import { Modal, RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { useTheme } from "@/src/theme/ThemeProvider";
import { radius, spacing } from "@/src/theme/tokens";

type Deletion = {
  id: string;
  user_id: string;
  user_name?: string;
  role?: string;
  status: string;
  reason?: string | null;
  created_at?: string | null;
  completion_note?: string | null;
};

export default function AccountDeletionAdmin() {
  const { token } = useAuth();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { data, loading, refetch } = useGet<{ requests: Deletion[] }>("/account-deletion/requests");
  const [selected, setSelected] = useState<Deletion | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const complete = async () => {
    if (!token || !selected) return;
    if (note.trim().length < 3) return toast("Enter a completion note", "error");
    setBusy(true);
    try {
      await apiPost(`/account-deletion/requests/${selected.id}/complete`, token, { note: note.trim() });
      toast("Account deletion completed", "success");
      setSelected(null); setNote(""); refetch();
    } catch (e: any) { toast(e.detail || "Completion failed", "error"); }
    finally { setBusy(false); }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }} refreshControl={<RefreshControl refreshing={false} onRefresh={refetch} tintColor={colors.brand} />}>
        <View><AppText variant="title">Account Deletion Requests</AppText><AppText variant="caption">Central Admin review and completion</AppText></View>
        {loading && !data ? <><Skeleton height={100} /><Skeleton height={100} /></> : null}
        {data?.requests.map((r) => (
          <Card key={r.id} style={{ gap: spacing.sm }}>
            <AppText variant="heading">{r.user_name || r.user_id}</AppText>
            <AppText variant="caption">{r.role || "user"} · {r.status} · {r.created_at ? new Date(r.created_at).toLocaleString() : ""}</AppText>
            {r.reason ? <AppText variant="caption">Reason: {r.reason}</AppText> : null}
            {r.completion_note ? <AppText variant="caption">Completion: {r.completion_note}</AppText> : null}
            {r.status === "PENDING" ? <Button label="Complete Deletion" onPress={() => { setSelected(r); setNote(""); }} /> : null}
          </Card>
        ))}
        {data && data.requests.length === 0 ? <Card><AppText variant="bodyMuted">No deletion requests.</AppText></Card> : null}
      </ScrollView>

      <Modal visible={!!selected} transparent animationType="fade" onRequestClose={() => setSelected(null)}>
        <View style={{ flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.45)" }}>
          <View style={{ backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: spacing.lg, gap: spacing.md }}>
            <AppText variant="heading">Complete deletion</AppText>
            <AppText variant="caption">The user identity will be anonymized and sessions revoked. Plant owners must first transfer or disable owned plants.</AppText>
            <Input label="Completion note" value={note} onChangeText={setNote} placeholder="Checks completed / retention basis" />
            <Button label="Confirm Completion" onPress={complete} loading={busy} />
            <Button label="Cancel" variant="outline" onPress={() => setSelected(null)} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

import React, { useState } from "react";
import { ScrollView, View } from "react-native";
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
import { spacing } from "@/src/theme/tokens";

type Request = {
  id: string;
  status: string;
  reason?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
};

export default function AccountDeletion() {
  const { token } = useAuth();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { data, loading, refetch } = useGet<{ request: Request | null }>("/account-deletion/status");
  const [confirm, setConfirm] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const requestDeletion = async () => {
    if (!token) return;
    if (confirm.trim().toUpperCase() !== "DELETE") return toast("Type DELETE to confirm", "error");
    setBusy(true);
    try {
      await apiPost("/account-deletion/request", token, { confirm: "DELETE", reason: reason.trim() || null });
      toast("Deletion request submitted", "success");
      setConfirm("");
      refetch();
    } catch (e: any) { toast(e.detail || "Request failed", "error"); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!token) return;
    setBusy(true);
    try {
      await apiPost("/account-deletion/cancel", token);
      toast("Deletion request cancelled", "success");
      refetch();
    } catch (e: any) { toast(e.detail || "Cancel failed", "error"); }
    finally { setBusy(false); }
  };

  const req = data?.request;
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }}>
        <View style={{ gap: 4 }}>
          <AppText variant="title">Account Deletion</AppText>
          <AppText variant="caption">Request deletion of your TrackMyRMC login and personal account data.</AppText>
        </View>

        {loading && !data ? <Skeleton height={120} /> : null}

        {req?.status === "PENDING" ? (
          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Deletion request pending</AppText>
            <AppText variant="bodyMuted">Submitted {req.created_at ? new Date(req.created_at).toLocaleString() : "recently"}.</AppText>
            {req.reason ? <AppText variant="caption">Reason: {req.reason}</AppText> : null}
            <AppText variant="caption">You can cancel the request until it is completed. Business transaction records that must be retained for legal/accounting obligations may remain in anonymized form.</AppText>
            <Button label="Cancel deletion request" variant="outline" onPress={cancel} loading={busy} />
          </Card>
        ) : (
          <>
            <Card style={{ gap: spacing.sm }}>
              <AppText variant="heading">Before requesting deletion</AppText>
              <AppText variant="caption">Your sign-in identity and personal profile will be removed when the request is completed. Orders, challans, invoices or other statutory transaction records may be retained in anonymized form where required.</AppText>
              <AppText variant="caption">Plant owners must transfer or disable owned plants before deletion can be completed.</AppText>
            </Card>
            <Input label="Reason (optional)" value={reason} onChangeText={setReason} placeholder="Why are you deleting your account?" />
            <Input label='Type "DELETE" to confirm' value={confirm} onChangeText={setConfirm} autoCapitalize="characters" />
            <Button label="Request Account Deletion" onPress={requestDeletion} loading={busy} />
          </>
        )}
      </ScrollView>
    </View>
  );
}

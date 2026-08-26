import React, { useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { apiPublicPost, requestOtp } from "@/src/api/client";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { useToast } from "@/src/components/ui/Toast";
import { useTheme } from "@/src/theme/ThemeProvider";
import { spacing } from "@/src/theme/tokens";

export default function PublicAccountDeletion() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const toast = useToast();
  const [phase, setPhase] = useState<"identify" | "verify" | "done">("identify");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const sendOtp = async () => {
    if (identifier.trim().length < 3) return toast("Enter your registered mobile number or email", "error");
    setBusy(true);
    try {
      const res = await requestOtp(identifier.trim());
      if (res.dev_otp) setCode(res.dev_otp);
      setPhase("verify");
      toast(`Verification code sent via ${res.channel === "email" ? "email" : "SMS"}`, "success");
    } catch (e: any) { toast(e.detail || "Could not send verification code", "error"); }
    finally { setBusy(false); }
  };

  const submit = async () => {
    if (confirm.trim().toUpperCase() !== "DELETE") return toast("Type DELETE to confirm", "error");
    if (code.trim().length < 4) return toast("Enter the verification code", "error");
    setBusy(true);
    try {
      await apiPublicPost("/account-deletion/public-request", {
        identifier: identifier.trim(),
        code: code.trim(),
        confirm: "DELETE",
        reason: reason.trim() || null,
      });
      setPhase("done");
    } catch (e: any) { toast(e.detail || "Deletion request failed", "error"); }
    finally { setBusy(false); }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 80, gap: spacing.lg }}>
        <AppText variant="title">Delete Account</AppText>
        <AppText variant="bodyMuted">You can request deletion without signing in. We verify ownership first using a one-time code sent to your registered mobile number or email.</AppText>

        {phase === "identify" ? <>
          <Card style={{ gap: spacing.sm }}>
            <AppText variant="heading">What deletion does</AppText>
            <AppText variant="caption">Your sign-in identity and personal profile are removed when the request is completed. Orders, challans, invoices and other statutory transaction records may be retained in anonymized form where legally required.</AppText>
          </Card>
          <Input label="Registered mobile number or email" value={identifier} onChangeText={setIdentifier} keyboardType="email-address" />
          <Button label="Send verification code" onPress={sendOtp} loading={busy} />
        </> : null}

        {phase === "verify" ? <>
          <Input label="Verification code" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={8} />
          <Input label="Reason (optional)" value={reason} onChangeText={setReason} />
          <Input label='Type "DELETE" to confirm' value={confirm} onChangeText={setConfirm} autoCapitalize="characters" />
          <Button label="Request Account Deletion" onPress={submit} loading={busy} />
          <Button label="Change mobile/email" variant="outline" onPress={() => setPhase("identify")} />
        </> : null}

        {phase === "done" ? <Card style={{ gap: spacing.md }}>
          <AppText variant="heading">Deletion request submitted</AppText>
          <AppText variant="bodyMuted">Your request has been recorded for completion. Any active sessions will be revoked when deletion is completed.</AppText>
          <Button label="Back to Sign in" onPress={() => router.replace("/login")} />
        </Card> : null}
      </ScrollView>
    </View>
  );
}

import React, { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import {
  KeyboardAwareScrollView,
} from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";

import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Input } from "@/src/components/ui/Input";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const HERO =
  "https://images.pexels.com/photos/12519386/pexels-photo-12519386.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function Login() {
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { requestOtp, verify } = useAuth();

  const [phase, setPhase] = useState<"enter" | "otp">("enter");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  const startCountdown = (secs: number) => {
    setCountdown(secs);
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1 && timer.current) {
          clearInterval(timer.current);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const handleSendOtp = async () => {
    setError(null);
    if (identifier.trim().length < 3) {
      setError("Enter your mobile number or email");
      return;
    }
    setLoading(true);
    try {
      const res = await requestOtp(identifier.trim());
      setDevOtp(res.dev_otp ?? null);
      if (res.dev_otp) setCode(res.dev_otp);
      setPhase("otp");
      startCountdown(30);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`OTP sent via ${res.channel === "email" ? "email" : "SMS"}`, "success");
    } catch (e: any) {
      setError(e.detail || "Could not send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0) return;
    await handleSendOtp();
  };

  const handleVerify = async () => {
    setError(null);
    if (code.trim().length < 4) {
      setError("Enter the OTP you received");
      return;
    }
    setLoading(true);
    try {
      const me = await verify(identifier.trim(), code.trim());
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`Welcome, ${me.name}`, "success");
      router.replace("/");
    } catch (e: any) {
      setError(e.detail || "Invalid OTP");
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style="light" />
      <KeyboardAwareScrollView
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ flexGrow: 1 }}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero */}
        <View style={styles.hero}>
          <Image source={{ uri: HERO }} style={StyleSheet.absoluteFill} contentFit="cover" />
          <LinearGradient
            colors={["rgba(18,18,18,0.35)", "rgba(18,18,18,0.75)", colors.surface]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.brandWrap, { paddingTop: insets.top + spacing.xl }]}>
            <View style={[styles.logoBadge, { backgroundColor: colors.brand }]}>
              <Ionicons name="cube" size={22} color="#121212" />
            </View>
            <AppText style={styles.brand} color="#FFFFFF">
              TRACK MY RMC
            </AppText>
            <AppText variant="caption" color="rgba(255,255,255,0.8)" style={{ marginTop: 2 }}>
              Ready-Mix Concrete · Order · Dispatch · Deliver
            </AppText>
          </View>
        </View>

        {/* Card */}
        <View style={[styles.card, { backgroundColor: colors.surface }]}>
          <AppText variant="title">{phase === "enter" ? "Sign in" : "Verify OTP"}</AppText>
          <AppText variant="bodyMuted" style={{ marginTop: spacing.xs, marginBottom: spacing.xl }}>
            {phase === "enter"
              ? "One login for everyone. We'll detect your role automatically."
              : `Enter the 6-digit code sent to ${identifier}`}
          </AppText>

          {phase === "enter" ? (
            <View style={{ gap: spacing.lg }}>
              <Input
                testID="login-identifier-input"
                label="Mobile number or email"
                value={identifier}
                onChangeText={(t) => {
                  setIdentifier(t);
                  setError(null);
                }}
                placeholder="+91 90000 00001  or  admin@…"
                keyboardType="email-address"
                autoFocus
                error={error}
              />
              <Button
                testID="login-send-otp-button"
                label="Send OTP"
                onPress={handleSendOtp}
                loading={loading}
                icon={<Ionicons name="paper-plane-outline" size={18} color={colors.onBrand} />}
              />
              <View style={[styles.hintRow, { borderColor: colors.border }]}>
                <Ionicons name="information-circle-outline" size={16} color={colors.onSurfaceTertiary} />
                <AppText variant="caption" style={{ flex: 1 }}>
                  Customers & drivers sign in with mobile OTP · Staff, authority & admin use email OTP.
                </AppText>
              </View>
            </View>
          ) : (
            <View style={{ gap: spacing.lg }}>
              <Input
                testID="login-otp-input"
                label="One-time password"
                value={code}
                onChangeText={(t) => {
                  setCode(t.replace(/[^0-9]/g, ""));
                  setError(null);
                }}
                placeholder="••••••"
                keyboardType="number-pad"
                maxLength={6}
                center
                autoFocus
                error={error}
              />

              {devOtp ? (
                <View style={[styles.devHint, { backgroundColor: colors.brandSoft }]}>
                  <Ionicons name="flask-outline" size={16} color={colors.onBrandSoft} />
                  <AppText style={{ color: colors.onBrandSoft, fontFamily: fonts.medium, fontSize: fontSize.sm }}>
                    Dev mode — OTP auto-filled ({devOtp})
                  </AppText>
                </View>
              ) : null}

              <Button
                testID="login-verify-button"
                label="Verify & Login"
                onPress={handleVerify}
                loading={loading}
                icon={<Ionicons name="lock-open-outline" size={18} color={colors.onBrand} />}
              />

              <View style={styles.resendRow}>
                <Pressable
                  testID="login-change-identifier"
                  onPress={() => {
                    setPhase("enter");
                    setCode("");
                    setError(null);
                  }}
                >
                  <AppText variant="label" color={colors.brand}>
                    ← Change
                  </AppText>
                </Pressable>
                <Pressable testID="login-resend-otp" onPress={handleResend} disabled={countdown > 0}>
                  <AppText variant="label" color={countdown > 0 ? colors.onSurfaceTertiary : colors.brand}>
                    {countdown > 0 ? `Resend in ${countdown}s` : "Resend OTP"}
                  </AppText>
                </Pressable>
              </View>
            </View>
          )}

          <View style={styles.legal}>
            <AppText variant="caption" center>
              By continuing you agree to our{" "}
              <AppText variant="caption" color={colors.brand}>Terms</AppText> &{" "}
              <AppText variant="caption" color={colors.brand}>Privacy Policy</AppText>.
            </AppText>
          </View>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { height: 320, justifyContent: "flex-start" },
  brandWrap: { alignItems: "center", paddingHorizontal: spacing.xl },
  logoBadge: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  brand: { fontFamily: fonts.displayBold, fontSize: 26, letterSpacing: 1 },
  card: {
    flex: 1,
    marginTop: -28,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xl,
    paddingBottom: spacing["2xl"],
  },
  hintRow: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  devHint: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    borderRadius: radius.md,
    padding: spacing.md,
  },
  resendRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  legal: { marginTop: spacing["2xl"] },
});

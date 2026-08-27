import React, { useEffect, useRef, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";

import { startGoogleStaffLogin } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { roleRouteFor } from "@/src/auth/roleRoutes";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Input } from "@/src/components/ui/Input";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const HERO = require("../assets/images/transit-mixer.jpg");
const GOOGLE_APP_REDIRECT = "trackmyrmc://auth/google";

WebBrowser.maybeCompleteAuthSession();

type LoginMode = "user" | "plant";

type ContactAction = {
  label: string;
  detail: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  url: string;
};

const CONTACT_ACTIONS: ContactAction[] = [
  {
    label: "Support",
    detail: "+91 9594177870",
    icon: "logo-whatsapp",
    url: "https://wa.me/919594177870",
  },
  {
    label: "Query",
    detail: "+91 9082189911",
    icon: "logo-whatsapp",
    url: "https://wa.me/919082189911",
  },
  {
    label: "Instagram",
    detail: "@trackmyrmc",
    icon: "logo-instagram",
    url: "https://www.instagram.com/trackmyrmc?igsi=MXQ5YnVpbmkyMmw1dA==",
  },
  {
    label: "Email",
    detail: "support@goldetech.com",
    icon: "mail-outline",
    url: "mailto:support@goldetech.com",
  },
];

const DEMO_LOGIN_ENABLED = process.env.EXPO_PUBLIC_ENABLE_DEMO_LOGIN === "1";

const DEMO_ROLES: { role: string; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
  { role: "customer", label: "User", icon: "person-outline" },
  { role: "plant_owner", label: "Owner", icon: "business-outline" },
  { role: "authority", label: "Authority", icon: "shield-checkmark-outline" },
  { role: "driver", label: "Driver", icon: "car-outline" },
];

const GOOGLE_ERRORS: Record<string, string> = {
  account_not_provisioned: "This Google account is not registered as a TrackMyRMC plant user.",
  account_not_ready: "This staff account is not fully assigned yet. Contact your plant administrator.",
  account_unavailable: "This staff account is not currently available.",
  use_mobile_login: "Customers and drivers must use User Login with mobile OTP.",
  google_cancelled: "Google sign-in was cancelled.",
  google_invalid_response: "Google sign-in returned an invalid response.",
  google_invalid_state: "Google sign-in expired. Please try again.",
  google_exchange_failed: "Google could not complete sign-in. Please try again.",
  google_unavailable: "Google sign-in is temporarily unavailable.",
  google_missing_identity: "Google did not return an account identity.",
  google_identity_invalid: "Google account verification failed.",
  google_email_unverified: "Use a Google account with a verified email address.",
  google_email_invalid: "Google returned an invalid email address.",
  google_retry: "Google sign-in could not finish. Please try again.",
};

export default function Login() {
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { hydrating, token, user, requestOtp, verify, verifyGoogle, demoLogin } = useAuth();

  const [mode, setMode] = useState<LoginMode>("user");
  const [phase, setPhase] = useState<"enter" | "otp">("enter");
  const [mobile, setMobile] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  useEffect(() => {
    if (!hydrating && token && user) router.replace(roleRouteFor(user.role) as any);
  }, [hydrating, token, user, router]);

  const resetEntry = (nextMode: LoginMode) => {
    setMode(nextMode);
    setPhase("enter");
    setCode("");
    setError(null);
    setCountdown(0);
    if (timer.current) clearInterval(timer.current);
  };

  const startCountdown = (secs: number) => {
    setCountdown(secs);
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          if (timer.current) clearInterval(timer.current);
          return 0;
        }
        return current - 1;
      });
    }, 1000);
  };

  const handleSendOtp = async () => {
    setError(null);
    if (mobile.length !== 10) {
      setError("Enter a valid 10-digit mobile number");
      return;
    }
    const fullNumber = `+91${mobile}`;
    setLoading(true);
    try {
      const res = await requestOtp(fullNumber);
      if (res.channel !== "sms") throw { detail: "User Login requires mobile OTP" };
      setIdentifier(fullNumber);
      setCode("");
      setPhase("otp");
      startCountdown(30);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast("OTP sent by SMS", "success");
    } catch (e: any) {
      setError(e.detail || "Could not send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown <= 0) await handleSendOtp();
  };

  const handleVerify = async () => {
    setError(null);
    if (code.trim().length !== 6) {
      setError("Enter the 6-digit OTP");
      return;
    }
    setLoading(true);
    try {
      const me = await verify(identifier, code.trim());
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`Welcome, ${me.name}`, "success");
      router.replace(roleRouteFor(me.role) as any);
    } catch (e: any) {
      setError(e.detail || "Invalid OTP");
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const { authorization_url } = await startGoogleStaffLogin();
      const result = await WebBrowser.openAuthSessionAsync(authorization_url, GOOGLE_APP_REDIRECT);
      if (result.type === "cancel" || result.type === "dismiss") return;
      if (result.type !== "success" || !("url" in result) || !result.url) {
        throw { detail: "Google sign-in did not complete" };
      }

      const parsed = Linking.parse(result.url);
      const oauthError = parsed.queryParams?.error;
      if (oauthError) {
        const key = String(oauthError);
        throw { detail: GOOGLE_ERRORS[key] || "Google sign-in failed" };
      }
      const exchangeCode = parsed.queryParams?.code;
      if (!exchangeCode) throw { detail: "Google sign-in code was not returned" };

      const me = await verifyGoogle(String(exchangeCode));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`Welcome, ${me.name}`, "success");
      router.replace(roleRouteFor(me.role) as any);
    } catch (e: any) {
      setError(e.detail || "Google sign-in failed");
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (role: string) => {
    setError(null);
    setLoading(true);
    try {
      const me = await demoLogin(role);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`Welcome, ${me.name}`, "success");
      router.replace(roleRouteFor(me.role) as any);
    } catch (e: any) {
      setError(e.detail || "Demo login is unavailable");
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const openExternal = async (url: string) => {    try {
      await Linking.openURL(url);
    } catch {
      toast("Unable to open this link on your device", "error");
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
        <View style={styles.hero}>
          <Image source={HERO} style={StyleSheet.absoluteFill} contentFit="contain" />
          <LinearGradient
            pointerEvents="none"
            colors={["rgba(5,24,20,0.76)", "rgba(5,24,20,0.10)", colors.surface]}
            locations={[0, 0.62, 1]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.brandWrap, { paddingTop: insets.top + spacing.lg }]}>
            <AppText style={styles.brand} color="#FFFFFF">TRACK MY RMC</AppText>
          </View>
        </View>

        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[styles.segmented, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
            <Pressable
              testID="login-user-tab"
              onPress={() => resetEntry("user")}
              style={[styles.segment, mode === "user" && { backgroundColor: colors.brand }]}
            >
              <AppText
                style={styles.segmentLabel}
                color={mode === "user" ? colors.onBrand : colors.onSurfaceTertiary}
              >
                USER LOGIN
              </AppText>
            </Pressable>
            <Pressable
              testID="login-plant-tab"
              onPress={() => resetEntry("plant")}
              style={[styles.segment, mode === "plant" && { backgroundColor: colors.brand }]}
            >
              <AppText
                style={styles.segmentLabel}
                color={mode === "plant" ? colors.onBrand : colors.onSurfaceTertiary}
              >
                PLANT USER LOGIN
              </AppText>
            </Pressable>
          </View>

          {mode === "user" ? (
            phase === "enter" ? (
              <View style={styles.formGap}>
                <AppText variant="heading">Mobile Login</AppText>
                <View
                  style={[
                    styles.phoneInputWrap,
                    {
                      borderColor: error ? colors.error : colors.border,
                      backgroundColor: colors.surfaceSecondary,
                    },
                  ]}
                >
                  <View style={[styles.prefix, { borderRightColor: colors.border }]}>
                    <AppText style={styles.prefixText}>+91</AppText>
                  </View>
                  <TextInput
                    testID="login-mobile-input"
                    value={mobile}
                    onChangeText={(text) => {
                      setMobile(text.replace(/\D/g, "").slice(0, 10));
                      setError(null);
                    }}
                    placeholder="10-digit mobile number"
                    placeholderTextColor={colors.onSurfaceTertiary}
                    keyboardType="number-pad"
                    maxLength={10}
                    autoFocus
                    style={[styles.phoneInput, { color: colors.onSurface }]}
                  />
                </View>
                {error ? <AppText variant="caption" color={colors.error}>{error}</AppText> : null}
                <Button
                  testID="login-send-otp-button"
                  label="Send OTP"
                  onPress={handleSendOtp}
                  loading={loading}
                  disabled={mobile.length !== 10}
                  icon={<Ionicons name="phone-portrait-outline" size={18} color={colors.onBrand} />}
                />
              </View>
            ) : (
              <View style={styles.formGap}>
                <AppText variant="heading">Verify OTP</AppText>
                <AppText variant="bodyMuted">OTP sent to +91 {mobile}</AppText>
                <Input
                  testID="login-otp-input"
                  label="One-time password"
                  value={code}
                  onChangeText={(text) => {
                    setCode(text.replace(/[^0-9]/g, "").slice(0, 6));
                    setError(null);
                  }}
                  placeholder="••••••"
                  keyboardType="number-pad"
                  maxLength={6}
                  center
                  autoFocus
                  error={error}
                />
                <Button
                  testID="login-verify-button"
                  label="Verify & Login"
                  onPress={handleVerify}
                  loading={loading}
                  disabled={code.length !== 6}
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
                    <AppText variant="label" color={colors.brand}>← Change number</AppText>
                  </Pressable>
                  <Pressable testID="login-resend-otp" onPress={handleResend} disabled={countdown > 0}>
                    <AppText variant="label" color={countdown > 0 ? colors.onSurfaceTertiary : colors.brand}>
                      {countdown > 0 ? `Resend in ${countdown}s` : "Resend OTP"}
                    </AppText>
                  </Pressable>
                </View>
              </View>
            )
          ) : (
            <View style={styles.formGap}>
              <AppText variant="heading">Plant User Login</AppText>
              <Pressable
                testID="login-google-button"
                accessibilityRole="button"
                onPress={handleGoogleLogin}
                disabled={loading}
                style={({ pressed }) => [
                  styles.googleButton,
                  {
                    borderColor: colors.border,
                    backgroundColor: pressed ? colors.surfaceSecondary : colors.surface,
                    opacity: loading ? 0.65 : 1,
                  },
                ]}
              >
                <View style={styles.googleMark}>
                  <AppText style={styles.googleLetter}>G</AppText>
                </View>
                <AppText style={styles.googleButtonText}>Continue with Google</AppText>
              </Pressable>
              {error ? <AppText variant="caption" color={colors.error}>{error}</AppText> : null}
            </View>
          )}

          {DEMO_LOGIN_ENABLED ? (
            <View style={[styles.demoBox, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}>
              <AppText variant="label" style={styles.demoTitle}>
                Demo access (Google Play review)
              </AppText>
              <View style={styles.demoGrid}>
                {DEMO_ROLES.map((item) => (
                  <Pressable
                    key={item.role}
                    testID={`demo-login-${item.role}`}
                    disabled={loading}
                    onPress={() => handleDemoLogin(item.role)}
                    style={({ pressed }) => [
                      styles.demoChip,
                      {
                        borderColor: colors.border,
                        backgroundColor: pressed ? colors.brand + "1A" : colors.surface,
                        opacity: loading ? 0.6 : 1,
                      },
                    ]}
                  >
                    <Ionicons name={item.icon} size={18} color={colors.brand} />
                    <AppText style={styles.demoChipLabel}>{item.label}</AppText>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}

          <View style={styles.legal}>
            <View style={styles.legalRow}>
              <Pressable onPress={() => router.push("/privacy")}>
                <AppText variant="caption" color={colors.brand}>Privacy Policy</AppText>
              </Pressable>
              <AppText variant="caption">·</AppText>
              <Pressable onPress={() => router.push("/account-deletion-public")}>
                <AppText variant="caption" color={colors.brand}>Delete Account</AppText>
              </Pressable>
            </View>

            <AppText variant="caption" center style={styles.poweredBy}>
              Powered by <AppText variant="caption" style={styles.goldETech}>GOLD e TECH</AppText>
            </AppText>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.contactRow}
            >
              {CONTACT_ACTIONS.map((action) => (
                <Pressable
                  key={action.label}
                  accessibilityRole="link"
                  accessibilityLabel={`${action.label}: ${action.detail}`}
                  onPress={() => openExternal(action.url)}
                  style={[styles.contactAction, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}
                >
                  <Ionicons name={action.icon} size={20} color={colors.brand} />
                  <AppText style={styles.contactLabel}>{action.label}</AppText>
                  <AppText style={styles.contactDetail} numberOfLines={1}>{action.detail}</AppText>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: {
    height: 300,
    justifyContent: "flex-start",
    backgroundColor: "#071B17",
  },
  brandWrap: {
    alignItems: "center",
    paddingHorizontal: spacing.xl,
  },
  brand: {
    fontFamily: fonts.displayBold,
    fontSize: 26,
    letterSpacing: 1.2,
  },
  card: {
    flex: 1,
    marginTop: -24,
    marginHorizontal: spacing.md,
    borderRadius: 28,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing["2xl"],
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 5,
  },
  segmented: {
    flexDirection: "row",
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: 4,
    marginBottom: spacing.xl,
  },
  segment: {
    flex: 1,
    minHeight: 44,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  segmentLabel: {
    fontFamily: fonts.semibold,
    fontSize: 11,
    letterSpacing: 0.25,
    textAlign: "center",
  },
  formGap: {
    gap: spacing.lg,
  },
  phoneInputWrap: {
    flexDirection: "row",
    minHeight: 56,
    borderRadius: radius.md,
    borderWidth: 1,
    overflow: "hidden",
    alignItems: "stretch",
  },
  prefix: {
    width: 66,
    borderRightWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  prefixText: {
    fontFamily: fonts.semibold,
    fontSize: fontSize.base,
  },
  phoneInput: {
    flex: 1,
    minHeight: 56,
    paddingHorizontal: spacing.md,
    fontFamily: fonts.medium,
    fontSize: fontSize.base,
  },
  googleButton: {
    minHeight: 56,
    borderWidth: 1,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  googleMark: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(127,127,127,0.28)",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
  },
  googleLetter: {
    color: "#4285F4",
    fontFamily: fonts.displayBold,
    fontSize: 17,
  },
  googleButtonText: {
    fontFamily: fonts.semibold,
    fontSize: fontSize.base,
  },
  resendRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
  },
  legal: {
    marginTop: spacing["2xl"],
    paddingTop: spacing.lg,
  },
  demoBox: {
    marginTop: spacing.xl,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  demoTitle: {
    textAlign: "center",
  },
  demoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    justifyContent: "center",
  },
  demoChip: {
    minHeight: 44,
    flexGrow: 1,
    minWidth: "45%",
    borderWidth: 1,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  demoChipLabel: {
    fontFamily: fonts.semibold,
    fontSize: fontSize.sm,
  },  legalRow: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.sm,
  },
  poweredBy: {
    marginTop: spacing.lg,
  },
  goldETech: {
    fontFamily: fonts.semibold,
    letterSpacing: 0.4,
  },
  contactRow: {
    flexDirection: "row",
    flexWrap: "nowrap",
    gap: spacing.sm,
    paddingTop: spacing.lg,
    paddingHorizontal: 1,
  },
  contactAction: {
    width: 116,
    minHeight: 78,
    borderWidth: 1,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
    paddingVertical: spacing.sm,
    gap: 3,
  },
  contactLabel: {
    fontFamily: fonts.semibold,
    fontSize: 11,
  },
  contactDetail: {
    fontFamily: fonts.regular,
    fontSize: 9,
    opacity: 0.72,
    maxWidth: 104,
  },
});
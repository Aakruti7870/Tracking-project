import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
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

import { startGoogleStaffLogin, startStaffPasskeyAuthentication } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { roleRouteFor } from "@/src/auth/roleRoutes";
import { OtpOrbitVerification, OtpVisualState } from "@/src/components/auth/OtpOrbitVerification";
import { useTheme } from "@/src/theme/ThemeProvider";

const HERO_LIGHT = require("../../assets/images/login-hero-light.jpg");
const HERO_DARK = require("../../assets/images/login-hero-dark.jpg");
const PRIVACY_POLICY_URL = "https://trackmyrmc.com/privacy_policy";
const ACCOUNT_DELETION_URL = "https://trackmyrmc.com/account-deletion";
const TERMS_URL = "https://trackmyrmc.com/terms";
const DEMO_LOGIN_ENABLED = process.env.EXPO_PUBLIC_ENABLE_DEMO_LOGIN === "1";
const DEMO_ROLES = [
  { role: "customer", label: "User" },
  { role: "plant_owner", label: "Owner" },
  { role: "authority", label: "Authority" },
  { role: "driver", label: "Driver" },
];

type LoginMode = "user" | "plant";
type LoginPhase = "enter" | "user_otp" | "staff_email_otp" | "staff_totp" | "staff_passkey";
const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function PremiumLoginScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const {
    hydrating, token, user, requestOtp, requestStaffOtp, staffAuthMethod,
    verify, verifyStaff, verifyStaffAuthenticator, completeStaffPasskey,
    verifyGoogle, demoLogin,
  } = useAuth();

  const [mode, setMode] = useState<LoginMode>("user");
  const [phase, setPhase] = useState<LoginPhase>("enter");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [otpVisual, setOtpVisual] = useState<OtpVisualState>("idle");
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const accent = "#FF650D";
  const danger = "#E5484D";
  const page = colors.isDark ? "#070809" : "#F7F7F5";
  const card = colors.isDark ? "#111212" : "#FFFFFF";
  const secondary = colors.isDark ? "#0A0B0B" : "#F2F2EF";
  const text = colors.isDark ? "#F8F8F6" : "#151515";
  const muted = colors.isDark ? "#9B9B98" : "#747474";
  const border = colors.isDark ? "rgba(255,255,255,0.09)" : "rgba(20,20,20,0.10)";

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  useEffect(() => {
    if (!hydrating && token && user && phase === "enter") {
      if (user.mfa_configured && !user.mfa_enabled && user.role !== "customer" && user.role !== "driver") {
        router.replace("/mfa-setup" as any);
      } else {
        router.replace(roleRouteFor(user.role) as any);
      }
    }
  }, [hydrating, token, user, phase, router]);

  const startCountdown = (seconds = 30) => {
    setCountdown(seconds);
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          if (timer.current) clearInterval(timer.current);
          timer.current = null;
          return 0;
        }
        return current - 1;
      });
    }, 1000);
  };

  const reset = (nextMode: LoginMode) => {
    setMode(nextMode); setPhase("enter"); setCode(""); setError(null); setOtpVisual("idle"); setCountdown(0);
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  const finishLogin = async (me: Awaited<ReturnType<typeof verify>>) => {
    setOtpVisual("success");
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    await delay(650);
    if (me.mfa_configured && !me.mfa_enabled && me.role !== "customer" && me.role !== "driver") {
      router.replace("/mfa-setup" as any);
    } else {
      router.replace(roleRouteFor(me.role) as any);
    }
  };

  const failOtp = async (message: string) => {
    setError(message); setOtpVisual("error");
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    await delay(800); setCode(""); setOtpVisual("idle");
  };

  const sendUserOtp = async () => {
    setError(null);
    const clean = mobile.replace(/\D/g, "").slice(0, 10);
    if (!/^[6-9]\d{9}$/.test(clean)) return setError("Enter a valid 10-digit mobile number");
    setLoading(true);
    try {
      const full = `+91${clean}`;
      const response = await requestOtp(full);
      if (response.channel !== "sms") throw { detail: "User Login requires mobile OTP" };
      setIdentifier(full); setCode(""); setPhase("user_otp"); startCountdown(30);
    } catch (e: any) { setError(e.detail || "Could not send OTP"); }
    finally { setLoading(false); }
  };

  const sendStaffOtp = async () => {
    setError(null);
    const normalized = email.trim().toLowerCase();
    if (!validEmail(normalized)) return setError("Enter a valid approved email address");
    setLoading(true);
    try {
      const response = await requestStaffOtp(normalized);
      if (response.status === "ONBOARDING_REQUIRED") {
        router.push({ pathname: "/plant-onboarding" as any, params: { email: normalized } } as any);
        return;
      }
      setIdentifier(normalized); setCode("");
      if (response.status === "AUTHENTICATOR_REQUIRED") {
        setPhase(response.passkey_available ? "staff_passkey" : "staff_totp");
      } else {
        setPhase("staff_email_otp"); startCountdown(30);
      }
    } catch (e: any) { setError(e.detail || "Could not start Plant Staff login"); }
    finally { setLoading(false); }
  };

  const verifyUserOtp = useCallback(async (otp: string) => {
    if (loading || otp.length !== 6) return;
    setLoading(true); setOtpVisual("checking");
    try { await finishLogin(await verify(identifier, otp)); }
    catch (e: any) { await failOtp(e.detail || "Incorrect OTP. Please try again."); }
    finally { setLoading(false); }
  }, [identifier, loading, verify]);

  const verifyEmailOtp = useCallback(async (otp: string) => {
    if (loading || otp.length !== 6) return;
    setLoading(true); setOtpVisual("checking");
    try { await finishLogin(await verifyStaff(identifier, otp)); }
    catch (e: any) { await failOtp(e.detail || "Incorrect or expired email OTP."); }
    finally { setLoading(false); }
  }, [identifier, loading, verifyStaff]);

  const verifyTotp = useCallback(async (otp: string) => {
    if (loading || otp.length !== 6) return;
    setLoading(true); setOtpVisual("checking");
    try { await finishLogin(await verifyStaffAuthenticator(identifier, otp)); }
    catch (e: any) { await failOtp(e.detail || "Incorrect Authenticator code."); }
    finally { setLoading(false); }
  }, [identifier, loading, verifyStaffAuthenticator]);

  const startAuthenticator = async () => {
    setMode("plant"); setError(null);
    const normalized = email.trim().toLowerCase();
    if (!validEmail(normalized)) return setError("Enter your approved Plant Staff email first");
    setLoading(true);
    try {
      const method = await staffAuthMethod(normalized);
      if (method.method !== "totp") {
        setError("Authenticator is not enabled for this staff account. Continue with email OTP.");
        return;
      }
      setIdentifier(normalized); setCode(""); setPhase("staff_totp");
    } catch (e: any) { setError(e.detail || "Authenticator login could not start"); }
    finally { setLoading(false); }
  };

  const startGoogle = async () => {
    setMode("plant"); setError(null); setLoading(true);
    try {
      const request = await startGoogleStaffLogin();
      if (Platform.OS === "web") {
        window.location.assign(request.authorization_url);
        return;
      }
      const result = await WebBrowser.openAuthSessionAsync(request.authorization_url, "trackmyrmc://auth/google");
      if (result.type !== "success") throw new Error("Google sign-in was cancelled");
      const parsed = Linking.parse(result.url);
      const rawCode = parsed.queryParams?.code;
      const handoff = Array.isArray(rawCode) ? String(rawCode[0] || "") : String(rawCode || "");
      if (handoff.length < 20) throw new Error("Google sign-in return code was missing");
      await finishLogin(await verifyGoogle(handoff));
    } catch (e: any) { setError(e.detail || e.message || "Google sign-in could not be completed"); }
    finally { setLoading(false); }
  };

  const verifyPasskey = async () => {
    setError(null); setLoading(true);
    try {
      const returnMode = Platform.OS === "web" ? "web" : "app";
      const request = await startStaffPasskeyAuthentication(identifier, returnMode);
      if (Platform.OS === "web") { window.location.assign(request.authorization_url); return; }
      const result = await WebBrowser.openAuthSessionAsync(request.authorization_url, "trackmyrmc://auth/passkey");
      if (result.type !== "success") throw new Error("Passkey login was cancelled");
      const parsed = Linking.parse(result.url);
      const rawCode = parsed.queryParams?.code;
      const handoff = Array.isArray(rawCode) ? String(rawCode[0] || "") : String(rawCode || "");
      if (handoff.length < 24) throw new Error("Secure passkey return code was missing");
      await finishLogin(await completeStaffPasskey(handoff));
    } catch (e: any) { setError(e.detail || e.message || "Passkey verification could not be completed"); }
    finally { setLoading(false); }
  };

  const openUrl = (url: string) => Linking.openURL(url).catch(() => setError("Unable to open this link on your device"));
  const otpColors = {
    surface: card, surfaceSecondary: secondary, onSurface: text, onSurfaceSecondary: muted,
    onSurfaceTertiary: muted, border, brand: accent, error: danger,
  };

  const renderPrimary = () => {
    if (phase === "user_otp") return <View style={styles.phaseBox}>
      <OtpOrbitVerification testID="login-user-otp-input" value={code} onChangeText={(v) => { setCode(v); setError(null); }} onComplete={verifyUserOtp} state={otpVisual} title="Verify your number" subtitle={`Enter the 6-digit code sent to +91 •••••• ${identifier.slice(-4)}.`} errorText={error} countdown={countdown} onResend={sendUserOtp} colors={otpColors} />
      <Pressable onPress={() => reset("user")}><Text style={[styles.linkText, { color: accent }]}>← Change mobile number</Text></Pressable>
    </View>;

    if (phase === "staff_email_otp") return <View style={styles.phaseBox}>
      <OtpOrbitVerification testID="login-plant-otp-input" value={code} onChangeText={(v) => { setCode(v); setError(null); }} onComplete={verifyEmailOtp} state={otpVisual} title="Verify approved email" subtitle={`Enter the 6-digit code sent to ${email.trim().toLowerCase()}.`} errorText={error} countdown={countdown} onResend={sendStaffOtp} resendLabel="Resend email code" colors={otpColors} />
      <Pressable onPress={() => reset("plant")}><Text style={[styles.linkText, { color: accent }]}>← Change email</Text></Pressable>
    </View>;

    if (phase === "staff_totp") return <View style={styles.phaseBox}>
      <OtpOrbitVerification testID="login-plant-authenticator-input" value={code} onChangeText={(v) => { setCode(v); setError(null); }} onComplete={verifyTotp} state={otpVisual} title="Authenticator verification" subtitle="Enter the current 6-digit code from your Authenticator app." errorText={error} colors={otpColors} successSubtitle="Authenticator verification completed." />
      <Pressable onPress={() => reset("plant")}><Text style={[styles.linkText, { color: accent }]}>← Back to Plant Staff login</Text></Pressable>
    </View>;

    if (phase === "staff_passkey") return <View style={styles.phaseBox}>
      <Ionicons name="finger-print-outline" size={48} color={accent} style={{ alignSelf: "center" }} />
      <Text style={[styles.phaseTitle, { color: text }]}>Secure staff verification</Text>
      <Text style={[styles.phaseSubtitle, { color: muted }]}>Use your registered passkey, or switch to Authenticator.</Text>
      <Pressable style={[styles.cta, { backgroundColor: accent }]} onPress={verifyPasskey} disabled={loading}><Ionicons name="finger-print-outline" size={20} color="#fff" /><Text style={styles.ctaText}>USE PASSKEY</Text></Pressable>
      <Pressable onPress={() => setPhase("staff_totp")}><Text style={[styles.linkText, { color: accent }]}>Use Authenticator instead</Text></Pressable>
    </View>;

    return <>
      <View style={[styles.segment, { backgroundColor: secondary, borderColor: border }]}> 
        <Pressable testID="login-mode-user" onPress={() => reset("user")} style={[styles.segmentButton, mode === "user" && { backgroundColor: colors.isDark ? "rgba(255,101,13,.18)" : "rgba(255,101,13,.10)", borderColor: accent }]}> <Ionicons name="person-outline" size={18} color={mode === "user" ? accent : muted} /><Text style={[styles.segmentLabel, { color: mode === "user" ? text : muted }]}>USER LOGIN</Text></Pressable>
        <Pressable testID="login-mode-plant" onPress={() => reset("plant")} style={[styles.segmentButton, mode === "plant" && { backgroundColor: colors.isDark ? "rgba(255,101,13,.18)" : "rgba(255,101,13,.10)", borderColor: accent }]}> <Ionicons name="people-outline" size={18} color={mode === "plant" ? accent : muted} /><Text style={[styles.segmentLabel, { color: mode === "plant" ? text : muted }]}>PLANT STAFF</Text></Pressable>
      </View>

      {mode === "user" ? (
        <View style={[styles.inputShell, { borderColor: border, backgroundColor: secondary }]}>
          <View style={[styles.prefix, { borderRightColor: border }]}><Text style={[styles.prefixText, { color: text }]}>+91</Text></View>
          <TextInput testID="login-mobile-input" keyboardType="number-pad" maxLength={10} value={mobile} onChangeText={(v) => { setMobile(v.replace(/\D/g, "").slice(0, 10)); setError(null); }} placeholder="Enter 10-digit mobile number" placeholderTextColor={muted} style={[styles.input, { color: text }]} />
        </View>
      ) : (
        <View style={[styles.inputShell, { borderColor: border, backgroundColor: secondary }]}>
          <View style={styles.iconPrefix}><Ionicons name="mail-outline" size={20} color={muted} /></View>
          <TextInput testID="login-email-input" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={(v) => { setEmail(v); setError(null); }} placeholder="Enter approved staff email" placeholderTextColor={muted} style={[styles.input, { color: text }]} />
        </View>
      )}

      {error ? <Text style={[styles.error, { color: danger }]}>{error}</Text> : null}
      <Pressable testID="login-continue" onPress={mode === "user" ? sendUserOtp : sendStaffOtp} disabled={loading} style={styles.ctaWrap}>
        <LinearGradient colors={["#FF7419", "#FF650D", "#E74D00"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.cta}>
          {loading ? <ActivityIndicator color="#fff" /> : <><Ionicons name="shield-checkmark-outline" size={20} color="#fff" /><Text style={styles.ctaText}>CONTINUE</Text></>}
        </LinearGradient>
      </Pressable>

      <View style={styles.orRow}><View style={[styles.orLine, { backgroundColor: border }]} /><Text style={[styles.orText, { color: muted }]}>OR</Text><View style={[styles.orLine, { backgroundColor: border }]} /></View>
      <View style={styles.altRow}>
        <Pressable testID="login-authenticator" onPress={startAuthenticator} style={[styles.altButton, { backgroundColor: secondary, borderColor: border }]}><Ionicons name="key-outline" size={21} color={accent} /><Text style={[styles.altText, { color: text }]}>Authenticator</Text></Pressable>
        <Pressable testID="login-google" onPress={startGoogle} style={[styles.altButton, { backgroundColor: secondary, borderColor: border }]}><Ionicons name="logo-google" size={20} color={accent} /><Text style={[styles.altText, { color: text }]}>Gmail</Text></Pressable>
      </View>
    </>;
  };

  return <View style={[styles.root, { backgroundColor: page }]}>
    <StatusBar style={colors.isDark ? "light" : "dark"} />
    <KeyboardAwareScrollView contentContainerStyle={{ paddingBottom: Math.max(20, insets.bottom + 12) }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      <View style={styles.heroWrap}>
        <Image source={colors.isDark ? HERO_DARK : HERO_LIGHT} style={styles.hero} contentFit="cover" contentPosition="center" transition={180} />
        <LinearGradient pointerEvents="none" colors={colors.isDark ? ["rgba(7,8,9,0)", "rgba(7,8,9,.10)", page] : ["rgba(247,247,245,0)", "rgba(247,247,245,.06)", page]} locations={[0, .7, 1]} style={StyleSheet.absoluteFill} />
      </View>

      <View style={[styles.card, { backgroundColor: card, borderColor: border }]}> 
        <View style={[styles.handle, { backgroundColor: border }]} />
        <Text style={[styles.title, { color: text }]}>Welcome back</Text>
        <Text style={[styles.subtitle, { color: muted }]}>Secure access to Track My RMC</Text>
        {renderPrimary()}
      </View>

      {DEMO_LOGIN_ENABLED ? <View style={[styles.demoBox, { backgroundColor: card, borderColor: border }]}>
        <Text style={[styles.demoTitle, { color: muted }]}>Google Play review demo</Text>
        <View style={styles.demoRow}>{DEMO_ROLES.map((item) => <Pressable key={item.role} disabled={loading} onPress={async () => { setLoading(true); try { const me = await demoLogin(item.role); router.replace(roleRouteFor(me.role) as any); } finally { setLoading(false); } }} style={[styles.demoChip, { borderColor: border }]}><Text style={[styles.demoChipText, { color: text }]}>{item.label}</Text></Pressable>)}</View>
      </View> : null}

      <View style={styles.footer}>
        <Text style={[styles.legalCopy, { color: muted }]}>By continuing, you agree to our <Text onPress={() => openUrl(TERMS_URL)} style={{ color: accent, fontWeight: "700" }}>Terms of Service</Text> and <Text onPress={() => openUrl(PRIVACY_POLICY_URL)} style={{ color: accent, fontWeight: "700" }}>Privacy Policy</Text>.</Text>
        <View style={styles.legalRow}><Pressable onPress={() => openUrl(PRIVACY_POLICY_URL)}><Text style={[styles.privacyLink, { color: accent }]}>Privacy Policy</Text></Pressable><Text style={{ color: muted }}>·</Text><Pressable onPress={() => openUrl(ACCOUNT_DELETION_URL)}><Text style={[styles.deleteLink, { color: danger }]}>Account Deletion</Text></Pressable></View>
        <Text style={[styles.powered, { color: muted }]}>Powered by <Text style={{ color: text, fontWeight: "700" }}>Gold e Tech</Text></Text>
        <View style={styles.socialRow}>
          <Pressable onPress={() => openUrl("https://wa.me/")} style={[styles.social, { borderColor: border }]}><Ionicons name="logo-whatsapp" size={19} color={text} /></Pressable>
          <Pressable onPress={() => openUrl("https://instagram.com/")} style={[styles.social, { borderColor: border }]}><Ionicons name="logo-instagram" size={19} color={text} /></Pressable>
          <Pressable onPress={() => openUrl("mailto:support@trackmyrmc.com")} style={[styles.social, { borderColor: border }]}><Ionicons name="mail-outline" size={19} color={text} /></Pressable>
        </View>
        <Pressable testID="login-review-access" onPress={() => router.push("/review-access" as any)} hitSlop={10}><Text style={[styles.reviewLink, { color: muted }]}>REVIEW APP · Google Play reviewer access</Text></Pressable>
      </View>
    </KeyboardAwareScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  heroWrap: { height: 330, overflow: "hidden" },
  hero: { width: "100%", height: "100%" },
  card: { marginHorizontal: 14, marginTop: -30, padding: 18, borderRadius: 28, borderWidth: 1, shadowColor: "#000", shadowOpacity: .16, shadowRadius: 22, shadowOffset: { width: 0, height: 10 }, elevation: 10 },
  handle: { width: 44, height: 5, borderRadius: 99, alignSelf: "center", marginBottom: 18 },
  title: { fontSize: 29, fontWeight: "800", textAlign: "center", letterSpacing: -.6 },
  subtitle: { fontSize: 14, textAlign: "center", marginTop: 6, marginBottom: 20 },
  segment: { flexDirection: "row", padding: 5, borderWidth: 1, borderRadius: 18, gap: 5 },
  segmentButton: { flex: 1, minHeight: 50, borderRadius: 14, borderWidth: 1, borderColor: "transparent", flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  segmentLabel: { fontSize: 13, fontWeight: "800" },
  inputShell: { marginTop: 16, height: 56, borderRadius: 17, borderWidth: 1, flexDirection: "row", alignItems: "center", overflow: "hidden" },
  prefix: { width: 72, height: "100%", alignItems: "center", justifyContent: "center", borderRightWidth: 1 },
  prefixText: { fontSize: 17, fontWeight: "800" },
  iconPrefix: { width: 52, alignItems: "center", justifyContent: "center" },
  input: { flex: 1, height: "100%", paddingHorizontal: 16, fontSize: 16 },
  error: { marginTop: 10, fontSize: 13, fontWeight: "600" },
  ctaWrap: { marginTop: 14, borderRadius: 17, overflow: "hidden" },
  cta: { minHeight: 56, borderRadius: 17, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9 },
  ctaText: { color: "#fff", fontSize: 16, fontWeight: "900", letterSpacing: .5 },
  orRow: { flexDirection: "row", alignItems: "center", gap: 10, marginVertical: 15 },
  orLine: { flex: 1, height: 1 },
  orText: { fontSize: 11, fontWeight: "800" },
  altRow: { flexDirection: "row", gap: 10 },
  altButton: { flex: 1, minHeight: 54, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  altText: { fontSize: 13, fontWeight: "800" },
  phaseBox: { gap: 14 },
  phaseTitle: { fontSize: 22, fontWeight: "800", textAlign: "center" },
  phaseSubtitle: { fontSize: 14, textAlign: "center", lineHeight: 20 },
  linkText: { textAlign: "center", fontSize: 13, fontWeight: "800" },
  demoBox: { marginHorizontal: 14, marginTop: 12, padding: 12, borderWidth: 1, borderRadius: 18 },
  demoTitle: { fontSize: 11, fontWeight: "800", textAlign: "center", marginBottom: 8 },
  demoRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8 },
  demoChip: { paddingHorizontal: 10, paddingVertical: 7, borderWidth: 1, borderRadius: 12 },
  demoChipText: { fontSize: 11, fontWeight: "700" },
  footer: { paddingHorizontal: 22, paddingTop: 22, alignItems: "center" },
  legalCopy: { fontSize: 12, textAlign: "center", lineHeight: 18 },
  legalRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 10 },
  privacyLink: { fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  deleteLink: { fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  powered: { marginTop: 13, fontSize: 13 },
  socialRow: { flexDirection: "row", gap: 14, marginTop: 12 },
  social: { width: 38, height: 38, borderRadius: 19, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  reviewLink: { marginTop: 16, fontSize: 10, fontWeight: "700", textAlign: "center" },
});

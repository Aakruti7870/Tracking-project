import React, { useEffect, useRef, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";

import { startStaffPasskeyAuthentication } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { roleRouteFor } from "@/src/auth/roleRoutes";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { BrandHero } from "@/src/components/BrandHero";
import { Input } from "@/src/components/ui/Input";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type LoginMode = "user" | "plant";
type LoginPhase = "enter" | "user_otp" | "staff_email_otp" | "staff_passkey" | "staff_totp" | "staff_recovery";

type ContactAction = {
  label: string;
  detail: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  url: string;
  tone: "brand" | "instagram";
};

const CONTACT_ACTIONS: ContactAction[] = [
  { label: "Support", detail: "+91 9594177870", icon: "logo-whatsapp", url: "https://wa.me/919594177870", tone: "brand" },
  { label: "Query", detail: "+91 9082189911", icon: "logo-whatsapp", url: "https://wa.me/919082189911", tone: "brand" },
  { label: "Instagram", detail: "@trackmyrmc", icon: "logo-instagram", url: "https://www.instagram.com/trackmyrmc?igsi=MXQ5YnVpbmkyMmw1dA==", tone: "instagram" },
  { label: "Email", detail: "support@goldetech.com", icon: "mail-outline", url: "mailto:support@goldetech.com", tone: "brand" },
];

const DEMO_LOGIN_ENABLED = process.env.EXPO_PUBLIC_ENABLE_DEMO_LOGIN === "1";
const DEMO_ROLES: { role: string; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
  { role: "customer", label: "User", icon: "person-outline" },
  { role: "plant_owner", label: "Owner", icon: "business-outline" },
  { role: "authority", label: "Authority", icon: "shield-checkmark-outline" },
  { role: "driver", label: "Driver", icon: "car-outline" },
];

const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());

export default function Login() {
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const {
    hydrating,
    token,
    user,
    requestOtp,
    requestStaffOtp,
    verify,
    verifyStaff,
    verifyStaffAuthenticator,
    verifyStaffRecovery,
    completeStaffPasskey,
    demoLogin,
  } = useAuth();

  const [mode, setMode] = useState<LoginMode>("user");
  const [phase, setPhase] = useState<LoginPhase>("enter");
  const [mobile, setMobile] = useState("");
  const [plantEmail, setPlantEmail] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [onboardingRequired, setOnboardingRequired] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  useEffect(() => {
    if (!hydrating && token && user) {
      if (user.mfa_configured && !user.mfa_enabled && user.role !== "customer" && user.role !== "driver") {
        router.replace("/mfa-setup" as any);
      } else {
        router.replace(roleRouteFor(user.role) as any);
      }
    }
  }, [hydrating, token, user, router]);

  const clearTimer = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  const resetEntry = (nextMode: LoginMode) => {
    setMode(nextMode);
    setPhase("enter");
    setCode("");
    setRecoveryCode("");
    setError(null);
    setCountdown(0);
    setOnboardingRequired(false);
    clearTimer();
  };

  const startCountdown = (seconds: number) => {
    setCountdown(seconds);
    clearTimer();
    timer.current = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          clearTimer();
          return 0;
        }
        return current - 1;
      });
    }, 1000);
  };

  const handleSendUserOtp = async () => {
    setError(null);
    if (mobile.length !== 10) {
      setError("Enter a valid 10-digit mobile number");
      return;
    }
    const fullNumber = `+91${mobile}`;
    setLoading(true);
    try {
      const response = await requestOtp(fullNumber);
      if (response.channel !== "sms") throw { detail: "User Login requires mobile OTP" };
      setIdentifier(fullNumber);
      setCode("");
      setPhase("user_otp");
      startCountdown(30);
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast("OTP sent by SMS", "success");
    } catch (e: any) {
      setError(e.detail || "Could not send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleStartPlantLogin = async () => {
    setError(null);
    setOnboardingRequired(false);
    const email = plantEmail.trim().toLowerCase();
    if (!validEmail(email)) {
      setError("Enter a valid approved email address");
      return;
    }
    setLoading(true);
    try {
      const response = await requestStaffOtp(email);
      if (response.status === "ONBOARDING_REQUIRED") {
        setPlantEmail(response.email || email);
        setOnboardingRequired(true);
        setPhase("enter");
        return;
      }
      setIdentifier(email);
      setPlantEmail(email);
      setCode("");
      setRecoveryCode("");
      if (response.status === "AUTHENTICATOR_REQUIRED") {
        setPhase(response.passkey_available ? "staff_passkey" : "staff_totp");
        clearTimer();
        void Haptics.selectionAsync();
        return;
      }
      if (response.status !== "OTP_SENT" || response.channel !== "email") {
        throw { detail: "Plant Staff secure login could not start" };
      }
      setPhase("staff_email_otp");
      startCountdown(30);
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast("Verification code sent to your approved email", "success");
    } catch (e: any) {
      setError(e.detail || "Could not start Plant Staff login");
    } finally {
      setLoading(false);
    }
  };

  const finishLogin = (me: Awaited<ReturnType<typeof verify>>, offerPasskey = false) => {
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    toast(`Welcome, ${me.name}`, "success");
    if (me.mfa_configured && !me.mfa_enabled && me.role !== "customer" && me.role !== "driver") {
      router.replace("/mfa-setup" as any);
      return;
    }
    if (offerPasskey && me.mfa_enabled && !me.passkey_enabled && me.role !== "customer" && me.role !== "driver") {
      router.replace("/passkey-setup" as any);
      return;
    }
    router.replace(roleRouteFor(me.role) as any);
  };

  const handleVerifyUser = async () => {
    setError(null);
    if (code.trim().length !== 6) {
      setError("Enter the 6-digit OTP");
      return;
    }
    setLoading(true);
    try {
      const me = await verify(identifier, code.trim());
      finishLogin(me);
    } catch (e: any) {
      setError(e.detail || "Invalid OTP");
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyStaffEmail = async () => {
    setError(null);
    if (code.trim().length !== 6) {
      setError("Enter the 6-digit email code");
      return;
    }
    setLoading(true);
    try {
      const me = await verifyStaff(identifier, code.trim());
      finishLogin(me);
    } catch (e: any) {
      setError(e.detail || "Invalid or expired email OTP");
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPasskey = async () => {
    setLoading(true);
    setError(null);
    try {
      const returnMode = Platform.OS === "web" ? "web" : "app";
      const request = await startStaffPasskeyAuthentication(identifier, returnMode);
      if (Platform.OS === "web") {
        window.location.assign(request.authorization_url);
        return;
      }

      const result = await WebBrowser.openAuthSessionAsync(request.authorization_url, "trackmyrmc://auth/passkey");
      if (result.type !== "success") throw new Error("Passkey login was cancelled");
      const parsed = Linking.parse(result.url);
      const rawCode = parsed.queryParams?.code;
      const handoff = Array.isArray(rawCode) ? String(rawCode[0] || "") : String(rawCode || "");
      if (handoff.length < 24) throw new Error("Secure passkey return code was missing");
      const me = await completeStaffPasskey(handoff);
      finishLogin(me);
    } catch (e: any) {
      setError(e?.detail || e?.message || "Passkey verification could not be completed");
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAuthenticator = async () => {
    setError(null);
    if (code.trim().length !== 6) {
      setError("Enter the 6-digit Authenticator code");
      return;
    }
    setLoading(true);
    try {
      const me = await verifyStaffAuthenticator(identifier, code.trim());
      finishLogin(me, true);
    } catch (e: any) {
      setError(e.detail || "Invalid Authenticator code");
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyRecovery = async () => {
    setError(null);
    if (recoveryCode.replace(/[^A-Z0-9]/gi, "").length < 8) {
      setError("Enter one of your saved recovery codes");
      return;
    }
    setLoading(true);
    try {
      const me = await verifyStaffRecovery(identifier, recoveryCode.trim());
      finishLogin(me);
    } catch (e: any) {
      setError(e.detail || "Invalid or already used recovery code");
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setLoading(false);
    }
  };

  const resendCurrentOtp = async () => {
    if (countdown > 0) return;
    if (phase === "user_otp") await handleSendUserOtp();
    if (phase === "staff_email_otp") await handleStartPlantLogin();
  };

  const handleDemoLogin = async (role: string) => {
    setError(null);
    setLoading(true);
    try {
      const me = await demoLogin(role);
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(`Welcome, ${me.name}`, "success");
      router.replace(roleRouteFor(me.role) as any);
    } catch (e: any) {
      setError(e.detail || "Demo login is unavailable");
    } finally {
      setLoading(false);
    }
  };

  const openExternal = async (url: string) => {
    try {
      await Linking.openURL(url);
    } catch {
      toast("Unable to open this link on your device", "error");
    }
  };

  const PRIVACY_POLICY_URL = "https://trackmyrmc.com/privacy_policy";
  const ACCOUNT_DELETION_URL = "https://trackmyrmc.com/account-deletion";

  const confirmAccountDeletion = () => {
    void Haptics.selectionAsync();
    const title = "Delete your TrackMyRMC account?";
    const body = "You are about to open the TrackMyRMC account-deletion portal. You will verify ownership before deletion. Personal profile data is deleted permanently; legally required business records may be retained in anonymized form.";
    const proceed = () => { void openExternal(ACCOUNT_DELETION_URL); };
    if (Platform.OS === "web") {
      const ok = typeof window !== "undefined" && typeof window.confirm === "function" && window.confirm(`${title}\n\n${body}`);
      if (ok) proceed();
      return;
    }
    Alert.alert(title, body, [
      { text: "Cancel", style: "cancel" },
      { text: "Continue", style: "destructive", onPress: proceed },
    ]);
  };

  const openOnboarding = () => {
    router.push({ pathname: "/plant-onboarding" as any, params: { email: plantEmail.trim().toLowerCase() } } as any);
  };

  const codeInput = (label: string, testID: string, submit: () => void, buttonLabel: string) => (
    <View style={styles.formGap}>
      <View style={styles.securityHeading}>
        <View style={[styles.securityIcon, { backgroundColor: colors.brandSoft }]}>
          <Ionicons name="shield-checkmark-outline" size={24} color={colors.brand} />
        </View>
        <View style={{ flex: 1, gap: 3 }}>
          <AppText variant="heading">{label}</AppText>
          <AppText variant="bodyMuted">Secure verification for {plantEmail}</AppText>
        </View>
      </View>
      <Input
        testID={testID}
        label="6-digit code"
        value={code}
        onChangeText={(text) => { setCode(text.replace(/[^0-9]/g, "").slice(0, 6)); setError(null); }}
        placeholder="••••••"
        keyboardType="number-pad"
        maxLength={6}
        center
        autoFocus
        error={error}
      />
      <Button
        testID="login-plant-verify-button"
        label={buttonLabel}
        onPress={submit}
        loading={loading}
        disabled={code.length !== 6}
        icon={<Ionicons name="lock-open-outline" size={18} color={colors.onBrand} />}
      />
    </View>
  );

  const renderForm = () => {
    if (phase === "user_otp") {
      return (
        <View style={styles.formGap}>
          <View style={styles.formHeadingRow}>
            <View style={[styles.formIcon, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name="chatbox-ellipses-outline" size={22} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText variant="heading">Verify OTP</AppText>
              <AppText variant="bodyMuted">OTP sent to +91 {mobile}</AppText>
            </View>
          </View>
          <Input testID="login-otp-input" label="One-time password" value={code} onChangeText={(text) => { setCode(text.replace(/[^0-9]/g, "").slice(0, 6)); setError(null); }} placeholder="••••••" keyboardType="number-pad" maxLength={6} center autoFocus error={error} />
          <Button testID="login-verify-button" label="Verify & Login" onPress={handleVerifyUser} loading={loading} disabled={code.length !== 6} icon={<Ionicons name="lock-open-outline" size={18} color={colors.onBrand} />} />
          <View style={styles.resendRow}>
            <Pressable onPress={() => resetEntry("user")}><AppText variant="label" color={colors.brand}>← Change number</AppText></Pressable>
            <Pressable testID="login-resend-otp" onPress={resendCurrentOtp} disabled={countdown > 0}><AppText variant="label" color={countdown > 0 ? colors.onSurfaceTertiary : colors.brand}>{countdown > 0 ? `Resend in ${countdown}s` : "Resend OTP"}</AppText></Pressable>
          </View>
        </View>
      );
    }

    if (phase === "staff_email_otp") {
      return (
        <>
          {codeInput("Verify approved email", "login-plant-otp-input", handleVerifyStaffEmail, "Verify & Continue")}
          <View style={styles.resendRow}>
            <Pressable onPress={() => resetEntry("plant")}><AppText variant="label" color={colors.brand}>← Change email</AppText></Pressable>
            <Pressable testID="login-plant-resend-otp" onPress={resendCurrentOtp} disabled={countdown > 0}><AppText variant="label" color={countdown > 0 ? colors.onSurfaceTertiary : colors.brand}>{countdown > 0 ? `Resend in ${countdown}s` : "Resend email code"}</AppText></Pressable>
          </View>
          <View style={[styles.infoCard, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
            <Ionicons name="information-circle-outline" size={20} color={colors.brand} />
            <AppText variant="caption" style={{ flex: 1 }}>This one-time email check is used only to activate Authenticator security for an approved staff account.</AppText>
          </View>
        </>
      );
    }

    if (phase === "staff_passkey") {
      return (
        <View style={styles.formGap}>
          <View style={styles.securityHeading}>
            <View style={[styles.securityIcon, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name="finger-print-outline" size={26} color={colors.brand} />
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <AppText variant="heading">Passkey</AppText>
              <AppText variant="bodyMuted">Phishing-resistant verification for {plantEmail}</AppText>
            </View>
          </View>
          <Button testID="login-plant-passkey" label="Continue with Passkey" onPress={handleVerifyPasskey} loading={loading} icon={<Ionicons name="finger-print-outline" size={20} color={colors.onBrand} />} />
          {error ? <AppText variant="caption" center color={colors.error}>{error}</AppText> : null}
          <View style={styles.resendRow}>
            <Pressable onPress={() => resetEntry("plant")}><AppText variant="label" color={colors.brand}>← Change email</AppText></Pressable>
            <Pressable testID="login-use-authenticator" onPress={() => { setCode(""); setError(null); setPhase("staff_totp"); }}><AppText variant="label" color={colors.brand}>Use Authenticator</AppText></Pressable>
          </View>
          <View style={[styles.infoCard, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
            <Ionicons name="shield-checkmark-outline" size={20} color={colors.brand} />
            <AppText variant="caption" style={{ flex: 1 }}>Your device confirms your fingerprint, face, PIN, or saved passkey. TrackMyRMC never receives your biometric data or private passkey key.</AppText>
          </View>
        </View>
      );
    }

    if (phase === "staff_totp") {
      return (
        <>
          {codeInput("Authenticator App", "login-plant-authenticator-input", handleVerifyAuthenticator, "Verify & Login")}
          <View style={styles.resendRow}>
            <Pressable onPress={() => resetEntry("plant")}><AppText variant="label" color={colors.brand}>← Change email</AppText></Pressable>
            <Pressable testID="login-use-recovery" onPress={() => { setRecoveryCode(""); setCode(""); setError(null); setPhase("staff_recovery"); }}><AppText variant="label" color={colors.brand}>Use recovery code</AppText></Pressable>
          </View>
          <View style={[styles.infoCard, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
            <Ionicons name="time-outline" size={20} color={colors.brand} />
            <AppText variant="caption" style={{ flex: 1 }}>Enter the current 6-digit code from Google Authenticator, Microsoft Authenticator, Authy, 1Password, or another TOTP app.</AppText>
          </View>
        </>
      );
    }

    if (phase === "staff_recovery") {
      return (
        <View style={styles.formGap}>
          <View style={styles.securityHeading}>
            <View style={[styles.securityIcon, { backgroundColor: colors.brandSoft }]}><Ionicons name="key-outline" size={24} color={colors.brand} /></View>
            <View style={{ flex: 1, gap: 3 }}><AppText variant="heading">Recovery Code</AppText><AppText variant="bodyMuted">Use one saved one-time recovery code.</AppText></View>
          </View>
          <Input testID="login-plant-recovery-input" label="Recovery code" value={recoveryCode} onChangeText={(text) => { setRecoveryCode(text.toUpperCase().slice(0, 20)); setError(null); }} placeholder="ABCD-EFGH-JKLM" autoCapitalize="characters" autoCorrect={false} error={error} />
          <Button testID="login-plant-recovery-verify" label="Recover & Login" onPress={handleVerifyRecovery} loading={loading} icon={<Ionicons name="key-outline" size={18} color={colors.onBrand} />} />
          <Pressable onPress={() => { setError(null); setPhase("staff_totp"); }}><AppText variant="label" center color={colors.brand}>Back to Authenticator</AppText></Pressable>
        </View>
      );
    }

    if (mode === "user") {
      return (
        <View style={styles.formGap}>
          <View style={styles.formHeadingRow}>
            <View style={[styles.formIcon, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name="phone-portrait-outline" size={23} color={colors.brand} />
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <AppText variant="heading">Mobile Login</AppText>
              <AppText variant="bodyMuted">Enter your mobile number to continue</AppText>
            </View>
          </View>
          <View style={[styles.phoneInputWrap, { borderColor: error ? colors.error : colors.border, backgroundColor: colors.surfaceSecondary }]}>
            <View style={[styles.prefix, { borderRightColor: colors.border }]}><AppText style={styles.prefixText}>+91</AppText></View>
            <TextInput testID="login-mobile-input" value={mobile} onChangeText={(text) => { setMobile(text.replace(/\D/g, "").slice(0, 10)); setError(null); }} placeholder="Enter 10-digit mobile number" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="number-pad" maxLength={10} style={[styles.phoneInput, { color: colors.onSurface }]} />
          </View>
          {error ? <AppText variant="caption" color={colors.error}>{error}</AppText> : null}
          <Button testID="login-send-otp-button" label="SEND OTP" onPress={handleSendUserOtp} loading={loading} disabled={mobile.length !== 10} icon={<Ionicons name="shield-checkmark-outline" size={19} color={colors.onBrand} />} style={styles.primaryCta} />
          <View style={styles.secureLine}>
            <Ionicons name="shield-checkmark-outline" size={17} color={colors.onSurfaceTertiary} />
            <AppText variant="caption">Secure login</AppText>
          </View>
        </View>
      );
    }

    return (
      <View style={styles.formGap}>
        <View style={styles.formHeadingRow}>
          <View style={[styles.formIcon, { backgroundColor: colors.brandSoft }]}>
            <Ionicons name="people-outline" size={23} color={colors.brand} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <AppText variant="heading">Plant Staff Secure Login</AppText>
            <AppText variant="bodyMuted">Use your approved work email</AppText>
          </View>
        </View>
        <Input testID="login-plant-email-input" label="Work email" value={plantEmail} onChangeText={(text) => { setPlantEmail(text.trimStart().toLowerCase()); setError(null); setOnboardingRequired(false); }} placeholder="name@company.com" keyboardType="email-address" autoCapitalize="none" autoCorrect={false} error={error} />
        <Button testID="login-plant-send-otp" label="Continue Securely" onPress={handleStartPlantLogin} loading={loading} disabled={!validEmail(plantEmail)} icon={<Ionicons name="shield-checkmark-outline" size={18} color={colors.onBrand} />} style={styles.primaryCta} />
        <View style={[styles.securityStrip, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
          <Ionicons name="lock-closed-outline" size={19} color={colors.brand} />
          <AppText variant="caption" style={{ flex: 1 }}>Approved staff use Passkey first, with Authenticator and recovery codes as controlled fallbacks. New approved staff verify email once to activate security.</AppText>
        </View>
        {onboardingRequired ? (
          <View testID="login-onboarding-banner" style={[styles.onboardingCard, { borderColor: colors.brand + "55", backgroundColor: colors.brandSoft }]}> 
            <View style={[styles.onboardingIcon, { backgroundColor: colors.surface }]}><Ionicons name="business-outline" size={22} color={colors.brand} /></View>
            <View style={{ gap: spacing.xs }}>
              <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: colors.onSurface }}>Welcome to TrackMyRMC</AppText>
              <AppText variant="caption">This email is not currently associated with an approved TrackMyRMC plant account. Plant Owners and partners can submit onboarding details for Authority review.</AppText>
            </View>
            <Button testID="login-get-onboard" label="Get Onboard" onPress={openOnboarding} icon={<Ionicons name="arrow-forward-outline" size={18} color={colors.onBrand} />} />
          </View>
        ) : null}
      </View>
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={colors.isDark ? "light" : "dark"} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator={false}>
        <BrandHero topInset={insets.top} />

        <View style={[styles.loginShell, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}> 
          <View style={[styles.segmented, { backgroundColor: colors.surface, borderColor: colors.border }]}> 
            <Pressable testID="login-user-tab" onPress={() => resetEntry("user")} style={[styles.segment, mode === "user" && { backgroundColor: colors.brandSoft, borderColor: colors.brand }]}> 
              <Ionicons name="person" size={18} color={mode === "user" ? colors.brand : colors.onSurfaceTertiary} />
              <AppText style={styles.segmentLabel} color={mode === "user" ? colors.onSurface : colors.onSurfaceTertiary}>USER LOGIN</AppText>
            </Pressable>
            <Pressable testID="login-plant-tab" onPress={() => resetEntry("plant")} style={[styles.segment, mode === "plant" && { backgroundColor: colors.brandSoft, borderColor: colors.brand }]}> 
              <Ionicons name="people" size={18} color={mode === "plant" ? colors.brand : colors.onSurfaceTertiary} />
              <AppText style={styles.segmentLabel} color={mode === "plant" ? colors.onSurface : colors.onSurfaceTertiary}>PLANT STAFF LOGIN</AppText>
            </Pressable>
          </View>

          <View style={styles.formPanel}>{renderForm()}</View>

          {DEMO_LOGIN_ENABLED ? (
            <View style={[styles.demoBox, { borderColor: colors.border, backgroundColor: colors.surface }]}> 
              <AppText variant="label" style={styles.demoTitle}>Demo access (Google Play review)</AppText>
              <View style={styles.demoGrid}>{DEMO_ROLES.map((item) => (
                <Pressable key={item.role} testID={`demo-login-${item.role}`} disabled={loading} onPress={() => handleDemoLogin(item.role)} style={({ pressed }) => [styles.demoChip, { borderColor: colors.border, backgroundColor: pressed ? colors.brandSoft : colors.surfaceSecondary, opacity: loading ? 0.6 : 1 }]}> 
                  <Ionicons name={item.icon} size={18} color={colors.brand} /><AppText style={styles.demoChipLabel}>{item.label}</AppText>
                </Pressable>
              ))}</View>
            </View>
          ) : null}
        </View>

        <View style={styles.afterLogin}>
          <View style={styles.legalCardsRow}>
            <Pressable testID="login-privacy-card" onPress={() => { void Haptics.selectionAsync(); void openExternal(PRIVACY_POLICY_URL); }} style={[styles.legalCard, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}> 
              <View style={[styles.legalCardIcon, { backgroundColor: colors.brandSoft }]}><Ionicons name="shield-checkmark-outline" size={24} color={colors.brand} /></View>
              <View style={styles.legalCardBody}><AppText style={styles.legalCardTitle}>Privacy Policy</AppText><AppText style={styles.legalCardSub}>How TrackMyRMC uses your data</AppText></View>
              <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
            </Pressable>
            <Pressable testID="login-delete-account-card" onPress={confirmAccountDeletion} style={[styles.legalCard, { borderColor: "#F2C9C9", backgroundColor: colors.surfaceSecondary }]}> 
              <View style={[styles.legalCardIcon, { backgroundColor: "#FFE9E9" }]}><Ionicons name="trash-outline" size={24} color="#D93B3B" /></View>
              <View style={styles.legalCardBody}><AppText style={styles.legalCardTitle}>Delete Account</AppText><AppText style={styles.legalCardSub}>Erase your account without signing in</AppText></View>
              <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>

          <View style={styles.helpTitleRow}>
            <View style={[styles.helpRule, { backgroundColor: colors.border }]} />
            <AppText style={styles.helpTitle}>Need Help?</AppText>
            <View style={[styles.helpRule, { backgroundColor: colors.border }]} />
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.contactRow}>{CONTACT_ACTIONS.map((action) => {
            const iconColor = action.tone === "instagram" ? "#E1306C" : colors.brand;
            return (
              <Pressable key={action.label} onPress={() => openExternal(action.url)} style={[styles.contactAction, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}> 
                <View style={[styles.contactIconWrap, { backgroundColor: action.tone === "instagram" ? "#FFF0F5" : colors.brandSoft }]}>
                  <Ionicons name={action.icon} size={25} color={iconColor} />
                </View>
                <AppText style={styles.contactLabel}>{action.label}</AppText>
                <AppText style={styles.contactDetail} numberOfLines={1}>{action.detail}</AppText>
              </Pressable>
            );
          })}</ScrollView>

          <Pressable testID="login-review-access" onPress={() => router.push("/review-access" as any)} style={[styles.reviewCard, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}> 
            <View style={[styles.reviewIcon, { backgroundColor: colors.brandSoft }]}><Ionicons name="star" size={23} color={colors.brand} /></View>
            <View style={{ flex: 1 }}>
              <AppText style={styles.reviewTitle}>REVIEW APP</AppText>
              <AppText variant="caption">Your feedback helps us improve</AppText>
            </View>
            <View style={styles.starsRow}>{[0, 1, 2, 3, 4].map((n) => <Ionicons key={n} name="star" size={16} color={colors.brand} />)}</View>
          </Pressable>

          <AppText variant="caption" center style={styles.poweredBy}>Powered by <AppText variant="caption" style={styles.goldETech}>GOLD <AppText variant="caption" style={{ color: colors.brand, fontFamily: fonts.bold }}>e</AppText> TECH</AppText></AppText>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { height: 300, justifyContent: "center", overflow: "hidden" },
  loginShell: { marginTop: -18, marginHorizontal: spacing.md, borderRadius: 30, borderWidth: 1, padding: spacing.md, shadowColor: "#000", shadowOpacity: 0.10, shadowRadius: 22, shadowOffset: { width: 0, height: 8 }, elevation: 6 },
  segmented: { flexDirection: "row", borderRadius: 22, borderWidth: 1, padding: 4, marginBottom: spacing.md },
  segment: { flex: 1, minHeight: 54, borderRadius: 18, borderWidth: 1, borderColor: "transparent", alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8, paddingHorizontal: spacing.sm },
  segmentLabel: { fontFamily: fonts.semibold, fontSize: 11, letterSpacing: 0.2, textAlign: "center" },
  formPanel: { paddingHorizontal: spacing.sm, paddingVertical: spacing.sm },
  formGap: { gap: spacing.lg },
  formHeadingRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  formIcon: { width: 46, height: 46, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  phoneInputWrap: { flexDirection: "row", minHeight: 62, borderRadius: 16, borderWidth: 1, overflow: "hidden", alignItems: "stretch" },
  prefix: { width: 72, borderRightWidth: 1, alignItems: "center", justifyContent: "center" },
  prefixText: { fontFamily: fonts.bold, fontSize: fontSize.lg },
  phoneInput: { flex: 1, minHeight: 62, paddingHorizontal: spacing.md, fontFamily: fonts.medium, fontSize: fontSize.base },
  primaryCta: { height: 58, borderRadius: 16 },
  secureLine: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm },
  resendRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.md, marginTop: spacing.md },
  securityHeading: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  securityIcon: { width: 48, height: 48, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  securityStrip: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderRadius: radius.md },
  infoCard: { marginTop: spacing.md, flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderRadius: radius.md },
  onboardingCard: { borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  onboardingIcon: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  demoBox: { marginTop: spacing.xl, borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: spacing.sm },
  demoTitle: { textAlign: "center" },
  demoGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, justifyContent: "center" },
  demoChip: { minHeight: 44, flexGrow: 1, minWidth: "45%", borderWidth: 1, borderRadius: radius.md, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  demoChipLabel: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  afterLogin: { paddingHorizontal: spacing.md, paddingTop: spacing.xl, paddingBottom: spacing["3xl"], gap: spacing.xl },
  legalCardsRow: { flexDirection: "row", gap: spacing.sm },
  legalCard: { flex: 1, minHeight: 92, borderWidth: 1, borderRadius: 20, flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md },
  legalCardIcon: { width: 46, height: 46, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  legalCardBody: { flex: 1, minWidth: 0, gap: 3 },
  legalCardTitle: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  legalCardSub: { fontFamily: fonts.regular, fontSize: 11, opacity: 0.72 },
  helpTitleRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.md },
  helpRule: { flex: 1, height: 1 },
  helpTitle: { fontFamily: fonts.bold, fontSize: fontSize.lg },
  contactRow: { gap: spacing.sm, paddingBottom: spacing.xs },
  contactAction: { width: 124, minHeight: 112, borderWidth: 1, borderRadius: 18, alignItems: "center", justifyContent: "center", gap: 5, paddingHorizontal: spacing.sm, paddingVertical: spacing.md },
  contactIconWrap: { width: 46, height: 46, borderRadius: 16, alignItems: "center", justifyContent: "center", marginBottom: 2 },
  contactLabel: { fontFamily: fonts.semibold, fontSize: 12 },
  contactDetail: { fontFamily: fonts.regular, fontSize: 10, opacity: 0.72 },
  reviewCard: { minHeight: 82, borderWidth: 1, borderRadius: 20, flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.md, paddingVertical: spacing.md },
  reviewIcon: { width: 46, height: 46, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  reviewTitle: { fontFamily: fonts.bold, fontSize: fontSize.base },
  starsRow: { flexDirection: "row", gap: 1 },
  poweredBy: { marginTop: spacing.sm },
  goldETech: { fontFamily: fonts.bold },
});
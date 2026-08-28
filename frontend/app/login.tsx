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
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import * as Linking from "expo-linking";

import { useAuth } from "@/src/auth/AuthContext";
import { roleRouteFor } from "@/src/auth/roleRoutes";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Input } from "@/src/components/ui/Input";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const HERO = require("../assets/images/transit-mixer.jpg");

type LoginMode = "user" | "plant";
type LoginPhase = "enter" | "user_otp" | "staff_email_otp" | "staff_totp" | "staff_recovery";

type ContactAction = {
  label: string;
  detail: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  url: string;
};

const CONTACT_ACTIONS: ContactAction[] = [
  { label: "Support", detail: "+91 9594177870", icon: "logo-whatsapp", url: "https://wa.me/919594177870" },
  { label: "Query", detail: "+91 9082189911", icon: "logo-whatsapp", url: "https://wa.me/919082189911" },
  { label: "Instagram", detail: "@trackmyrmc", icon: "logo-instagram", url: "https://www.instagram.com/trackmyrmc?igsi=MXQ5YnVpbmkyMmw1dA==" },
  { label: "Email", detail: "support@goldetech.com", icon: "mail-outline", url: "mailto:support@goldetech.com" },
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
        setPhase("staff_totp");
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

  const finishLogin = (me: Awaited<ReturnType<typeof verify>>) => {
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    toast(`Welcome, ${me.name}`, "success");
    if (me.mfa_configured && !me.mfa_enabled && me.role !== "customer" && me.role !== "driver") {
      router.replace("/mfa-setup" as any);
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

  const handleVerifyAuthenticator = async () => {
    setError(null);
    if (code.trim().length !== 6) {
      setError("Enter the 6-digit Authenticator code");
      return;
    }
    setLoading(true);
    try {
      const me = await verifyStaffAuthenticator(identifier, code.trim());
      finishLogin(me);
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
        <View style={[styles.securityIcon, { backgroundColor: colors.brand + "18" }]}>
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
          <AppText variant="heading">Verify OTP</AppText>
          <AppText variant="bodyMuted">OTP sent to +91 {mobile}</AppText>
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
            <View style={[styles.securityIcon, { backgroundColor: colors.brand + "18" }]}><Ionicons name="key-outline" size={24} color={colors.brand} /></View>
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
          <AppText variant="heading">Mobile Login</AppText>
          <View style={[styles.phoneInputWrap, { borderColor: error ? colors.error : colors.border, backgroundColor: colors.surfaceSecondary }]}>
            <View style={[styles.prefix, { borderRightColor: colors.border }]}><AppText style={styles.prefixText}>+91</AppText></View>
            <TextInput testID="login-mobile-input" value={mobile} onChangeText={(text) => { setMobile(text.replace(/\D/g, "").slice(0, 10)); setError(null); }} placeholder="10-digit mobile number" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="number-pad" maxLength={10} style={[styles.phoneInput, { color: colors.onSurface }]} />
          </View>
          {error ? <AppText variant="caption" color={colors.error}>{error}</AppText> : null}
          <Button testID="login-send-otp-button" label="Send OTP" onPress={handleSendUserOtp} loading={loading} disabled={mobile.length !== 10} icon={<Ionicons name="phone-portrait-outline" size={18} color={colors.onBrand} />} />
        </View>
      );
    }

    return (
      <View style={styles.formGap}>
        <View style={{ gap: spacing.xs }}>
          <AppText variant="heading">Plant Staff Secure Login</AppText>
          <AppText variant="bodyMuted">Use the approved work email for your Plant Owner, staff, Authority, or Central Admin account.</AppText>
        </View>
        <Input testID="login-plant-email-input" label="Work email" value={plantEmail} onChangeText={(text) => { setPlantEmail(text.trimStart().toLowerCase()); setError(null); setOnboardingRequired(false); }} placeholder="name@company.com" keyboardType="email-address" autoCapitalize="none" autoCorrect={false} error={error} />
        <Button testID="login-plant-send-otp" label="Continue Securely" onPress={handleStartPlantLogin} loading={loading} disabled={!validEmail(plantEmail)} icon={<Ionicons name="shield-checkmark-outline" size={18} color={colors.onBrand} />} />
        <View style={[styles.securityStrip, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
          <Ionicons name="shield-checkmark" size={19} color={colors.brand} />
          <AppText variant="caption" style={{ flex: 1 }}>Approved staff use Authenticator App security. New approved staff verify email once to activate it.</AppText>
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
      <StatusBar style="light" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Image source={HERO} style={StyleSheet.absoluteFill} contentFit="contain" />
          <LinearGradient pointerEvents="none" colors={["rgba(5,24,20,0.78)", "rgba(5,24,20,0.12)", colors.surface]} locations={[0, 0.62, 1]} style={StyleSheet.absoluteFill} />
          <View style={[styles.brandWrap, { paddingTop: insets.top + spacing.lg }]}>
            <AppText style={styles.brand} color="#FFFFFF">TRACK MY RMC</AppText>
            <AppText style={styles.brandSub} color="rgba(255,255,255,0.78)">Secure access for concrete operations</AppText>
          </View>
        </View>

        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[styles.segmented, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
            <Pressable testID="login-user-tab" onPress={() => resetEntry("user")} style={[styles.segment, mode === "user" && { backgroundColor: colors.brand }]}>
              <AppText style={styles.segmentLabel} color={mode === "user" ? colors.onBrand : colors.onSurfaceTertiary}>USER LOGIN</AppText>
            </Pressable>
            <Pressable testID="login-plant-tab" onPress={() => resetEntry("plant")} style={[styles.segment, mode === "plant" && { backgroundColor: colors.brand }]}>
              <AppText style={styles.segmentLabel} color={mode === "plant" ? colors.onBrand : colors.onSurfaceTertiary}>PLANT STAFF LOGIN</AppText>
            </Pressable>
          </View>

          {renderForm()}

          {DEMO_LOGIN_ENABLED ? (
            <View style={[styles.demoBox, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}>
              <AppText variant="label" style={styles.demoTitle}>Demo access (Google Play review)</AppText>
              <View style={styles.demoGrid}>{DEMO_ROLES.map((item) => (
                <Pressable key={item.role} testID={`demo-login-${item.role}`} disabled={loading} onPress={() => handleDemoLogin(item.role)} style={({ pressed }) => [styles.demoChip, { borderColor: colors.border, backgroundColor: pressed ? colors.brand + "1A" : colors.surface, opacity: loading ? 0.6 : 1 }]}>
                  <Ionicons name={item.icon} size={18} color={colors.brand} /><AppText style={styles.demoChipLabel}>{item.label}</AppText>
                </Pressable>
              ))}</View>
            </View>
          ) : null}

          <View style={styles.legal}>
            <View style={styles.legalCardsRow}>
              <Pressable testID="login-privacy-card" onPress={() => { void Haptics.selectionAsync(); void openExternal(PRIVACY_POLICY_URL); }} style={[styles.legalCard, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}>
                <View style={[styles.legalCardIcon, { backgroundColor: colors.brand + "1A" }]}><Ionicons name="shield-checkmark-outline" size={21} color={colors.brand} /></View>
                <View style={styles.legalCardBody}><AppText style={styles.legalCardTitle}>Privacy Policy</AppText><AppText style={styles.legalCardSub}>How TrackMyRMC uses your data</AppText></View>
              </Pressable>
              <Pressable testID="login-delete-account-card" onPress={confirmAccountDeletion} style={[styles.legalCard, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}>
                <View style={[styles.legalCardIcon, { backgroundColor: "#E45B5B22" }]}><Ionicons name="trash-outline" size={21} color="#E45B5B" /></View>
                <View style={styles.legalCardBody}><AppText style={styles.legalCardTitle}>Delete Account</AppText><AppText style={styles.legalCardSub}>Erase your account without signing in</AppText></View>
              </Pressable>
            </View>

            <View style={styles.legalRow}>
              <Pressable onPress={() => router.push("/privacy")}><AppText variant="caption" color={colors.brand}>Privacy Policy</AppText></Pressable><AppText variant="caption">·</AppText>
              <Pressable onPress={() => router.push("/account-deletion-public")}><AppText variant="caption" color={colors.brand}>Delete Account</AppText></Pressable><AppText variant="caption">·</AppText>
              <Pressable testID="login-review-access" onPress={() => router.push("/review-access" as any)}><AppText variant="caption" color={colors.brand}>App Review Access</AppText></Pressable>
            </View>

            <AppText variant="caption" center style={styles.poweredBy}>Powered by <AppText variant="caption" style={styles.goldETech}>GOLD e TECH</AppText></AppText>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.contactRow}>{CONTACT_ACTIONS.map((action) => (
              <Pressable key={action.label} onPress={() => openExternal(action.url)} style={[styles.contactAction, { borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}>
                <Ionicons name={action.icon} size={20} color={colors.brand} /><AppText style={styles.contactLabel}>{action.label}</AppText><AppText style={styles.contactDetail} numberOfLines={1}>{action.detail}</AppText>
              </Pressable>
            ))}</ScrollView>
          </View>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { height: 300, justifyContent: "flex-start", backgroundColor: "#071B17" },
  brandWrap: { alignItems: "center", paddingHorizontal: spacing.xl, gap: 4 },
  brand: { fontFamily: fonts.displayBold, fontSize: 26, letterSpacing: 1.2 },
  brandSub: { fontFamily: fonts.medium, fontSize: 12, letterSpacing: 0.2 },
  card: { flex: 1, marginTop: -24, marginHorizontal: spacing.md, borderRadius: 28, borderWidth: 1, paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing["2xl"], shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 5 },
  segmented: { flexDirection: "row", borderRadius: radius.lg, borderWidth: 1, padding: 4, marginBottom: spacing.xl },
  segment: { flex: 1, minHeight: 44, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.sm },
  segmentLabel: { fontFamily: fonts.semibold, fontSize: 11, letterSpacing: 0.25, textAlign: "center" },
  formGap: { gap: spacing.lg },
  phoneInputWrap: { flexDirection: "row", minHeight: 56, borderRadius: radius.md, borderWidth: 1, overflow: "hidden", alignItems: "stretch" },
  prefix: { width: 66, borderRightWidth: 1, alignItems: "center", justifyContent: "center" },
  prefixText: { fontFamily: fonts.semibold, fontSize: fontSize.base },
  phoneInput: { flex: 1, minHeight: 56, paddingHorizontal: spacing.md, fontFamily: fonts.medium, fontSize: fontSize.base },
  resendRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.md, marginTop: spacing.md },
  securityHeading: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  securityIcon: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  securityStrip: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderRadius: radius.md },
  infoCard: { marginTop: spacing.md, flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderRadius: radius.md },
  onboardingCard: { borderWidth: 1, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  onboardingIcon: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  demoBox: { marginTop: spacing.xl, borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: spacing.sm },
  demoTitle: { textAlign: "center" },
  demoGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, justifyContent: "center" },
  demoChip: { minHeight: 44, flexGrow: 1, minWidth: "45%", borderWidth: 1, borderRadius: radius.md, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  demoChipLabel: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  legal: { marginTop: spacing["2xl"], paddingTop: spacing.lg },
  legalCardsRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  legalCard: { flex: 1, minHeight: 76, borderWidth: 1, borderRadius: radius.md, flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.sm },
  legalCardIcon: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  legalCardBody: { flex: 1, minWidth: 0, gap: 2 },
  legalCardTitle: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  legalCardSub: { fontFamily: fonts.regular, fontSize: 11, opacity: 0.72 },
  legalRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", alignItems: "center", gap: spacing.sm },
  poweredBy: { marginTop: spacing.lg },
  goldETech: { fontFamily: fonts.bold },
  contactRow: { gap: spacing.sm, paddingTop: spacing.lg, paddingBottom: spacing.sm },
  contactAction: { width: 122, minHeight: 76, borderWidth: 1, borderRadius: radius.md, alignItems: "center", justifyContent: "center", gap: 3, paddingHorizontal: spacing.sm },
  contactLabel: { fontFamily: fonts.semibold, fontSize: 12 },
  contactDetail: { fontFamily: fonts.regular, fontSize: 10, opacity: 0.72 },
});

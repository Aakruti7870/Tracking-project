import React, { useEffect, useMemo, useRef } from "react";
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { AppText } from "@/src/components/ui/AppText";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

export type OtpVisualState = "idle" | "checking" | "error" | "success";

type Props = {
  value: string;
  onChangeText: (value: string) => void;
  onComplete: (value: string) => void;
  state: OtpVisualState;
  title: string;
  subtitle: string;
  errorText?: string | null;
  countdown?: number;
  onResend?: () => void;
  resendLabel?: string;
  successSubtitle?: string;
  autoFocus?: boolean;
  testID?: string;
  colors: {
    surface: string;
    surfaceSecondary: string;
    onSurface: string;
    onSurfaceSecondary: string;
    onSurfaceTertiary: string;
    border: string;
    brand: string;
    error: string;
  };
};

const OTP_LENGTH = 6;
const SUCCESS = "#28C48D";
const ERROR = "#E5484D";
const SLOT = 52;
const ORBIT = 210;

const positions = [
  { left: 79, top: 4, transform: [{ rotate: "-8deg" }] },
  { left: 145, top: 43, transform: [{ rotate: "8deg" }] },
  { left: 145, top: 116, transform: [{ rotate: "-7deg" }] },
  { left: 79, top: 154, transform: [{ rotate: "7deg" }] },
  { left: 13, top: 116, transform: [{ rotate: "-8deg" }] },
  { left: 13, top: 43, transform: [{ rotate: "8deg" }] },
] as const;

export function OtpOrbitVerification({
  value,
  onChangeText,
  onComplete,
  state,
  title,
  subtitle,
  errorText,
  countdown = 0,
  onResend,
  resendLabel = "Resend OTP",
  successSubtitle = "Your verification has been completed.",
  autoFocus = true,
  testID,
  colors,
}: Props) {
  const inputRef = useRef<TextInput>(null);
  const spin = useRef(new Animated.Value(0)).current;
  const shake = useRef(new Animated.Value(0)).current;
  const successScale = useRef(new Animated.Value(0.82)).current;
  const lastCompleted = useRef("");

  const digits = useMemo(
    () => Array.from({ length: OTP_LENGTH }, (_, i) => value[i] || ""),
    [value],
  );

  useEffect(() => {
    if (state === "checking") {
      spin.setValue(0);
      const animation = Animated.loop(
        Animated.timing(spin, {
          toValue: 1,
          duration: 850,
          easing: Easing.linear,
          useNativeDriver: true,
        }),
      );
      animation.start();
      return () => animation.stop();
    }
    spin.stopAnimation();
    return undefined;
  }, [spin, state]);

  useEffect(() => {
    if (state === "error") {
      shake.setValue(0);
      Animated.sequence([
        Animated.timing(shake, { toValue: -7, duration: 70, useNativeDriver: true }),
        Animated.timing(shake, { toValue: 7, duration: 90, useNativeDriver: true }),
        Animated.timing(shake, { toValue: -4, duration: 80, useNativeDriver: true }),
        Animated.timing(shake, { toValue: 0, duration: 70, useNativeDriver: true }),
      ]).start();
    }
  }, [shake, state]);

  useEffect(() => {
    if (state === "success") {
      successScale.setValue(0.82);
      Animated.spring(successScale, {
        toValue: 1,
        damping: 9,
        stiffness: 140,
        mass: 0.8,
        useNativeDriver: true,
      }).start();
    }
  }, [state, successScale]);

  useEffect(() => {
    if (state !== "idle") return;
    if (value.length === OTP_LENGTH && value !== lastCompleted.current) {
      lastCompleted.current = value;
      onComplete(value);
    }
    if (value.length < OTP_LENGTH) lastCompleted.current = "";
  }, [onComplete, state, value]);

  const sanitize = (text: string) => text.replace(/\D/g, "").slice(0, OTP_LENGTH);
  const ringRotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const stateColor = state === "success" ? SUCCESS : state === "error" ? ERROR : colors.brand;

  if (state === "success") {
    return (
      <View style={[styles.card, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
        <AppText style={[styles.successTitle, { color: SUCCESS }]}>Verified successfully</AppText>
        <AppText variant="bodyMuted" center>{successSubtitle}</AppText>
        <Animated.View style={[styles.successVisual, { transform: [{ scale: successScale }] }]}>
          <View style={[styles.successRingOuter, { borderColor: `${SUCCESS}35` }]} />
          <View style={[styles.successRingInner, { borderColor: `${SUCCESS}55` }]} />
          <View style={[styles.successCheck, { borderColor: SUCCESS, backgroundColor: `${SUCCESS}18` }]}>
            <Ionicons name="checkmark" size={34} color={SUCCESS} />
          </View>
        </Animated.View>
        <View style={styles.secureRow}>
          <Ionicons name="lock-closed-outline" size={16} color={SUCCESS} />
          <AppText style={[styles.secureText, { color: SUCCESS }]}>Verified and secure</AppText>
        </View>
      </View>
    );
  }

  return (
    <Pressable onPress={() => inputRef.current?.focus()}>
      <Animated.View
        style={[
          styles.card,
          { backgroundColor: colors.surfaceSecondary, borderColor: state === "error" ? `${ERROR}88` : colors.border },
          { transform: [{ translateX: shake }] },
        ]}
      >
        <View style={[styles.grabber, { backgroundColor: colors.border }]} />
        <AppText style={[styles.title, { color: colors.onSurface }]}>{title}</AppText>
        <AppText variant="bodyMuted" center style={styles.subtitle}>{subtitle}</AppText>

        <TextInput
          ref={inputRef}
          testID={testID}
          value={value}
          onChangeText={(text) => onChangeText(sanitize(text))}
          keyboardType="number-pad"
          inputMode="numeric"
          maxLength={OTP_LENGTH}
          autoFocus={autoFocus}
          editable={state !== "checking"}
          autoComplete={Platform.OS === "android" ? "sms-otp" : "one-time-code"}
          textContentType="oneTimeCode"
          importantForAutofill="yes"
          style={styles.nativeInput}
          accessibilityLabel="Six digit verification code"
        />

        <View style={styles.orbit}>
          <Animated.View
            style={[
              styles.orbitRing,
              { borderColor: state === "error" ? `${ERROR}66` : colors.border },
              state === "checking" && { borderColor: `${SUCCESS}88`, transform: [{ rotate: ringRotate }] },
            ]}
          />
          <View style={[styles.hub, { backgroundColor: state === "checking" ? SUCCESS : colors.onSurface }]} />
          {digits.map((digit, index) => (
            <View
              key={index}
              style={[
                styles.slot,
                positions[index],
                {
                  borderColor: state === "error" ? ERROR : digit ? `${stateColor}BB` : colors.border,
                  backgroundColor: state === "error" ? `${ERROR}13` : colors.surface,
                },
                state === "checking" && styles.slotChecking,
              ]}
            >
              <AppText style={[styles.digit, { color: state === "error" ? ERROR : colors.onSurface }]}>{digit}</AppText>
            </View>
          ))}
          {state === "checking" ? (
            <Animated.View style={[styles.checkingDot, { borderColor: `${SUCCESS}44`, borderTopColor: SUCCESS, transform: [{ rotate: ringRotate }] }]} />
          ) : null}
        </View>

        {state === "error" ? (
          <AppText style={[styles.errorText, { color: ERROR }]} center>{errorText || "Incorrect OTP. Please try again."}</AppText>
        ) : null}

        {onResend ? (
          <View style={styles.resendRow}>
            <AppText variant="caption">Didn&apos;t receive the code?</AppText>
            {countdown > 0 ? (
              <AppText variant="caption">Resend in {countdown}s</AppText>
            ) : (
              <Pressable onPress={onResend} hitSlop={10}>
                <AppText style={[styles.resendLink, { color: colors.brand }]}>{resendLabel}</AppText>
              </Pressable>
            )}
          </View>
        ) : null}
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "100%",
    maxWidth: 430,
    alignSelf: "center",
    borderWidth: 1,
    borderRadius: 24,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
  },
  grabber: { width: 40, height: 4, borderRadius: 99, alignSelf: "center", marginBottom: spacing.lg },
  title: { fontFamily: fonts.bold, fontSize: fontSize.xl, textAlign: "center" },
  subtitle: { marginTop: spacing.sm, paddingHorizontal: spacing.sm },
  nativeInput: { position: "absolute", width: 2, height: 2, opacity: 0.01 },
  orbit: { width: ORBIT, height: ORBIT, alignSelf: "center", marginTop: spacing.lg, marginBottom: spacing.sm },
  orbitRing: { position: "absolute", width: 104, height: 104, left: 53, top: 53, borderWidth: 1.5, borderRadius: 52, borderStyle: "dashed" },
  hub: { position: "absolute", width: 8, height: 8, left: 101, top: 101, borderRadius: 4, opacity: 0.9 },
  slot: { position: "absolute", width: SLOT, height: SLOT, borderWidth: 1.5, borderRadius: radius.lg, alignItems: "center", justifyContent: "center" },
  slotChecking: { opacity: 0.28 },
  digit: { fontFamily: fonts.bold, fontSize: 22 },
  checkingDot: { position: "absolute", width: 28, height: 28, left: 91, top: 91, borderWidth: 3, borderRadius: 14 },
  errorText: { fontFamily: fonts.semibold, fontSize: fontSize.sm, marginTop: spacing.xs },
  resendRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, flexWrap: "wrap", marginTop: spacing.md },
  resendLink: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
  successTitle: { fontFamily: fonts.bold, fontSize: fontSize.xl, textAlign: "center", marginTop: spacing.md },
  successVisual: { width: 180, height: 180, alignSelf: "center", alignItems: "center", justifyContent: "center", marginVertical: spacing.lg },
  successRingOuter: { position: "absolute", width: 170, height: 170, borderWidth: 1, borderRadius: 40 },
  successRingInner: { position: "absolute", width: 116, height: 116, borderWidth: 1, borderRadius: 30 },
  successCheck: { width: 70, height: 70, borderWidth: 2, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  secureRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs },
  secureText: { fontFamily: fonts.semibold, fontSize: fontSize.sm },
});

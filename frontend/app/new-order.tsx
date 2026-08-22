import React, { useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { PlantData } from "@/src/components/PlantCard";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

const TIME_SLOTS = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00"];

function nextDays(n: number) {
  const out: { value: string; label: string; sub: string }[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const value = d.toISOString().slice(0, 10);
    const label = i === 0 ? "Today" : i === 1 ? "Tomorrow" : d.toLocaleDateString(undefined, { weekday: "short" });
    const sub = d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
    out.push({ value, label, sub });
  }
  return out;
}

export default function NewOrder() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { token, user } = useAuth();
  const params = useLocalSearchParams<{ plantId?: string }>();
  const { data: plantsData } = useGet<{ plants: PlantData[] }>("/customer/plants");

  const days = useMemo(() => nextDays(7), []);
  const [plantId, setPlantId] = useState<string | null>(params.plantId || null);
  const [grade, setGrade] = useState<string | null>(null);
  const [quantity, setQuantity] = useState("6");
  const [date, setDate] = useState(days[1].value);
  const [time, setTime] = useState<string | null>("10:00");
  const [siteName, setSiteName] = useState("");
  const [address, setAddress] = useState("");
  const [contact, setContact] = useState(user?.name || "");
  const [mobile, setMobile] = useState(user?.phone || "");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState<null | "order" | "draft">(null);
  const [error, setError] = useState<string | null>(null);

  const plants = plantsData?.plants || [];
  const selectedPlant = plants.find((p) => p.id === plantId) || null;
  const grades = selectedPlant?.grades || [];
  const kycOk = user?.kyc_status === "VERIFIED";

  const submit = async (draft: boolean) => {
    setError(null);
    if (!plantId) return setError("Choose a plant");
    if (!grade) return setError("Select a concrete grade");
    if (!quantity || Number(quantity) <= 0) return setError("Enter a valid quantity");
    if (!siteName.trim()) return setError("Enter the site name");
    if (!address.trim()) return setError("Enter the delivery address");
    if (!draft && !kycOk) {
      toast("Complete KYC to place an order", "info");
      return router.push("/kyc");
    }
    setSubmitting(draft ? "draft" : "order");
    try {
      const res: any = await apiPost("/customer/orders", token!, {
        plant_id: plantId,
        grade,
        quantity: Number(quantity),
        site_name: siteName.trim(),
        site_address: address.trim(),
        delivery_date: date,
        delivery_time: time,
        contact_person: contact.trim() || null,
        contact_mobile: mobile.trim() || null,
        notes: notes.trim() || null,
        save_draft: draft,
      });
      toast(draft ? "Draft saved" : "Order placed!", "success");
      router.replace(`/order/${res.id}` as any);
    } catch (e: any) {
      if (e.detail === "KYC_REQUIRED") {
        toast("Complete KYC to place an order", "info");
        router.push("/kyc");
      } else {
        setError(e.detail || "Could not place order");
      }
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="neworder-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">New Order</AppText>
      </View>

      <KeyboardAwareScrollView
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"], gap: spacing.lg }}
        showsVerticalScrollIndicator={false}
      >
        {!kycOk ? (
          <Pressable onPress={() => router.push("/kyc")} style={[styles.warn, { backgroundColor: colors.warning + "1A", borderColor: colors.warning + "55" }]}>
            <Ionicons name="alert-circle-outline" size={18} color={colors.warning} />
            <AppText variant="caption" style={{ flex: 1 }}>Complete KYC to place a live order. You can still save a draft.</AppText>
          </Pressable>
        ) : null}

        {/* Plant */}
        <Section title="Choose Plant">
          <View style={{ gap: spacing.sm }}>
            {plants.map((p) => {
              const sel = p.id === plantId;
              return (
                <Pressable
                  key={p.id}
                  testID={`neworder-plant-${p.id}`}
                  onPress={() => { setPlantId(p.id); setGrade(null); }}
                  style={[styles.plantRow, { borderColor: sel ? colors.brand : colors.border, backgroundColor: sel ? colors.brandSoft : colors.surfaceSecondary }]}
                >
                  <Ionicons name={sel ? "radio-button-on" : "radio-button-off"} size={20} color={sel ? colors.brand : colors.onSurfaceTertiary} />
                  <View style={{ flex: 1 }}>
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }}>{p.name}</AppText>
                    <AppText variant="caption">{p.city}</AppText>
                  </View>
                  <Ionicons name="shield-checkmark" size={16} color={colors.success} />
                </Pressable>
              );
            })}
          </View>
        </Section>

        {/* Grade */}
        {selectedPlant ? (
          <Section title="Concrete Grade">
            <View style={styles.chips}>
              {grades.map((g) => {
                const sel = g === grade;
                return (
                  <Pressable key={g} testID={`grade-${g}`} onPress={() => setGrade(g)} style={[styles.chip, { backgroundColor: sel ? colors.brand : colors.surfaceSecondary, borderColor: sel ? colors.brand : colors.border }]}>
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: 13, color: sel ? colors.onBrand : colors.onSurfaceSecondary }}>{g}</AppText>
                  </Pressable>
                );
              })}
            </View>
          </Section>
        ) : null}

        {/* Quantity */}
        <Section title="Quantity (m³)">
          <View style={styles.stepper}>
            <Stepper icon="remove" onPress={() => setQuantity((q) => String(Math.max(1, Number(q) - 1)))} colors={colors} />
            <View style={{ flex: 1 }}>
              <Input testID="neworder-quantity" value={quantity} onChangeText={(t) => setQuantity(t.replace(/[^0-9.]/g, ""))} keyboardType="numeric" center />
            </View>
            <Stepper icon="add" onPress={() => setQuantity((q) => String(Number(q || "0") + 1))} colors={colors} />
          </View>
        </Section>

        {/* Date */}
        <Section title="Delivery Date">
          <View style={styles.chips}>
            {days.map((d) => {
              const sel = d.value === date;
              return (
                <Pressable key={d.value} testID={`date-${d.value}`} onPress={() => setDate(d.value)} style={[styles.dateChip, { backgroundColor: sel ? colors.brand : colors.surfaceSecondary, borderColor: sel ? colors.brand : colors.border }]}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: sel ? colors.onBrand : colors.onSurface }}>{d.label}</AppText>
                  <AppText style={{ fontFamily: fonts.regular, fontSize: 10, color: sel ? colors.onBrand : colors.onSurfaceTertiary }}>{d.sub}</AppText>
                </Pressable>
              );
            })}
          </View>
        </Section>

        {/* Time */}
        <Section title="Preferred Time">
          <View style={styles.chips}>
            {TIME_SLOTS.map((t) => {
              const sel = t === time;
              return (
                <Pressable key={t} testID={`time-${t}`} onPress={() => setTime(t)} style={[styles.chip, { backgroundColor: sel ? colors.brand : colors.surfaceSecondary, borderColor: sel ? colors.brand : colors.border }]}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 13, color: sel ? colors.onBrand : colors.onSurfaceSecondary }}>{t}</AppText>
                </Pressable>
              );
            })}
          </View>
        </Section>

        {/* Site details */}
        <Section title="Site Details">
          <View style={{ gap: spacing.md }}>
            <Input testID="neworder-site" label="Site name" value={siteName} onChangeText={setSiteName} placeholder="e.g. Skyline Towers" autoCapitalize="words" />
            <Input testID="neworder-address" label="Delivery address" value={address} onChangeText={setAddress} placeholder="Full site address" autoCapitalize="sentences" />
            <Input testID="neworder-contact" label="Contact person" value={contact} onChangeText={setContact} placeholder="Name at site" autoCapitalize="words" />
            <Input testID="neworder-mobile" label="Contact mobile" value={mobile} onChangeText={setMobile} placeholder="+91…" keyboardType="phone-pad" />
            <Input testID="neworder-notes" label="Notes (optional)" value={notes} onChangeText={setNotes} placeholder="e.g. Pump required" autoCapitalize="sentences" />
          </View>
        </Section>

        {error ? (
          <View style={[styles.warn, { backgroundColor: colors.error + "1A", borderColor: colors.error + "55" }]}>
            <Ionicons name="close-circle-outline" size={18} color={colors.error} />
            <AppText variant="caption" color={colors.error} style={{ flex: 1 }}>{error}</AppText>
          </View>
        ) : null}

        <View style={{ gap: spacing.sm }}>
          <Button testID="neworder-place" label="Place Order" onPress={() => submit(false)} loading={submitting === "order"} icon={<Ionicons name="checkmark-circle-outline" size={18} color={colors.onBrand} />} />
          <Button testID="neworder-draft" label="Save Draft" variant="outline" onPress={() => submit(true)} loading={submitting === "draft"} />
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: spacing.sm }}>
      <AppText variant="heading">{title}</AppText>
      {children}
    </View>
  );
}

function Stepper({ icon, onPress, colors }: any) {
  return (
    <Pressable onPress={onPress} style={[styles.stepBtn, { backgroundColor: colors.surfaceTertiary }]}>
      <Ionicons name={icon} size={20} color={colors.onSurface} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  warn: { flexDirection: "row", gap: spacing.sm, alignItems: "center", borderWidth: 1, borderRadius: radius.md, padding: spacing.md },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  dateChip: { width: 72, paddingVertical: spacing.sm, borderRadius: radius.md, borderWidth: 1, alignItems: "center", gap: 2 },
  plantRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  stepper: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  stepBtn: { width: 52, height: 52, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
});

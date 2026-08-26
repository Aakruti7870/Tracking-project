import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiGet, apiPost, apiPut } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { useToast } from "@/src/components/ui/Toast";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";

type Shift = { id: string; name: string; start_time: string; end_time: string };
type Employee = { user_id: string; name: string; role: string };
type Roster = { id: string; date: string; user_id: string; user_name?: string; shift_id?: string | null; week_off: boolean; shift?: Shift | null };
type Correction = { id: string; attendance_date: string; user_name?: string; reason: string; status: string };
type ExceptionRow = { id: string; date: string; user_id: string; user_name?: string; check_in_geofence_status?: string; check_out_geofence_status?: string };
type OwnerPlant = { plant_id: string; settings: any; shifts: Shift[]; roster: Roster[]; pending_corrections: Correction[]; geofence_exceptions: ExceptionRow[]; employees: Employee[] };
type OwnerResponse = { mode: "owner"; plants: OwnerPlant[] };
type MeResponse = { plant_id: string; timezone_name: string; geofence_enabled: boolean; roster: Roster[]; corrections: Correction[] };

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function localIso(day: string, hhmm: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !/^\d{2}:\d{2}$/.test(hhmm)) return null;
  const d = new Date(`${day}T${hhmm}:00`);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export default function WorkforceRulesScreen() {
  const { colors } = useTheme();
  const { token, user } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const ownerMode = user?.role === "plant_owner";
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [ownerData, setOwnerData] = useState<OwnerResponse | null>(null);
  const [meData, setMeData] = useState<MeResponse | null>(null);

  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [radius, setRadius] = useState("250");
  const [timezoneName, setTimezoneName] = useState("Asia/Kolkata");
  const [shiftName, setShiftName] = useState("");
  const [shiftStart, setShiftStart] = useState("09:00");
  const [shiftEnd, setShiftEnd] = useState("18:00");
  const [rosterDate, setRosterDate] = useState(todayKey());
  const [selectedEmployee, setSelectedEmployee] = useState<string | null>(null);
  const [selectedShift, setSelectedShift] = useState<string | null>(null);
  const [weekOff, setWeekOff] = useState(false);
  const [correctionDate, setCorrectionDate] = useState(todayKey());
  const [correctionIn, setCorrectionIn] = useState("");
  const [correctionOut, setCorrectionOut] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");

  const plant = ownerData?.plants?.[0] || null;

  const load = useCallback(async () => {
    if (!token || !user) { setLoading(false); return; }
    setLoading(true);
    try {
      if (ownerMode) {
        const data = await apiGet<OwnerResponse>("/workforce-rules/owner/control", token);
        setOwnerData(data);
        const first = data.plants?.[0];
        if (first?.settings) {
          setLat(first.settings.center_lat != null ? String(first.settings.center_lat) : "");
          setLng(first.settings.center_lng != null ? String(first.settings.center_lng) : "");
          setRadius(String(first.settings.radius_m || 250));
          setTimezoneName(first.settings.timezone_name || "Asia/Kolkata");
        }
      } else {
        setMeData(await apiGet<MeResponse>("/workforce-rules/me", token));
      }
    } catch (e: any) {
      toast(e?.detail || "Unable to load attendance rules", "error");
    } finally {
      setLoading(false);
    }
  }, [token, user, ownerMode, toast]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try { await fn(); toast(message, "success"); await load(); }
    catch (e: any) { toast(e?.detail || "Action failed", "error"); }
    finally { setBusy(false); }
  };

  const selectedEmployeeName = useMemo(() => plant?.employees.find((e) => e.user_id === selectedEmployee)?.name, [plant, selectedEmployee]);
  const selectedShiftName = useMemo(() => plant?.shifts.find((s) => s.id === selectedShift)?.name, [plant, selectedShift]);

  if (!user || (!ownerMode && ["customer", "authority", "central_admin"].includes(user.role))) {
    return <View style={[styles.center, { backgroundColor: colors.surface }]}><AppText>Attendance rules are not available for this role.</AppText></View>;
  }
  if (loading) return <View style={[styles.center, { backgroundColor: colors.surface }]}><ActivityIndicator color={colors.brand} /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={[styles.iconButton, { borderColor: colors.border }]}><Ionicons name="arrow-back" size={20} color={colors.onSurface} /></Pressable>
          <View style={{ flex: 1 }}><AppText variant="title">Shift & Attendance Rules</AppText><AppText variant="caption">Roster, geofence evidence, exceptions and corrections</AppText></View>
        </View>

        {ownerMode && plant ? <>
          <Card style={{ gap: spacing.md }}>
            <View style={styles.rowBetween}><AppText variant="heading">Plant Geofence</AppText><Badge label={plant.settings?.enabled ? "ENABLED" : "OFF"} color={plant.settings?.enabled ? colors.success : colors.warning} /></View>
            <Input label="Plant latitude" value={lat} onChangeText={setLat} keyboardType="decimal-pad" />
            <Input label="Plant longitude" value={lng} onChangeText={setLng} keyboardType="decimal-pad" />
            <Input label="Allowed radius (metres)" value={radius} onChangeText={setRadius} keyboardType="numeric" />
            <Input label="Timezone" value={timezoneName} onChangeText={setTimezoneName} />
            <Button label="Save Geofence" disabled={busy || !lat || !lng} onPress={() => run(() => apiPut(`/workforce-rules/plants/${plant.plant_id}/settings`, token!, { center_lat: Number(lat), center_lng: Number(lng), radius_m: Number(radius || 250), timezone_name: timezoneName, enabled: true, max_accuracy_m: 250 }), "Attendance geofence saved")} />
          </Card>

          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Shift Master</AppText>
            <Input label="Shift name" value={shiftName} onChangeText={setShiftName} placeholder="General Shift" />
            <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Start HH:MM" value={shiftStart} onChangeText={setShiftStart} /></View><View style={{ flex: 1 }}><Input label="End HH:MM" value={shiftEnd} onChangeText={setShiftEnd} /></View></View>
            <Button label="Create Shift" disabled={busy || shiftName.trim().length < 2} onPress={() => run(() => apiPost(`/workforce-rules/plants/${plant.plant_id}/shifts`, token!, { name: shiftName.trim(), start_time: shiftStart, end_time: shiftEnd, grace_minutes: 10, half_day_minutes: 240, full_day_minutes: 480, overtime_after_minutes: 540, active: true }), "Shift created")} />
            <View style={styles.wrap}>{plant.shifts.map((s) => <Badge key={s.id} label={`${s.name} ${s.start_time}-${s.end_time}`} color={colors.brand} />)}</View>
          </Card>

          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Assign Roster</AppText>
            <Input label="Roster date YYYY-MM-DD" value={rosterDate} onChangeText={setRosterDate} />
            <AppText variant="label">Employee</AppText>
            <View style={styles.wrap}>{plant.employees.map((e) => <Pressable key={e.user_id} onPress={() => setSelectedEmployee(e.user_id)} style={[styles.chip, { borderColor: selectedEmployee === e.user_id ? colors.brand : colors.border }]}><AppText>{e.name}</AppText></Pressable>)}</View>
            <AppText variant="label">Shift</AppText>
            <View style={styles.wrap}>{plant.shifts.map((s) => <Pressable key={s.id} onPress={() => { setSelectedShift(s.id); setWeekOff(false); }} style={[styles.chip, { borderColor: selectedShift === s.id && !weekOff ? colors.brand : colors.border }]}><AppText>{s.name}</AppText></Pressable>)}<Pressable onPress={() => { setWeekOff(true); setSelectedShift(null); }} style={[styles.chip, { borderColor: weekOff ? colors.brand : colors.border }]}><AppText>Week Off</AppText></Pressable></View>
            <AppText variant="caption">{selectedEmployeeName || "Select employee"} · {weekOff ? "Week Off" : selectedShiftName || "Select shift"}</AppText>
            <Button label="Save Roster" disabled={busy || !selectedEmployee || (!weekOff && !selectedShift)} onPress={() => run(() => apiPut(`/workforce-rules/plants/${plant.plant_id}/roster/${rosterDate}/${selectedEmployee}`, token!, { shift_id: selectedShift, week_off: weekOff, note: null }), "Roster updated")} />
          </Card>

          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Pending Geofence Exceptions</AppText>
            {plant.geofence_exceptions.length === 0 ? <AppText variant="caption">No pending location exceptions.</AppText> : plant.geofence_exceptions.map((x) => <View key={x.id} style={styles.listRow}><View style={{ flex: 1 }}><AppText style={{ fontFamily: fonts.semibold }}>{x.user_name || "Staff"}</AppText><AppText variant="caption">{x.date} · In {x.check_in_geofence_status || "-"} · Out {x.check_out_geofence_status || "-"}</AppText></View><Button label="Accept" size="sm" fullWidth={false} disabled={busy} onPress={() => run(() => apiPost(`/workforce-rules/plants/${plant.plant_id}/attendance/${x.date}/${x.user_id}/geofence-review`, token!, { action: "ACCEPT", note: "Owner reviewed and accepted attendance evidence" }), "Exception accepted")} /></View>)}
          </Card>

          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Attendance Corrections</AppText>
            {plant.pending_corrections.length === 0 ? <AppText variant="caption">No pending correction requests.</AppText> : plant.pending_corrections.map((c) => <View key={c.id} style={{ gap: spacing.sm }}><AppText style={{ fontFamily: fonts.semibold }}>{c.user_name || "Staff"} · {c.attendance_date}</AppText><AppText variant="caption">{c.reason}</AppText><View style={styles.twoCol}><Button label="Approve" size="sm" disabled={busy} onPress={() => run(() => apiPost(`/workforce-rules/plants/${plant.plant_id}/corrections/${c.id}/decision`, token!, { action: "APPROVE", note: "Approved by Plant Owner" }), "Correction approved")} /><Button label="Reject" size="sm" variant="secondary" disabled={busy} onPress={() => run(() => apiPost(`/workforce-rules/plants/${plant.plant_id}/corrections/${c.id}/decision`, token!, { action: "REJECT", note: "Rejected by Plant Owner" }), "Correction rejected")} /></View></View>)}
          </Card>
        </> : <>
          <Card style={{ gap: spacing.sm }}>
            <View style={styles.rowBetween}><AppText variant="heading">My Roster</AppText><Badge label={meData?.geofence_enabled ? "GEOFENCE ON" : "GEOFENCE OFF"} color={meData?.geofence_enabled ? colors.success : colors.warning} /></View>
            <AppText variant="caption">Timezone: {meData?.timezone_name || "Asia/Kolkata"}</AppText>
            {(meData?.roster || []).length === 0 ? <AppText variant="caption">No roster assigned for the next 14 days.</AppText> : meData?.roster.map((r) => <View key={r.id} style={styles.listRow}><View><AppText style={{ fontFamily: fonts.semibold }}>{r.date}</AppText><AppText variant="caption">{r.week_off ? "Week Off" : `${r.shift?.name || "Shift"} · ${r.shift?.start_time || ""}-${r.shift?.end_time || ""}`}</AppText></View></View>)}
          </Card>

          <Card style={{ gap: spacing.md }}>
            <AppText variant="heading">Request Attendance Correction</AppText>
            <Input label="Attendance date" value={correctionDate} onChangeText={setCorrectionDate} />
            <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Punch in HH:MM" value={correctionIn} onChangeText={setCorrectionIn} /></View><View style={{ flex: 1 }}><Input label="Punch out HH:MM" value={correctionOut} onChangeText={setCorrectionOut} /></View></View>
            <Input label="Reason" value={correctionReason} onChangeText={setCorrectionReason} />
            <Button label="Submit Correction" disabled={busy || correctionReason.trim().length < 5 || (!correctionIn && !correctionOut)} onPress={() => {
              const requested_check_in = correctionIn ? localIso(correctionDate, correctionIn) : null;
              const requested_check_out = correctionOut ? localIso(correctionDate, correctionOut) : null;
              if ((correctionIn && !requested_check_in) || (correctionOut && !requested_check_out)) { toast("Enter valid date and HH:MM times", "error"); return; }
              run(() => apiPost("/workforce-rules/attendance-corrections", token!, { attendance_date: correctionDate, requested_check_in, requested_check_out, reason: correctionReason.trim() }), "Correction request submitted");
            }} />
          </Card>

          <Card style={{ gap: spacing.sm }}><AppText variant="heading">Correction History</AppText>{(meData?.corrections || []).map((c) => <View key={c.id} style={styles.listRow}><View style={{ flex: 1 }}><AppText>{c.attendance_date}</AppText><AppText variant="caption">{c.reason}</AppText></View><Badge label={c.status} color={c.status === "APPROVED" ? colors.success : c.status === "REJECTED" ? colors.error : colors.warning} /></View>)}</Card>
        </>}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  iconButton: { width: 42, height: 42, borderRadius: radius.md, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  twoCol: { flexDirection: "row", gap: spacing.sm },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  listRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md, paddingVertical: spacing.sm },
});

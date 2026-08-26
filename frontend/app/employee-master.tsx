import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiGet, apiPut } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Badge } from "@/src/components/ui/Badge";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { useToast } from "@/src/components/ui/Toast";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, radius, spacing } from "@/src/theme/tokens";

type EmployeeProfile = {
  employee_code?: string;
  designation?: string;
  department?: string;
  join_date?: string;
  employment_type?: string;
  weekly_off_day?: string;
  work_location?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  address?: string | null;
  pan_masked?: string | null;
  uan_masked?: string | null;
  bank_account_masked?: string | null;
  bank_name?: string | null;
  ifsc?: string | null;
  document_references?: string[];
  notes?: string | null;
};

type Salary = {
  effective_from?: string;
  pay_basis?: string;
  basic_amount?: number;
  hra_amount?: number;
  other_allowances?: number;
  overtime_rate_per_hour?: number;
  fixed_deductions?: number;
  employee_pf?: number;
  employee_esi?: number;
  professional_tax?: number;
  tds?: number;
};

type Employee = {
  user_id: string;
  name: string;
  role: string;
  email?: string | null;
  phone?: string | null;
  profile: EmployeeProfile | null;
  current_salary: Salary | null;
  salary_totals: { allowances: number; deductions: number; gross: number; net_before_overtime: number };
};
type PlantEmployees = { plant_id: string; employees: Employee[] };
type Response = { plants: PlantEmployees[]; can_edit: boolean };

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function money(value: number) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export default function EmployeeMasterScreen() {
  const { colors } = useTheme();
  const { token, user } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<Response | null>(null);
  const [selected, setSelected] = useState<Employee | null>(null);

  const [employeeCode, setEmployeeCode] = useState("");
  const [designation, setDesignation] = useState("");
  const [department, setDepartment] = useState("");
  const [joinDate, setJoinDate] = useState(todayKey());
  const [employmentType, setEmploymentType] = useState("PERMANENT");
  const [weeklyOff, setWeeklyOff] = useState("SUNDAY");
  const [workLocation, setWorkLocation] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [documentRefs, setDocumentRefs] = useState("");

  const [effectiveFrom, setEffectiveFrom] = useState(todayKey());
  const [payBasis, setPayBasis] = useState("MONTHLY");
  const [basic, setBasic] = useState("0");
  const [hra, setHra] = useState("0");
  const [allowances, setAllowances] = useState("0");
  const [otRate, setOtRate] = useState("0");
  const [fixedDeductions, setFixedDeductions] = useState("0");
  const [pf, setPf] = useState("0");
  const [esi, setEsi] = useState("0");
  const [pt, setPt] = useState("0");
  const [tds, setTds] = useState("0");

  const allowed = user?.role === "plant_owner" || user?.role === "accountant";
  const canEdit = user?.role === "plant_owner";
  const plant = data?.plants?.[0] || null;

  const applyEmployee = (employee: Employee) => {
    setSelected(employee);
    const p = employee.profile || {};
    const s = employee.current_salary || {};
    setEmployeeCode(p.employee_code || "");
    setDesignation(p.designation || "");
    setDepartment(p.department || "");
    setJoinDate(p.join_date || todayKey());
    setEmploymentType(p.employment_type || "PERMANENT");
    setWeeklyOff(p.weekly_off_day || "SUNDAY");
    setWorkLocation(p.work_location || "");
    setEmergencyName(p.emergency_contact_name || "");
    setEmergencyPhone(p.emergency_contact_phone || "");
    setDocumentRefs((p.document_references || []).join(", "));
    setEffectiveFrom(s.effective_from || todayKey());
    setPayBasis(s.pay_basis || "MONTHLY");
    setBasic(String(s.basic_amount || 0));
    setHra(String(s.hra_amount || 0));
    setAllowances(String(s.other_allowances || 0));
    setOtRate(String(s.overtime_rate_per_hour || 0));
    setFixedDeductions(String(s.fixed_deductions || 0));
    setPf(String(s.employee_pf || 0));
    setEsi(String(s.employee_esi || 0));
    setPt(String(s.professional_tax || 0));
    setTds(String(s.tds || 0));
  };

  const load = useCallback(async () => {
    if (!token || !allowed) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await apiGet<Response>("/hr/employees", token);
      setData(res);
      if (selected) {
        const fresh = res.plants.flatMap((p) => p.employees).find((e) => e.user_id === selected.user_id);
        if (fresh) applyEmployee(fresh);
      }
    } catch (e: any) {
      toast(e?.detail || "Unable to load employee master", "error");
    } finally {
      setLoading(false);
    }
  }, [token, allowed, toast, selected?.user_id]);

  useEffect(() => { load(); }, [token, allowed]);

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      toast(message, "success");
      await load();
    } catch (e: any) {
      toast(e?.detail || "Unable to save employee record", "error");
    } finally {
      setBusy(false);
    }
  };

  if (!allowed) return <View style={[styles.center, { backgroundColor: colors.surface }]}><AppText>Employee salary master is available to Plant Owner and Accountant only.</AppText></View>;
  if (loading && !data) return <View style={[styles.center, { backgroundColor: colors.surface }]}><ActivityIndicator color={colors.brand} /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={[styles.iconButton, { borderColor: colors.border }]}><Ionicons name="arrow-back" size={20} color={colors.onSurface} /></Pressable>
          <View style={{ flex: 1 }}><AppText variant="title">Employee Master</AppText><AppText variant="caption">Employment profile, HR references and versioned salary structure</AppText></View>
        </View>

        <Card style={{ gap: spacing.md }}>
          <View style={styles.rowBetween}><AppText variant="heading">Employees</AppText><Badge label={canEdit ? "OWNER EDIT" : "READ ONLY"} color={canEdit ? colors.brand : colors.warning} /></View>
          <View style={styles.wrap}>{(plant?.employees || []).map((e) => <Pressable key={e.user_id} onPress={() => applyEmployee(e)} style={[styles.chip, { borderColor: selected?.user_id === e.user_id ? colors.brand : colors.border, backgroundColor: selected?.user_id === e.user_id ? colors.surfaceSecondary : colors.surface }]}><AppText style={{ fontFamily: fonts.semibold }}>{e.name}</AppText><AppText variant="caption">{e.role.replaceAll("_", " ")}</AppText></Pressable>)}</View>
          {(plant?.employees || []).length === 0 ? <AppText variant="caption">No plant staff found.</AppText> : null}
        </Card>

        {selected ? (
          <>
            <Card style={{ gap: spacing.md }}>
              <View style={styles.rowBetween}><View><AppText variant="heading">{selected.name}</AppText><AppText variant="caption">{selected.email || selected.phone || selected.role}</AppText></View><Badge label={selected.role.toUpperCase()} color={colors.brand} /></View>
              <Input label="Employee code" value={employeeCode} onChangeText={setEmployeeCode} editable={canEdit} placeholder="EMP-001" />
              <Input label="Designation" value={designation} onChangeText={setDesignation} editable={canEdit} placeholder="Plant Supervisor" />
              <Input label="Department" value={department} onChangeText={setDepartment} editable={canEdit} placeholder="Operations" />
              <Input label="Join date YYYY-MM-DD" value={joinDate} onChangeText={setJoinDate} editable={canEdit} />
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Employment type" value={employmentType} onChangeText={setEmploymentType} editable={canEdit} /></View><View style={{ flex: 1 }}><Input label="Weekly off" value={weeklyOff} onChangeText={setWeeklyOff} editable={canEdit} /></View></View>
              <Input label="Work location" value={workLocation} onChangeText={setWorkLocation} editable={canEdit} />
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Emergency contact" value={emergencyName} onChangeText={setEmergencyName} editable={canEdit} /></View><View style={{ flex: 1 }}><Input label="Emergency phone" value={emergencyPhone} onChangeText={setEmergencyPhone} editable={canEdit} keyboardType="phone-pad" /></View></View>
              <Input label="HR document references (comma separated)" value={documentRefs} onChangeText={setDocumentRefs} editable={canEdit} placeholder="Appointment Letter, Driving Licence" />
              {canEdit ? <Button disabled={busy || employeeCode.trim().length < 2 || designation.trim().length < 2 || department.trim().length < 2} onPress={() => run(() => apiPut(`/hr/plants/${plant!.plant_id}/employees/${selected.user_id}/profile`, token!, { employee_code: employeeCode.trim(), designation: designation.trim(), department: department.trim(), join_date: joinDate, employment_type: employmentType.trim().toUpperCase(), weekly_off_day: weeklyOff.trim().toUpperCase(), work_location: workLocation.trim() || null, emergency_contact_name: emergencyName.trim() || null, emergency_contact_phone: emergencyPhone.trim() || null, address: null, pan_masked: null, uan_masked: null, bank_account_masked: null, bank_name: null, ifsc: null, document_references: documentRefs.split(",").map((v) => v.trim()).filter(Boolean), notes: null }), "Employee profile saved")}>Save Employee Profile</Button> : null}
            </Card>

            <Card style={{ gap: spacing.md }}>
              <AppText variant="heading">Salary Structure</AppText>
              <AppText variant="caption">Reference only. Payroll paid days, overtime, approval and payment remain controlled by the payroll workflow.</AppText>
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Effective from" value={effectiveFrom} onChangeText={setEffectiveFrom} editable={canEdit} /></View><View style={{ flex: 1 }}><Input label="Pay basis" value={payBasis} onChangeText={setPayBasis} editable={canEdit} /></View></View>
              <Input label="Basic amount" value={basic} onChangeText={setBasic} editable={canEdit} keyboardType="decimal-pad" />
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="HRA" value={hra} onChangeText={setHra} editable={canEdit} keyboardType="decimal-pad" /></View><View style={{ flex: 1 }}><Input label="Other allowances" value={allowances} onChangeText={setAllowances} editable={canEdit} keyboardType="decimal-pad" /></View></View>
              <Input label="Overtime rate / hour" value={otRate} onChangeText={setOtRate} editable={canEdit} keyboardType="decimal-pad" />
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Other fixed deductions" value={fixedDeductions} onChangeText={setFixedDeductions} editable={canEdit} keyboardType="decimal-pad" /></View><View style={{ flex: 1 }}><Input label="Employee PF" value={pf} onChangeText={setPf} editable={canEdit} keyboardType="decimal-pad" /></View></View>
              <View style={styles.twoCol}><View style={{ flex: 1 }}><Input label="Employee ESI" value={esi} onChangeText={setEsi} editable={canEdit} keyboardType="decimal-pad" /></View><View style={{ flex: 1 }}><Input label="Professional tax" value={pt} onChangeText={setPt} editable={canEdit} keyboardType="decimal-pad" /></View></View>
              <Input label="TDS" value={tds} onChangeText={setTds} editable={canEdit} keyboardType="decimal-pad" />
              <View style={styles.metrics}><View><AppText variant="caption">Gross</AppText><AppText variant="heading">{money(selected.salary_totals?.gross || 0)}</AppText></View><View><AppText variant="caption">Fixed deductions</AppText><AppText variant="heading">{money(selected.salary_totals?.deductions || 0)}</AppText></View><View><AppText variant="caption">Net before OT</AppText><AppText variant="heading">{money(selected.salary_totals?.net_before_overtime || 0)}</AppText></View></View>
              {canEdit ? <Button disabled={busy} onPress={() => run(() => apiPut(`/hr/plants/${plant!.plant_id}/employees/${selected.user_id}/salary`, token!, { effective_from: effectiveFrom, pay_basis: payBasis.trim().toUpperCase(), basic_amount: Number(basic || 0), hra_amount: Number(hra || 0), other_allowances: Number(allowances || 0), overtime_rate_per_hour: Number(otRate || 0), fixed_deductions: Number(fixedDeductions || 0), employee_pf: Number(pf || 0), employee_esi: Number(esi || 0), professional_tax: Number(pt || 0), tds: Number(tds || 0), notes: null }), "Salary structure saved")}>Save Salary Structure</Button> : null}
            </Card>
          </>
        ) : <Card><AppText variant="caption">Select an employee to view employment and salary information.</AppText></Card>}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  iconButton: { width: 42, height: 42, borderRadius: radius.md, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { minWidth: 130, borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: 2 },
  twoCol: { flexDirection: "row", gap: spacing.sm },
  metrics: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md, flexWrap: "wrap" },
});

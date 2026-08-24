import React, { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { useToast } from "@/src/components/ui/Toast";
import { ErrorView } from "@/src/components/StateViews";
import { useGet } from "@/src/hooks/useApi";
import { StaffCollection } from "@/src/screens/StaffCollection";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type ListingRequest = {
  id: string;
  google_place_id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  district?: string | null;
  contact_phone?: string | null;
  business_status?: string | null;
  requested_role?: string | null;
  claim_requested?: boolean;
  status: string;
};

export default function AuthorityPlants() {
  const { colors } = useTheme();
  const { token } = useAuth();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { data, loading, error, refetch, reload } = useGet<{ requests: ListingRequest[] }>("/plant-discovery/requests");
  const [busy, setBusy] = useState<string | null>(null);
  const [owners, setOwners] = useState<Record<string, { name: string; email: string; phone: string }>>({});

  const updateOwner = (id: string, field: "name" | "email" | "phone", value: string) => {
    setOwners((current) => ({
      ...current,
      [id]: { name: "", email: "", phone: "", ...current[id], [field]: value },
    }));
  };

  const review = async (request: ListingRequest, action: "approve" | "reject") => {
    if (!token) return;
    const owner = owners[request.id] || { name: "", email: "", phone: "" };
    if (action === "approve" && (!owner.name.trim() || (!owner.email.trim() && !owner.phone.trim()))) {
      toast("Enter the owner name and email or mobile number", "error");
      return;
    }
    setBusy(`${request.id}:${action}`);
    try {
      await apiPost(
        `/plant-discovery/requests/${request.id}/${action}`,
        token,
        action === "reject"
          ? { reason: "Not approved by Authority" }
          : { name: owner.name.trim(), email: owner.email.trim() || undefined, phone: owner.phone.trim() || undefined },
      );
      toast(action === "approve" ? "Plant listing approved" : "Plant listing rejected", "success");
      refetch();
    } catch (e: any) {
      toast(e?.detail || "Review action failed", "error");
    } finally {
      setBusy(null);
    }
  };

  const requests = data?.requests || [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => { refetch(); }} tintColor={colors.brand} />}
      >
        <View style={{ gap: 3 }}>
          <AppText variant="title">Plant Directory Review</AppText>
          <AppText variant="caption">
            Google-discovered RMC businesses must be approved here before they enter the TrackMyRMC plant directory.
          </AppText>
        </View>

        <View style={{ gap: spacing.sm }}>
          <View style={styles.sectionTitle}>
            <AppText variant="heading">Pending Google listings</AppText>
            <View style={[styles.count, { backgroundColor: colors.brandSoft }]}>
              <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onBrandSoft }}>{requests.length}</AppText>
            </View>
          </View>

          {error && !data ? (
            <ErrorView message={error} onRetry={reload} />
          ) : loading && !data ? (
            <View style={{ gap: spacing.sm }}>
              <Skeleton height={120} style={{ borderRadius: radius.lg }} />
              <Skeleton height={120} style={{ borderRadius: radius.lg }} />
            </View>
          ) : requests.length === 0 ? (
            <Card style={{ alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl }}>
              <Ionicons name="checkmark-done-circle-outline" size={30} color={colors.success} />
              <AppText variant="bodyMuted">No Google plant listings are waiting for review.</AppText>
            </Card>
          ) : (
            requests.map((request) => (
              <Card key={request.id} style={{ gap: spacing.md }}>
                <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" }}>
                  <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
                    <Ionicons name="business-outline" size={19} color={colors.onBrandSoft} />
                  </View>
                  <View style={{ flex: 1, gap: 3 }}>
                    <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: colors.onSurface }}>
                      {request.name}
                    </AppText>
                    <AppText variant="caption">{request.address || [request.city, request.district].filter(Boolean).join(" · ")}</AppText>
                    <AppText variant="caption" color={colors.warning}>
                      Google Places · Pending Authority review{request.claim_requested ? " · Owner claim requested" : ""}
                    </AppText>
                  </View>
                </View>
                <View style={{ gap: spacing.sm }}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onSurface }}>
                    Assign first Plant Owner
                  </AppText>
                  <TextInput
                    value={owners[request.id]?.name || ""}
                    onChangeText={(value) => updateOwner(request.id, "name", value)}
                    placeholder="Owner full name"
                    placeholderTextColor={colors.onSurfaceTertiary}
                    autoCapitalize="words"
                    style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}
                  />
                  <TextInput
                    value={owners[request.id]?.email || ""}
                    onChangeText={(value) => updateOwner(request.id, "email", value)}
                    placeholder="Owner email"
                    placeholderTextColor={colors.onSurfaceTertiary}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}
                  />
                  <TextInput
                    value={owners[request.id]?.phone || ""}
                    onChangeText={(value) => updateOwner(request.id, "phone", value)}
                    placeholder="Owner mobile (optional when email is entered)"
                    placeholderTextColor={colors.onSurfaceTertiary}
                    keyboardType="phone-pad"
                    style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]}
                  />
                  <AppText variant="caption">
                    A secure Plant Owner account will be created and linked to this plant. The owner signs in using OTP.
                  </AppText>
                </View>
                <View style={styles.actions}>
                  <Pressable
                    testID={`reject-listing-${request.id}`}
                    disabled={busy !== null}
                    onPress={() => review(request, "reject")}
                    style={[styles.action, { borderColor: colors.error + "66", backgroundColor: colors.error + "12" }]}
                  >
                    <Ionicons name="close-circle-outline" size={16} color={colors.error} />
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.error }}>
                      {busy === `${request.id}:reject` ? "Rejecting…" : "Reject"}
                    </AppText>
                  </Pressable>
                  <Pressable
                    testID={`approve-listing-${request.id}`}
                    disabled={busy !== null}
                    onPress={() => review(request, "approve")}
                    style={[styles.action, { borderColor: colors.brand, backgroundColor: colors.brand }]}
                  >
                    <Ionicons name="checkmark-circle-outline" size={16} color={colors.onBrand} />
                    <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onBrand }}>
                      {busy === `${request.id}:approve` ? "Approving…" : "Approve listing"}
                    </AppText>
                  </Pressable>
                </View>
              </Card>
            ))
          )}
        </View>

        <View style={{ gap: spacing.sm }}>
          <AppText variant="heading">Registered TrackMyRMC plants</AppText>
          <AppText variant="caption">
            Approved Google listings enter setup mode first; ordering remains unavailable until plant operations are configured.
          </AppText>
          <StaffCollection kind="plants" embedded />
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  sectionTitle: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  count: { minWidth: 26, height: 26, paddingHorizontal: 7, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  icon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  input: { minHeight: 44, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md, fontFamily: fonts.medium, fontSize: fontSize.sm },
  actions: { flexDirection: "row", gap: spacing.sm, justifyContent: "flex-end", flexWrap: "wrap" },
  action: {
    minHeight: 38,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
  },
});

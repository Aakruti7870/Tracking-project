import React, { useState } from "react";
import { Modal, Pressable, RefreshControl, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiGet, apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { useToast } from "@/src/components/ui/Toast";
import { ErrorView } from "@/src/components/StateViews";
import { useGet } from "@/src/hooks/useApi";
import { StaffCollection } from "@/src/screens/StaffCollection";
import type { StaffItem } from "@/src/screens/StaffCollection";
import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type UnownedPlant = { id: string; name: string; city?: string | null; address?: string | null; status?: string | null };
type GooglePlant = {
  place_id: string; name: string; address?: string | null; city?: string | null;
  taluka?: string | null; district?: string | null; state?: string | null;
  lat: number; lng: number; google_maps_uri?: string | null; business_status?: string | null;
  registered: boolean; request_status?: string | null;
};
type GoogleSearchResponse = { configured: boolean; places: GooglePlant[]; next_page_token?: string | null };

type ListingRequest = {
  id: string;
  google_place_id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  taluka?: string | null;
  district?: string | null;
  state?: string | null;
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
  const { data: unownedData, loading: unownedLoading, error: unownedError, refetch: refetchUnowned, reload: reloadUnowned } = useGet<{ plants: UnownedPlant[] }>("/plant-discovery/unowned-plants");
  const [busy, setBusy] = useState<string | null>(null);
  const [owners, setOwners] = useState<Record<string, { name: string; email: string; phone: string }>>({});
  const [selectedPlant, setSelectedPlant] = useState<StaffItem | null>(null);
  const [stateName, setStateName] = useState("Maharashtra");
  const [districtName, setDistrictName] = useState("");
  const [talukaName, setTalukaName] = useState("");
  const [googleResults, setGoogleResults] = useState<GooglePlant[]>([]);
  const [selectedPlaces, setSelectedPlaces] = useState<string[]>([]);
  const [selectedRequests, setSelectedRequests] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

  const discoverGooglePlants = async () => {
    if (!token || !stateName.trim() || !districtName.trim() || !talukaName.trim()) {
      toast("Enter State, District and Taluka", "error");
      return;
    }
    setDiscovering(true);
    try {
      const result = await apiGet<GoogleSearchResponse>(
        `/maps/authority/rmc-plants?state=${encodeURIComponent(stateName.trim())}&district=${encodeURIComponent(districtName.trim())}&taluka=${encodeURIComponent(talukaName.trim())}`,
        token,
      );
      if (!result.configured) {
        toast("Google Places is not configured on the server", "error");
        setGoogleResults([]);
      } else {
        setGoogleResults(result.places || []);
        setSelectedPlaces([]);
        toast(`${result.places?.length || 0} Google plants found`, "success");
      }
    } catch (e: any) {
      toast(e?.detail || "Google plant discovery failed", "error");
    } finally {
      setDiscovering(false);
    }
  };

  const importSelectedPlaces = async () => {
    if (!token || !selectedPlaces.length) return;
    setBulkBusy(true);
    try {
      const result = await apiPost<{ imported: any[]; skipped: any[] }>("/plant-discovery/requests/bulk-import", token, { place_ids: selectedPlaces });
      toast(`${result.imported.length} plant${result.imported.length === 1 ? "" : "s"} sent to Pending Review`, "success");
      setGoogleResults((rows) => rows.map((row) => selectedPlaces.includes(row.place_id) ? { ...row, request_status: "PENDING" } : row));
      setSelectedPlaces([]);
      refetch();
    } catch (e: any) {
      toast(e?.detail || "Bulk import failed", "error");
    } finally {
      setBulkBusy(false);
    }
  };

  const approveSelectedRequests = async () => {
    if (!token || !selectedRequests.length) return;
    setBulkBusy(true);
    try {
      const result = await apiPost<{ approved: any[]; skipped: any[] }>("/plant-discovery/requests/bulk-approve", token, { request_ids: selectedRequests });
      toast(`${result.approved.length} plant${result.approved.length === 1 ? "" : "s"} approved into setup mode`, "success");
      setSelectedRequests([]);
      refetch();
      refetchUnowned();
    } catch (e: any) {
      toast(e?.detail || "Bulk approval failed", "error");
    } finally {
      setBulkBusy(false);
    }
  };

  const togglePlace = (id: string) => setSelectedPlaces((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const toggleRequest = (id: string) => setSelectedRequests((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);

  const updateOwner = (id: string, field: "name" | "email" | "phone", value: string) => {
    setOwners((current) => ({
      ...current,
      [id]: { ...(current[id] || { name: "", email: "", phone: "" }), [field]: value },
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

  const assignExistingOwner = async (plant: UnownedPlant) => {
    if (!token) return;
    const owner = owners[plant.id] || { name: "", email: "", phone: "" };
    if (!owner.name.trim() || (!owner.email.trim() && !owner.phone.trim())) {
      toast("Enter the owner name and email or mobile number", "error");
      return;
    }
    setBusy(`${plant.id}:assign`);
    try {
      await apiPost(`/plant-discovery/plants/${plant.id}/assign-owner`, token, {
        name: owner.name.trim(),
        email: owner.email.trim() || undefined,
        phone: owner.phone.trim() || undefined,
      });
      toast("Plant Owner account assigned", "success");
      refetchUnowned();
      setSelectedPlant(null);
    } catch (e: any) {
      toast(e?.detail || "Owner assignment failed", "error");
    } finally {
      setBusy(null);
    }
  };

  const requests = data?.requests || [];
  const unownedPlants = unownedData?.plants || [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => { refetch(); refetchUnowned(); }} tintColor={colors.brand} />}
      >
        <View style={{ gap: 3 }}>
          <AppText variant="title">Plant Directory Review</AppText>
          <AppText variant="caption">
            Google-discovered RMC businesses must be approved here before they enter the TrackMyRMC plant directory.
          </AppText>
        </View>

        <Card style={{ gap: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
            <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
              <Ionicons name="logo-google" size={20} color={colors.onBrandSoft} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText variant="heading">Discover RMC Plants on Google</AppText>
              <AppText variant="caption">Search by State, District and Taluka, then select multiple verified business locations.</AppText>
            </View>
          </View>
          <View style={styles.locationRow}>
            <TextInput testID="google-state" value={stateName} onChangeText={setStateName} placeholder="State" placeholderTextColor={colors.onSurfaceTertiary} style={[styles.locationInput, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
            <TextInput testID="google-district" value={districtName} onChangeText={setDistrictName} placeholder="District" placeholderTextColor={colors.onSurfaceTertiary} style={[styles.locationInput, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
            <TextInput testID="google-taluka" value={talukaName} onChangeText={setTalukaName} placeholder="Taluka" placeholderTextColor={colors.onSurfaceTertiary} style={[styles.locationInput, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
          </View>
          <Pressable testID="authority-google-search" onPress={discoverGooglePlants} disabled={discovering || bulkBusy} style={[styles.action, { alignSelf: "stretch", borderColor: colors.brand, backgroundColor: colors.brand }]}>
            <Ionicons name="search" size={17} color={colors.onBrand} />
            <AppText style={{ fontFamily: fonts.semibold, color: colors.onBrand }}>{discovering ? "Searching Google…" : "Find RMC Plants"}</AppText>
          </Pressable>
          {googleResults.length ? (
            <View style={{ gap: spacing.sm }}>
              <View style={styles.sectionTitle}>
                <AppText variant="label">{googleResults.length} Google result{googleResults.length === 1 ? "" : "s"}</AppText>
                <Pressable onPress={() => setSelectedPlaces(googleResults.filter((row) => !row.registered && row.request_status !== "PENDING" && row.request_status !== "APPROVED").map((row) => row.place_id))}>
                  <AppText style={{ color: colors.brand, fontFamily: fonts.semibold, fontSize: 12 }}>Select available</AppText>
                </Pressable>
              </View>
              {googleResults.map((place) => {
                const unavailable = place.registered || place.request_status === "PENDING" || place.request_status === "APPROVED";
                const selected = selectedPlaces.includes(place.place_id);
                return (
                  <Pressable key={place.place_id} disabled={unavailable} onPress={() => togglePlace(place.place_id)} style={[styles.googleResult, { borderColor: selected ? colors.brand : colors.border, backgroundColor: selected ? colors.brandSoft : colors.surfaceSecondary, opacity: unavailable ? 0.65 : 1 }]}>
                    <Ionicons name={unavailable ? "checkmark-circle" : selected ? "checkbox" : "square-outline"} size={21} color={unavailable ? colors.success : selected ? colors.brand : colors.onSurfaceTertiary} />
                    <View style={{ flex: 1, gap: 2 }}>
                      <AppText style={{ fontFamily: fonts.semibold, color: colors.onSurface }} numberOfLines={1}>{place.name}</AppText>
                      <AppText variant="caption" numberOfLines={2}>{place.address || [place.taluka || place.city, place.district, place.state].filter(Boolean).join(", ")}</AppText>
                      <AppText variant="caption" color={unavailable ? colors.success : colors.warning}>{place.registered ? "Already registered" : place.request_status === "PENDING" ? "Already pending review" : place.request_status === "APPROVED" ? "Already approved" : "Available to import"}</AppText>
                    </View>
                  </Pressable>
                );
              })}
              <Pressable testID="bulk-import-google-plants" disabled={!selectedPlaces.length || bulkBusy} onPress={importSelectedPlaces} style={[styles.action, { alignSelf: "stretch", borderColor: colors.brand, backgroundColor: selectedPlaces.length ? colors.brand : colors.surfaceTertiary }]}>
                <Ionicons name="cloud-download-outline" size={17} color={selectedPlaces.length ? colors.onBrand : colors.onSurfaceTertiary} />
                <AppText style={{ fontFamily: fonts.semibold, color: selectedPlaces.length ? colors.onBrand : colors.onSurfaceTertiary }}>{bulkBusy ? "Importing…" : `Import ${selectedPlaces.length} to Pending Review`}</AppText>
              </Pressable>
            </View>
          ) : null}
        </Card>

        <View style={{ gap: spacing.sm }}>
          <View style={styles.sectionTitle}>
            <AppText variant="heading">Pending Google listings</AppText>
            <View style={[styles.count, { backgroundColor: colors.brandSoft }]}>
              <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onBrandSoft }}>{requests.length}</AppText>
            </View>
          </View>
          {requests.length ? (
            <View style={styles.bulkRow}>
              <Pressable onPress={() => setSelectedRequests(selectedRequests.length === requests.length ? [] : requests.map((row) => row.id))}>
                <AppText style={{ color: colors.brand, fontFamily: fonts.semibold, fontSize: 12 }}>{selectedRequests.length === requests.length ? "Clear selection" : "Select all pending"}</AppText>
              </Pressable>
              <Pressable testID="bulk-approve-google-listings" disabled={!selectedRequests.length || bulkBusy} onPress={approveSelectedRequests} style={[styles.action, { borderColor: colors.brand, backgroundColor: selectedRequests.length ? colors.brand : colors.surfaceTertiary }]}>
                <Ionicons name="checkmark-done-outline" size={16} color={selectedRequests.length ? colors.onBrand : colors.onSurfaceTertiary} />
                <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: selectedRequests.length ? colors.onBrand : colors.onSurfaceTertiary }}>{bulkBusy ? "Approving…" : `Approve selected (${selectedRequests.length})`}</AppText>
              </Pressable>
            </View>
          ) : null}

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
                  <Pressable testID={`select-request-${request.id}`} onPress={() => toggleRequest(request.id)} hitSlop={8}>
                    <Ionicons name={selectedRequests.includes(request.id) ? "checkbox" : "square-outline"} size={22} color={selectedRequests.includes(request.id) ? colors.brand : colors.onSurfaceTertiary} />
                  </Pressable>
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
          <View style={styles.sectionTitle}>
            <AppText variant="heading">Assign owner to existing plant</AppText>
            <View style={[styles.count, { backgroundColor: colors.brandSoft }]}>
              <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onBrandSoft }}>{unownedPlants.length}</AppText>
            </View>
          </View>
          <AppText variant="caption">Only registered plants without an owner appear here.</AppText>
          {unownedError && !unownedData ? (
            <ErrorView message={unownedError} onRetry={reloadUnowned} />
          ) : unownedLoading && !unownedData ? (
            <Skeleton height={180} style={{ borderRadius: radius.lg }} />
          ) : unownedPlants.length === 0 ? (
            <Card style={{ alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl }}>
              <Ionicons name="checkmark-done-circle-outline" size={30} color={colors.success} />
              <AppText variant="bodyMuted">Every registered plant has an assigned owner.</AppText>
            </Card>
          ) : unownedPlants.map((plant) => (
            <Card key={plant.id} style={{ gap: spacing.md }}>
              <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
                <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
                  <Ionicons name="business-outline" size={19} color={colors.onBrandSoft} />
                </View>
                <View style={{ flex: 1 }}>
                  <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: colors.onSurface }}>{plant.name}</AppText>
                  <AppText variant="caption">{plant.address || plant.city || "Registered plant"}</AppText>
                </View>
              </View>
              <TextInput value={owners[plant.id]?.name || ""} onChangeText={(value) => updateOwner(plant.id, "name", value)} placeholder="Owner full name" placeholderTextColor={colors.onSurfaceTertiary} autoCapitalize="words" style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
              <TextInput value={owners[plant.id]?.email || ""} onChangeText={(value) => updateOwner(plant.id, "email", value)} placeholder="Owner email" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
              <TextInput value={owners[plant.id]?.phone || ""} onChangeText={(value) => updateOwner(plant.id, "phone", value)} placeholder="Owner mobile (optional)" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="phone-pad" style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
              <Pressable testID={`assign-existing-owner-${plant.id}`} disabled={busy !== null} onPress={() => assignExistingOwner(plant)} style={[styles.action, { alignSelf: "stretch", borderColor: colors.brand, backgroundColor: colors.brand }]}>
                <Ionicons name="person-add-outline" size={17} color={colors.onBrand} />
                <AppText style={{ fontFamily: fonts.semibold, fontSize: 13, color: colors.onBrand }}>{busy === `${plant.id}:assign` ? "Assigning…" : "Create & Assign Plant Owner"}</AppText>
              </Pressable>
            </Card>
          ))}
        </View>

        <View style={{ gap: spacing.sm }}>
          <AppText variant="heading">Registered TrackMyRMC plants</AppText>
          <AppText variant="caption">
            Approved Google listings enter setup mode first; ordering remains unavailable until plant operations are configured.
          </AppText>
          <StaffCollection kind="plants" embedded onItemPress={setSelectedPlant} />
        </View>
      </ScrollView>

      <Modal visible={!!selectedPlant} transparent animationType="fade" onRequestClose={() => setSelectedPlant(null)}>
        <Pressable style={styles.backdrop} onPress={() => setSelectedPlant(null)}>
          <Pressable style={[styles.sheet, { backgroundColor: colors.surface, borderColor: colors.border }]} onPress={() => {}}>
            <View style={{ flexDirection: "row", alignItems: "flex-start", gap: spacing.sm }}>
              <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
                <Ionicons name="business-outline" size={19} color={colors.onBrandSoft} />
              </View>
              <View style={{ flex: 1 }}>
                <AppText variant="heading">{selectedPlant?.primary}</AppText>
                <AppText variant="caption">{selectedPlant?.secondary || "Registered plant"}</AppText>
              </View>
              <Pressable testID="close-owner-sheet" onPress={() => setSelectedPlant(null)} hitSlop={10}>
                <Ionicons name="close" size={22} color={colors.onSurfaceSecondary} />
              </Pressable>
            </View>

            {selectedPlant?.owner_assigned ? (
              <View style={[styles.ownerStatus, { backgroundColor: colors.success + "12", borderColor: colors.success + "55" }]}>
                <Ionicons name="checkmark-circle-outline" size={20} color={colors.success} />
                <View style={{ flex: 1 }}>
                  <AppText style={{ fontFamily: fonts.semibold, color: colors.success }}>Plant Owner already assigned</AppText>
                  <AppText variant="caption">Existing ownership cannot be replaced from this screen.</AppText>
                </View>
              </View>
            ) : (
              <>
                <AppText style={{ fontFamily: fonts.semibold, color: colors.onSurface }}>Create &amp; assign Plant Owner</AppText>
                <TextInput value={selectedPlant ? owners[selectedPlant.id]?.name || "" : ""} onChangeText={(value) => selectedPlant && updateOwner(selectedPlant.id, "name", value)} placeholder="Owner full name" placeholderTextColor={colors.onSurfaceTertiary} autoCapitalize="words" style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
                <TextInput value={selectedPlant ? owners[selectedPlant.id]?.email || "" : ""} onChangeText={(value) => selectedPlant && updateOwner(selectedPlant.id, "email", value)} placeholder="Owner email" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
                <TextInput value={selectedPlant ? owners[selectedPlant.id]?.phone || "" : ""} onChangeText={(value) => selectedPlant && updateOwner(selectedPlant.id, "phone", value)} placeholder="Owner mobile (optional when email is entered)" placeholderTextColor={colors.onSurfaceTertiary} keyboardType="phone-pad" style={[styles.input, { color: colors.onSurface, borderColor: colors.border, backgroundColor: colors.surfaceSecondary }]} />
                <AppText variant="caption">The owner will sign in using OTP after assignment.</AppText>
                <Pressable
                  testID="assign-owner-from-plant"
                  disabled={busy !== null}
                  onPress={() => selectedPlant && assignExistingOwner({ id: selectedPlant.id, name: selectedPlant.primary })}
                  style={[styles.action, { alignSelf: "stretch", borderColor: colors.brand, backgroundColor: colors.brand }]}
                >
                  <Ionicons name="person-add-outline" size={17} color={colors.onBrand} />
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 13, color: colors.onBrand }}>{busy === `${selectedPlant?.id}:assign` ? "Assigning…" : "Create & Assign Plant Owner"}</AppText>
                </Pressable>
              </>
            )}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  sectionTitle: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  locationRow: { flexDirection: "row", gap: spacing.sm },
  locationInput: { flex: 1, minHeight: 44, minWidth: 0, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.sm, fontFamily: fonts.medium, fontSize: 12 },
  googleResult: { minHeight: 70, flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, borderWidth: 1, borderRadius: radius.md, padding: spacing.sm },
  bulkRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm, flexWrap: "wrap" },
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
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", padding: spacing.lg },
  sheet: { borderRadius: radius.lg, borderWidth: 1, padding: spacing.lg, gap: spacing.md },
  ownerStatus: { borderWidth: 1, borderRadius: radius.md, padding: spacing.md, flexDirection: "row", alignItems: "center", gap: spacing.sm },
});

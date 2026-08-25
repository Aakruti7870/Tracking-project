import React, { useEffect, useMemo, useState } from "react";
import { FlatList, Linking, Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { apiGet, apiPost } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { PlantMap } from "@/src/components/PlantMap";
import { PlantCard, PlantData } from "@/src/components/PlantCard";
import { EmptyView, ErrorView } from "@/src/components/StateViews";
import { distanceKm, LatLng, validLatLng } from "@/src/maps/geo";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type GooglePlant = {
  place_id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  district?: string | null;
  lat: number;
  lng: number;
  contact_phone?: string | null;
  google_maps_uri?: string | null;
  business_status?: string | null;
  registered: boolean;
  plant_id?: string | null;
  request_status?: string | null;
};

type GoogleDiscoveryResponse = { configured: boolean; places: GooglePlant[] };

export default function CustomerPlants() {
  const { colors } = useTheme();
  const { token } = useAuth();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [userLocation, setUserLocation] = useState<LatLng | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [googlePlants, setGooglePlants] = useState<GooglePlant[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [requestingPlace, setRequestingPlace] = useState<string | null>(null);
  const { data, loading, error, refetch, reload } = useGet<{ plants: PlantData[] }>("/customer/plants");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const permission = await Location.getForegroundPermissionsAsync();
        if (permission.status !== "granted") return;
        const last = await Location.getLastKnownPositionAsync();
        if (mounted && last) {
          setUserLocation({ lat: last.coords.latitude, lng: last.coords.longitude });
        }
      } catch {
        // Location is optional for registered-plant discovery.
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const useMyLocation = async () => {
    setLocating(true);
    setLocationMessage(null);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== "granted") {
        setLocationMessage("Location permission is off. All registered plants are still shown.");
        return;
      }
      const current = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setUserLocation({ lat: current.coords.latitude, lng: current.coords.longitude });
    } catch {
      setLocationMessage("Could not read your location. All registered plants are still shown.");
    } finally {
      setLocating(false);
    }
  };

  const discoverOnGoogle = async () => {
    if (!token) return;
    if (!userLocation) {
      toast("Use your location first", "error");
      return;
    }
    setDiscovering(true);
    setDiscoveryError(null);
    try {
      const query = q.trim() || "ready mix concrete RMC plant";
      const result = await apiGet<GoogleDiscoveryResponse>(
        `/maps/rmc-plants?lat=${userLocation.lat}&lng=${userLocation.lng}&radius_km=50&q=${encodeURIComponent(query)}`,
        token,
      );
      if (!result.configured) {
        setGooglePlants([]);
        setDiscoveryError("Google Places discovery is not configured on the TrackMyRMC server yet.");
        return;
      }
      setGooglePlants(result.places || []);
      if (!result.places?.length) {
        setDiscoveryError("Google did not return an RMC plant for this search area. Try a plant/city name.");
      }
    } catch (e: any) {
      setDiscoveryError(e?.detail || "Google RMC discovery failed");
    } finally {
      setDiscovering(false);
    }
  };

  const requestListing = async (place: GooglePlant) => {
    if (!token) return;
    setRequestingPlace(place.place_id);
    try {
      const result = await apiPost<{ status: string; request_id?: string; plant_id?: string }>(
        `/maps/rmc-plants/${encodeURIComponent(place.place_id)}/request-listing`,
        token,
      );
      setGooglePlants((current) =>
        current.map((p) =>
          p.place_id === place.place_id
            ? {
                ...p,
                registered: result.status === "REGISTERED" ? true : p.registered,
                plant_id: result.plant_id || p.plant_id,
                request_status: result.status === "REGISTERED" ? p.request_status : result.status,
              }
            : p,
        ),
      );
      toast(result.status === "REGISTERED" ? "Plant is already registered" : "Sent to Authority for review", "success");
    } catch (e: any) {
      toast(e?.detail || "Could not submit this plant", "error");
    } finally {
      setRequestingPlace(null);
    }
  };

  const ranked = useMemo(() => {
    const list = (data?.plants || []).map((plant) => {
      if (!userLocation || !validLatLng(plant)) return { ...plant, distance_km: null };
      return {
        ...plant,
        distance_km: distanceKm(userLocation, { lat: plant.lat!, lng: plant.lng! }),
      };
    });

    if (userLocation) {
      list.sort((a, b) => {
        const ap = a.promoted ? 0 : 1;
        const bp = b.promoted ? 0 : 1;
        if (ap !== bp) return ap - bp;
        const ad = a.distance_km ?? Number.POSITIVE_INFINITY;
        const bd = b.distance_km ?? Number.POSITIVE_INFINITY;
        if (ad !== bd) return ad - bd;
        const ae = a.order_enabled ? 0 : 1;
        const be = b.order_enabled ? 0 : 1;
        if (ae !== be) return ae - be;
        return (a.name || "").localeCompare(b.name || "");
      });
    } else list.sort((a, b) => (a.promoted === b.promoted ? (a.name || "").localeCompare(b.name || "") : a.promoted ? -1 : 1));
    return list;
  }, [data, userLocation]);

  const filtered = useMemo(() => {
    if (!q.trim()) return ranked;
    const t = q.toLowerCase();
    return ranked.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(t) ||
        (p.city || "").toLowerCase().includes(t) ||
        (p.district || "").toLowerCase().includes(t) ||
        (p.address || "").toLowerCase().includes(t),
    );
  }, [ranked, q]);

  const googleMapPlants = useMemo<PlantData[]>(
    () =>
      googlePlants
        .filter((p) => !p.registered)
        .map((p) => ({
          id: `google:${p.place_id}`,
          name: p.name,
          city: p.city || "Google Places",
          district: p.district || undefined,
          address: p.address || "",
          lat: p.lat,
          lng: p.lng,
          grades: [],
          contact_phone: p.contact_phone || "",
          service_area_km: 0,
          status: "google_discovered",
          verified: false,
          order_enabled: false,
          distance_km: userLocation ? distanceKm(userLocation, { lat: p.lat, lng: p.lng }) : null,
        })),
    [googlePlants, userLocation],
  );

  const mapPlants = useMemo(() => [...filtered, ...googleMapPlants], [filtered, googleMapPlants]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <View style={styles.titleRow}>
        <AppText variant="title">Nearby Plants</AppText>
        <AppText variant="caption">
          Registered TrackMyRMC plants stay visible. You can also search Google for more real RMC businesses nearby.
        </AppText>
      </View>

      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : (
        <FlatList
          testID="plants-list"
          data={filtered}
          keyExtractor={(p) => p.id}
          showsVerticalScrollIndicator={false}
          onRefresh={refetch}
          refreshing={false}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.md, flexGrow: 1 }}
          ListHeaderComponent={
            <View style={{ gap: spacing.md, marginBottom: spacing.xs }}>
              <PlantMap plants={mapPlants} userLocation={userLocation} />

              <View style={[styles.locationBar, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
                <View style={[styles.locationIcon, { backgroundColor: colors.brandSoft }]}>
                  <Ionicons name="locate-outline" size={18} color={colors.onBrandSoft} />
                </View>
                <View style={{ flex: 1, gap: 1 }}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }}>
                    {userLocation ? "Nearest plants first" : "Sort by your location"}
                  </AppText>
                  <AppText variant="caption">
                    {userLocation
                      ? "Registered plants sort by proximity; Google discovery can find additional RMC businesses."
                      : "Location is optional for registered plants and required only for nearby Google discovery."}
                  </AppText>
                </View>
                <Pressable
                  testID="plants-use-location"
                  onPress={useMyLocation}
                  disabled={locating}
                  style={[styles.locationButton, { borderColor: colors.border }]}
                >
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.brand }}>
                    {locating ? "Locating…" : userLocation ? "Refresh" : "Use location"}
                  </AppText>
                </Pressable>
              </View>

              {locationMessage ? (
                <AppText variant="caption" color={colors.warning}>{locationMessage}</AppText>
              ) : null}

              <Input
                testID="plants-search"
                value={q}
                onChangeText={setQ}
                placeholder="Search plant/city, or type a Google RMC search"
              />

              <View style={[styles.discoveryBar, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
                <View style={{ flex: 1, gap: 2 }}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }}>
                    Google RMC Discovery
                  </AppText>
                  <AppText variant="caption">
                    Find real RMC businesses within 50 km. Google results are not orderable until Authority approval and plant setup.
                  </AppText>
                </View>
                <Pressable
                  testID="discover-google-rmc"
                  onPress={discoverOnGoogle}
                  disabled={discovering}
                  style={[styles.discoveryButton, { backgroundColor: colors.brand }]}
                >
                  <Ionicons name="search" size={16} color={colors.onBrand} />
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onBrand }}>
                    {discovering ? "Searching…" : "Find more"}
                  </AppText>
                </Pressable>
              </View>

              {discoveryError ? (
                <AppText variant="caption" color={colors.warning}>{discoveryError}</AppText>
              ) : null}
            </View>
          }
          renderItem={({ item }) =>
            loading && !data ? null : (
              <PlantCard plant={item} onOrder={() => router.push(`/new-order?plantId=${item.id}` as any)} />
            )
          }
          ListFooterComponent={
            googlePlants.length ? (
              <View style={{ gap: spacing.md, marginTop: spacing.lg }}>
                <View style={{ gap: 2 }}>
                  <AppText variant="heading">Google-discovered RMC plants</AppText>
                  <AppText variant="caption">
                    {googlePlants.length} result{googlePlants.length === 1 ? "" : "s"}. Submit a real business once; Google Place ID prevents duplicate imports.
                  </AppText>
                </View>
                {googlePlants.map((place) => (
                  <GooglePlantCard
                    key={place.place_id}
                    place={place}
                    requesting={requestingPlace === place.place_id}
                    onRequest={() => requestListing(place)}
                  />
                ))}
              </View>
            ) : null
          }
          ListEmptyComponent={
            googlePlants.length ? null : loading && !data ? (
              <View style={{ gap: spacing.md }}>
                {[0, 1].map((i) => (
                  <Skeleton key={i} height={140} style={{ borderRadius: radius.lg }} />
                ))}
              </View>
            ) : (
              <EmptyView
                icon="business-outline"
                title="No registered plants found"
                subtitle={q.trim() ? "Try another search or use Google RMC Discovery" : "Use Google RMC Discovery to find businesses nearby"}
              />
            )
          }
        />
      )}
    </View>
  );
}

function GooglePlantCard({
  place,
  requesting,
  onRequest,
}: {
  place: GooglePlant;
  requesting: boolean;
  onRequest: () => void;
}) {
  const { colors } = useTheme();
  const pending = place.request_status === "PENDING";
  const approved = place.request_status === "APPROVED";
  const buttonLabel = place.registered
    ? "Already listed"
    : pending
      ? "Sent for review"
      : approved
        ? "Approved"
        : requesting
          ? "Submitting…"
          : "Add to TrackMyRMC";

  const openDirections = () => {
    const url = place.google_maps_uri || `https://www.google.com/maps/dir/?api=1&destination=${place.lat},${place.lng}`;
    Linking.openURL(url);
  };

  return (
    <Card style={{ gap: spacing.sm }}>
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: spacing.sm }}>
        <View style={[styles.googleIcon, { backgroundColor: colors.surfaceTertiary }]}>
          <Ionicons name="location-outline" size={18} color={colors.brand} />
        </View>
        <View style={{ flex: 1, gap: 3 }}>
          <AppText style={{ fontFamily: fonts.bold, fontSize: fontSize.base, color: colors.onSurface }} numberOfLines={2}>
            {place.name}
          </AppText>
          <AppText variant="caption" numberOfLines={2}>{place.address || [place.city, place.district].filter(Boolean).join(" · ")}</AppText>
          <AppText variant="caption" color={place.registered ? colors.success : colors.warning}>
            {place.registered ? "Registered TrackMyRMC plant" : "Google-discovered · not yet verified for orders"}
          </AppText>
        </View>
      </View>
      <View style={styles.googleActions}>
        <Pressable onPress={openDirections} style={[styles.googleOutlineButton, { borderColor: colors.border }]}>
          <Ionicons name="navigate-outline" size={15} color={colors.onSurfaceSecondary} />
          <AppText style={{ fontFamily: fonts.semibold, fontSize: 12, color: colors.onSurfaceSecondary }}>Directions</AppText>
        </Pressable>
        <Pressable
          testID={`request-google-plant-${place.place_id}`}
          disabled={place.registered || pending || approved || requesting}
          onPress={onRequest}
          style={[
            styles.googleRequestButton,
            {
              backgroundColor: place.registered || pending || approved ? colors.surfaceTertiary : colors.brand,
              opacity: requesting ? 0.7 : 1,
            },
          ]}
        >
          <Ionicons
            name={place.registered ? "checkmark-circle-outline" : pending ? "time-outline" : "add-circle-outline"}
            size={15}
            color={place.registered || pending || approved ? colors.onSurfaceTertiary : colors.onBrand}
          />
          <AppText
            style={{
              fontFamily: fonts.semibold,
              fontSize: 12,
              color: place.registered || pending || approved ? colors.onSurfaceTertiary : colors.onBrand,
            }}
          >
            {buttonLabel}
          </AppText>
        </Pressable>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  titleRow: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, gap: 2 },
  locationBar: {
    minHeight: 64,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  locationIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  locationButton: {
    minHeight: 38,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  discoveryBar: {
    minHeight: 72,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  discoveryButton: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    flexDirection: "row",
    gap: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  googleIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  googleActions: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  googleOutlineButton: {
    minHeight: 38,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  googleRequestButton: {
    minHeight: 38,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    marginLeft: "auto",
  },
});

import React, { useEffect, useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Input } from "@/src/components/ui/Input";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { PlantMap } from "@/src/components/PlantMap";
import { PlantCard, PlantData } from "@/src/components/PlantCard";
import { EmptyView, ErrorView } from "@/src/components/StateViews";
import { distanceKm, LatLng, validLatLng } from "@/src/maps/geo";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

export default function CustomerPlants() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [userLocation, setUserLocation] = useState<LatLng | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
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
        // Location is optional for discovery. Keep the full plant list available.
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
        const ad = a.distance_km ?? Number.POSITIVE_INFINITY;
        const bd = b.distance_km ?? Number.POSITIVE_INFINITY;
        if (ad !== bd) return ad - bd;
        const ae = a.order_enabled ? 0 : 1;
        const be = b.order_enabled ? 0 : 1;
        if (ae !== be) return ae - be;
        return (a.name || "").localeCompare(b.name || "");
      });
    }
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

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <View style={styles.titleRow}>
        <AppText variant="title">Nearby Plants</AppText>
        <AppText variant="caption">
          All registered RMC plants are shown. Use your location to sort nearest first; distance never hides a plant.
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
              <PlantMap plants={filtered} userLocation={userLocation} />

              <View style={[styles.locationBar, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]}>
                <View style={[styles.locationIcon, { backgroundColor: colors.brandSoft }]}>
                  <Ionicons name="locate-outline" size={18} color={colors.onBrandSoft} />
                </View>
                <View style={{ flex: 1, gap: 1 }}>
                  <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.sm, color: colors.onSurface }}>
                    {userLocation ? "Nearest plants first" : "Sort by your location"}
                  </AppText>
                  <AppText variant="caption">
                    {userLocation ? "Distances are straight-line proximity; Directions uses Google Maps routing." : "Optional — plant visibility does not depend on distance."}
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
                placeholder="Search by plant, city, district or address"
              />
            </View>
          }
          renderItem={({ item }) =>
            loading && !data ? null : (
              <PlantCard plant={item} onOrder={() => router.push(`/new-order?plantId=${item.id}` as any)} />
            )
          }
          ListEmptyComponent={
            loading && !data ? (
              <View style={{ gap: spacing.md }}>
                {[0, 1].map((i) => (
                  <Skeleton key={i} height={140} style={{ borderRadius: radius.lg }} />
                ))}
              </View>
            ) : (
              <EmptyView
                icon="business-outline"
                title="No plants found"
                subtitle={q.trim() ? "Try a different search" : "No registered RMC plants are available yet"}
              />
            )
          }
        />
      )}
    </View>
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
});

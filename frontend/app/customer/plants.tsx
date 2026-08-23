import React, { useMemo, useState } from "react";
import { FlatList, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Input } from "@/src/components/ui/Input";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { MapPlaceholder } from "@/src/components/ui/MapPlaceholder";
import { PlantCard, PlantData } from "@/src/components/PlantCard";
import { EmptyView, ErrorView } from "@/src/components/StateViews";
import { radius, spacing } from "@/src/theme/tokens";

export default function CustomerPlants() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const { data, loading, error, refetch, reload } = useGet<{ plants: PlantData[] }>("/customer/plants");

  const filtered = useMemo(() => {
    const list = data?.plants || [];
    if (!q.trim()) return list;
    const t = q.toLowerCase();
    return list.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(t) ||
        (p.city || "").toLowerCase().includes(t) ||
        (p.district || "").toLowerCase().includes(t) ||
        (p.address || "").toLowerCase().includes(t),
    );
  }, [data, q]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      <View style={styles.titleRow}>
        <AppText variant="title">Nearby Plants</AppText>
        <AppText variant="caption">
          All registered RMC plants are shown. Verification and operating status are displayed separately.
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
              <MapPlaceholder
                pins={filtered.length}
                label="Map and distance sorting will activate with Google Maps"
                style={{ minHeight: 170 }}
              />
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
});

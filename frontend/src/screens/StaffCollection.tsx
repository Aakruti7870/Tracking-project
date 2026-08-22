import React from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/src/theme/ThemeProvider";
import { useGet } from "@/src/hooks/useApi";
import { AppText } from "@/src/components/ui/AppText";
import { Card } from "@/src/components/ui/Card";
import { Badge } from "@/src/components/ui/Badge";
import { Skeleton } from "@/src/components/ui/Skeleton";
import { ErrorView } from "@/src/components/StateViews";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

export type StaffItem = {
  id: string;
  icon: keyof typeof Ionicons.glyphMap;
  primary: string;
  secondary?: string | null;
  meta?: string | null;
  badge?: string | null;
  badge_status?: string | null;
};

type CollectionData = { title: string; empty: string; items: StaffItem[] };

export function ItemRow({ item }: { item: StaffItem }) {
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      <View style={[styles.icon, { backgroundColor: colors.brandSoft }]}>
        <Ionicons name={item.icon || "ellipse-outline"} size={18} color={colors.onBrandSoft} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <AppText style={{ fontFamily: fonts.semibold, fontSize: fontSize.base, color: colors.onSurface }} numberOfLines={1}>
          {item.primary}
        </AppText>
        {item.secondary ? <AppText variant="caption" numberOfLines={1}>{item.secondary}</AppText> : null}
        {item.meta ? <AppText style={{ fontFamily: fonts.regular, fontSize: 11, color: colors.onSurfaceTertiary }} numberOfLines={1}>{item.meta}</AppText> : null}
      </View>
      {item.badge ? <Badge label={item.badge} status={item.badge_status || item.badge} /> : null}
    </View>
  );
}

/**
 * Generic role-scoped list. Used as a full-screen tab (default) or embedded
 * inside a dashboard (embedded + limit). Data comes from /api/staff/collection/{kind}.
 */
export function StaffCollection({
  kind,
  embedded = false,
  limit,
}: {
  kind: string;
  embedded?: boolean;
  limit?: number;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { data, loading, error, refetch, reload } = useGet<CollectionData>(`/staff/collection/${kind}`);

  const items = data ? (limit ? data.items.slice(0, limit) : data.items) : [];

  const body = (
    <>
      {loading && !data ? (
        <View style={{ gap: spacing.md }}>
          <Skeleton height={70} style={{ borderRadius: radius.lg }} />
          <Skeleton height={70} style={{ borderRadius: radius.lg }} />
          <Skeleton height={70} style={{ borderRadius: radius.lg }} />
        </View>
      ) : data && items.length === 0 ? (
        <Card style={{ alignItems: "center", paddingVertical: spacing.xl, gap: spacing.sm }}>
          <Ionicons name="file-tray-outline" size={30} color={colors.onSurfaceTertiary} />
          <AppText variant="bodyMuted">{data.empty}</AppText>
        </Card>
      ) : (
        <Card padded={false}>
          {items.map((it, i) => (
            <View key={it.id} style={i < items.length - 1 && { borderBottomColor: colors.divider, borderBottomWidth: StyleSheet.hairlineWidth }}>
              <ItemRow item={it} />
            </View>
          ))}
        </Card>
      )}
    </>
  );

  if (embedded) return body;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ height: insets.top }} />
      {error && !data ? (
        <ErrorView message={error} onRetry={reload} />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120, gap: spacing.lg }}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={false} onRefresh={refetch} tintColor={colors.brand} />}
        >
          <AppText variant="title">{data?.title || "List"}</AppText>
          {body}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md },
  icon: { width: 38, height: 38, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});

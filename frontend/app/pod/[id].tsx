import React, { useRef, useState } from "react";
import { Linking, PanResponder, Pressable, StyleSheet, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { apiPost } from "@/src/api/client";
import { uploadImage } from "@/src/api/upload";
import { useAuth } from "@/src/auth/AuthContext";
import { useTheme } from "@/src/theme/ThemeProvider";
import { useToast } from "@/src/components/ui/Toast";
import { AppText } from "@/src/components/ui/AppText";
import { Button } from "@/src/components/ui/Button";
import { Card } from "@/src/components/ui/Card";
import { Input } from "@/src/components/ui/Input";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

export default function PodScreen() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [receiver, setReceiver] = useState("");
  const [qty, setQty] = useState("");
  const [remarks, setRemarks] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [strokes, setStrokes] = useState<string[]>([]);
  const [current, setCurrent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const pan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        const { locationX, locationY } = e.nativeEvent;
        setCurrent(`M${locationX.toFixed(0)},${locationY.toFixed(0)}`);
      },
      onPanResponderMove: (e) => {
        const { locationX, locationY } = e.nativeEvent;
        setCurrent((c) => `${c} L${locationX.toFixed(0)},${locationY.toFixed(0)}`);
      },
      onPanResponderRelease: () => {
        setCurrent((c) => {
          if (c) setStrokes((s) => [...s, c]);
          return "";
        });
      },
    }),
  ).current;

  const pickImage = async (fromCamera: boolean) => {
    const req = fromCamera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!req.granted) {
      if (!req.canAskAgain) {
        toast("Permission blocked. Opening settings…", "error");
        Linking.openSettings();
      } else {
        toast(`${fromCamera ? "Camera" : "Photos"} permission is needed for the site photo`, "info");
      }
      return;
    }
    const res = fromCamera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.6 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.6 });
    if (!res.canceled && res.assets?.[0]) setPhoto(res.assets[0].uri);
  };

  const submit = async () => {
    setErr(null);
    if (!receiver.trim()) return setErr("Enter the receiver's name");
    if (!qty || Number(qty) <= 0) return setErr("Enter the delivered quantity");
    if (strokes.length === 0 && !current) return setErr("Capture the receiver's signature");
    setSubmitting(true);
    try {
      let photoPath: string | null = null;
      if (photo) {
        try {
          photoPath = await uploadImage(photo, token!, id!);
        } catch {
          toast("Photo upload failed — submitting without it", "info");
        }
      }
      await apiPost(`/driver/trips/${id}/pod`, token!, {
        receiver_name: receiver.trim(),
        delivered_quantity: Number(qty),
        remarks: remarks.trim() || null,
        photo_path: photoPath,
        signature: JSON.stringify(strokes.length ? strokes : [current]),
      });
      toast("Delivery completed!", "success");
      router.replace("/driver");
    } catch (e: any) {
      setErr(e.detail || "Could not submit POD");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <View style={{ height: insets.top }} />
      <View style={[styles.header, { borderBottomColor: colors.divider }]}>
        <Pressable testID="pod-back" onPress={() => router.back()} style={[styles.iconBtn, { borderColor: colors.border }]}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <AppText variant="title">Proof of Delivery</AppText>
      </View>

      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing["3xl"] }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        <Input testID="pod-receiver" label="Received by (name)" value={receiver} onChangeText={setReceiver} placeholder="Site engineer / supervisor" autoCapitalize="words" />
        <Input testID="pod-qty" label="Delivered quantity (m³)" value={qty} onChangeText={(t) => setQty(t.replace(/[^0-9.]/g, ""))} keyboardType="numeric" placeholder="e.g. 6" />
        <Input testID="pod-remarks" label="Remarks (optional)" value={remarks} onChangeText={setRemarks} placeholder="Any notes" autoCapitalize="sentences" />

        {/* Site photo */}
        <View style={{ gap: spacing.sm }}>
          <AppText variant="heading">Site Photo</AppText>
          {photo ? (
            <View>
              <Image source={{ uri: photo }} style={styles.photo} contentFit="cover" />
              <Pressable testID="pod-photo-remove" onPress={() => setPhoto(null)} style={[styles.removeBtn, { backgroundColor: colors.error }]}>
                <Ionicons name="close" size={16} color="#fff" />
              </Pressable>
            </View>
          ) : (
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <Pressable testID="pod-camera" onPress={() => pickImage(true)} style={[styles.photoBtn, { borderColor: colors.border }]}>
                <Ionicons name="camera-outline" size={22} color={colors.brand} />
                <AppText variant="caption">Camera</AppText>
              </Pressable>
              <Pressable testID="pod-gallery" onPress={() => pickImage(false)} style={[styles.photoBtn, { borderColor: colors.border }]}>
                <Ionicons name="images-outline" size={22} color={colors.brand} />
                <AppText variant="caption">Gallery</AppText>
              </Pressable>
            </View>
          )}
        </View>

        {/* Signature */}
        <View style={{ gap: spacing.sm }}>
          <View style={styles.rowBetween}>
            <AppText variant="heading">Signature</AppText>
            <Pressable testID="pod-sign-clear" onPress={() => { setStrokes([]); setCurrent(""); }}>
              <AppText variant="label" color={colors.brand}>Clear</AppText>
            </Pressable>
          </View>
          <View testID="pod-signature" style={[styles.sign, { backgroundColor: colors.surfaceSecondary, borderColor: colors.border }]} {...pan.panHandlers}>
            <Svg style={StyleSheet.absoluteFill}>
              {strokes.map((d, i) => <Path key={i} d={d} stroke={colors.onSurface} strokeWidth={2.5} fill="none" />)}
              {current ? <Path d={current} stroke={colors.onSurface} strokeWidth={2.5} fill="none" /> : null}
            </Svg>
            {strokes.length === 0 && !current ? (
              <AppText variant="caption" style={{ position: "absolute", alignSelf: "center", top: "45%" }}>Sign here</AppText>
            ) : null}
          </View>
        </View>

        {err ? <AppText variant="caption" color={colors.error}>{err}</AppText> : null}
        <Button testID="pod-submit" label="Submit POD & Mark Delivered" loading={submitting} onPress={submit} icon={<Ionicons name="checkmark-done-outline" size={18} color={colors.onBrand} />} />
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  photoBtn: { flex: 1, alignItems: "center", justifyContent: "center", gap: 4, height: 90, borderRadius: radius.md, borderWidth: 1, borderStyle: "dashed" },
  photo: { width: "100%", height: 200, borderRadius: radius.md },
  removeBtn: { position: "absolute", top: spacing.sm, right: spacing.sm, width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  sign: { height: 180, borderRadius: radius.md, borderWidth: 1, overflow: "hidden" },
});

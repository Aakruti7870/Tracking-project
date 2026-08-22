import { Platform } from "react-native";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

// Uploads a local image uri to the backend -> object storage. Returns storage path.
export async function uploadImage(uri: string, token: string): Promise<string> {
  const name = `pod_${Date.now()}.jpg`;
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    form.append("file", { uri, name, type: "image/jpeg" } as any);
  }
  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }, // never set Content-Type for multipart
    body: form,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || "Upload failed");
  }
  const data = await res.json();
  return data.path as string;
}

// Build an authenticated URL for displaying a stored image via expo-image.
export function fileUrl(path: string, token: string): string {
  return `${BASE}/files/${path}?token=${encodeURIComponent(token)}`;
}

import { Platform } from "react-native";
import * as Location from "expo-location";
import * as TaskManager from "expo-task-manager";

import { storage } from "@/src/utils/storage";

export const TRIP_LOCATION_TASK = "trackmyrmc-active-trip-location";
const ACTIVE_TRIP_KEY = "tmrmc_active_trip_id";
const TOKEN_KEY = "tmrmc_token";

const activeStatuses = new Set(["EN_ROUTE", "ARRIVED", "AT_SITE", "UNLOADING", "POD_PENDING"]);

function backendBase(): string | null {
  const raw = process.env.EXPO_PUBLIC_BACKEND_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/$/, "");
}

async function postLocation(tripId: string, location: Location.LocationObject): Promise<void> {
  const base = backendBase();
  if (!base || !tripId) return;

  const token = await storage.secureGet<string>(TOKEN_KEY, "");
  if (!token) return;

  const { latitude, longitude, accuracy } = location.coords;
  try {
    await fetch(`${base}/api/driver/trips/${encodeURIComponent(tripId)}/location`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        lat: latitude,
        lng: longitude,
        accuracy: accuracy ?? undefined,
      }),
    });
  } catch {
    // Location delivery is best-effort. The next update retries naturally.
  }
}

// TaskManager tasks must be defined at module/global scope so Android can invoke
// them even when no React screen is mounted.
if (!TaskManager.isTaskDefined(TRIP_LOCATION_TASK)) {
  TaskManager.defineTask(TRIP_LOCATION_TASK, async ({ data, error }) => {
    if (error || !data) return;
    const tripId = await storage.getItem<string>(ACTIVE_TRIP_KEY, "");
    if (!tripId) return;

    const payload = data as { locations?: Location.LocationObject[] };
    const latest = payload.locations?.[payload.locations.length - 1];
    if (latest) await postLocation(tripId, latest);
  });
}

export type TrackingStartResult =
  | { mode: "background" }
  | { mode: "foreground"; subscription: Location.LocationSubscription }
  | { mode: "denied" }
  | { mode: "unavailable" };

export function shouldTrackTrip(status?: string | null): boolean {
  return !!status && activeStatuses.has(status);
}

async function startForegroundWatcher(tripId: string): Promise<Location.LocationSubscription> {
  return Location.watchPositionAsync(
    {
      accuracy: Location.Accuracy.High,
      timeInterval: 15_000,
      distanceInterval: 25,
    },
    (location) => {
      void postLocation(tripId, location);
    },
  );
}

export async function startTripLocationTracking(tripId: string): Promise<TrackingStartResult> {
  if (!tripId || Platform.OS === "web") return { mode: "unavailable" };

  const servicesEnabled = await Location.hasServicesEnabledAsync();
  if (!servicesEnabled) return { mode: "unavailable" };

  const foreground = await Location.requestForegroundPermissionsAsync();
  if (foreground.status !== "granted") return { mode: "denied" };

  await storage.setItem(ACTIVE_TRIP_KEY, tripId);

  // Send an immediate point rather than waiting for the first watch interval.
  try {
    const current = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
    await postLocation(tripId, current);
  } catch {
    // A watcher may still receive a position shortly afterwards.
  }

  // Android delivery tracking should continue while the driver backgrounds the
  // app. If background permission is refused, degrade to foreground tracking
  // instead of making the trip workflow unusable.
  if (Platform.OS === "android") {
    try {
      const background = await Location.requestBackgroundPermissionsAsync();
      const taskAvailable = await TaskManager.isAvailableAsync();
      if (background.status === "granted" && taskAvailable) {
        const registered = await TaskManager.isTaskRegisteredAsync(TRIP_LOCATION_TASK);
        if (!registered) {
          await Location.startLocationUpdatesAsync(TRIP_LOCATION_TASK, {
            accuracy: Location.Accuracy.High,
            timeInterval: 15_000,
            distanceInterval: 25,
            deferredUpdatesInterval: 30_000,
            deferredUpdatesDistance: 25,
            foregroundService: {
              notificationTitle: "TrackMyRMC delivery tracking",
              notificationBody: "Mixer location is shared only while your delivery trip is active.",
              killServiceOnDestroy: false,
            },
          });
        }
        return { mode: "background" };
      }
    } catch {
      // Fall back to foreground-only tracking below.
    }
  }

  return { mode: "foreground", subscription: await startForegroundWatcher(tripId) };
}

export async function stopTripLocationTracking(): Promise<void> {
  await storage.removeItem(ACTIVE_TRIP_KEY);
  try {
    const registered = await TaskManager.isTaskRegisteredAsync(TRIP_LOCATION_TASK);
    if (registered) await Location.stopLocationUpdatesAsync(TRIP_LOCATION_TASK);
  } catch {
    // Safe during logout, permission changes, or unsupported environments.
  }
}

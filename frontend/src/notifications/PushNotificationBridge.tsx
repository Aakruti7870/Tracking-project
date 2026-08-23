import { useEffect, useRef } from "react";
import { useRouter } from "expo-router";
import { Platform } from "react-native";

import { useAuth } from "@/src/auth/AuthContext";
import {
  configureForegroundNotifications,
  getLastNotificationRoute,
  registerPushDevice,
  subscribeToNotificationResponses,
  subscribeToPushTokenChanges,
} from "@/src/notifications/pushClient";

export function PushNotificationBridge() {
  const { token, user } = useAuth();
  const router = useRouter();
  const coldStartHandled = useRef(false);

  useEffect(() => {
    if (Platform.OS !== "android" || !token || !user) return;
    let disposed = false;
    let removeTokenListener = () => undefined;

    void (async () => {
      await configureForegroundNotifications();
      await registerPushDevice(token);
      const remove = await subscribeToPushTokenChanges(token);
      if (disposed) remove();
      else removeTokenListener = remove;
    })().catch(() => undefined);

    return () => {
      disposed = true;
      removeTokenListener();
    };
  }, [token, user]);

  useEffect(() => {
    if (Platform.OS !== "android" || !token) return;
    let disposed = false;
    let removeResponseListener = () => undefined;
    const openRoute = (route: string) => {
      if (!disposed) router.push(route as never);
    };

    void (async () => {
      const remove = await subscribeToNotificationResponses(openRoute);
      if (disposed) {
        remove();
        return;
      }
      removeResponseListener = remove;
      if (!coldStartHandled.current) {
        coldStartHandled.current = true;
        const route = await getLastNotificationRoute();
        if (route) openRoute(route);
      }
    })().catch(() => undefined);

    return () => {
      disposed = true;
      removeResponseListener();
    };
  }, [router, token]);

  return null;
}

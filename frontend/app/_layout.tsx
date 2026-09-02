import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useCallback, useEffect, useState } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { KeyboardProvider } from "react-native-keyboard-controller";
import { useFonts } from "expo-font";

// Registers the background location task at JS module scope before any screen
// mounts. TaskManager requires this for Android background execution.
import "@/src/location/tripTracking";
import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { ThemeProvider } from "@/src/theme/ThemeProvider";
import { AuthProvider } from "@/src/auth/AuthContext";
import { ToastProvider } from "@/src/components/ui/Toast";
import { PushNotificationBridge } from "@/src/notifications/PushNotificationBridge";
import { BackgroundLocationConsentProvider } from "@/src/location/BackgroundLocationConsent";

// Keep the native splash visible from cold start until fonts and the persisted
// theme preference are ready. Do not suppress LogBox globally: development
// warnings are useful signals for performance, lifecycle, and deprecation bugs.
void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [themeReady, setThemeReady] = useState(false);
  const [iconsLoaded, iconError] = useIconFonts();
  const [fontsLoaded, fontError] = useFonts({
    "Outfit-SemiBold": require("../assets/fonts/Outfit-SemiBold.ttf"),
    "Outfit-Bold": require("../assets/fonts/Outfit-Bold.ttf"),
    "Jakarta-Regular": require("../assets/fonts/Jakarta-Regular.ttf"),
    "Jakarta-Medium": require("../assets/fonts/Jakarta-Medium.ttf"),
    "Jakarta-SemiBold": require("../assets/fonts/Jakarta-SemiBold.ttf"),
    "Jakarta-Bold": require("../assets/fonts/Jakarta-Bold.ttf"),
  });

  const iconsReady = iconsLoaded || !!iconError;
  const fontsReady = fontsLoaded || !!fontError;
  const handleThemeReady = useCallback(() => setThemeReady(true), []);

  useEffect(() => {
    if (iconsReady && fontsReady && themeReady) {
      void SplashScreen.hideAsync();
    }
  }, [iconsReady, fontsReady, themeReady]);

  if (!iconsReady || !fontsReady) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <KeyboardProvider>
          <ThemeProvider onReady={handleThemeReady}>
            <AuthProvider>
              <ToastProvider>
                <PushNotificationBridge />
                <BackgroundLocationConsentProvider />
                <Stack screenOptions={{ headerShown: false, animation: "fade" }} />
              </ToastProvider>
            </AuthProvider>
          </ThemeProvider>
        </KeyboardProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

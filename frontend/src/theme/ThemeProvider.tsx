import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { storage } from "@/src/utils/storage";
import { ThemeColors, darkColors, lightColors } from "./tokens";

type Scheme = "light" | "dark";
type ThemeMode = "system" | "light" | "dark";

type ThemeContextValue = {
  colors: ThemeColors;
  scheme: Scheme;
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  toggle: () => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
const MODE_KEY = "tmrmc_theme_mode";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>("dark");

  useEffect(() => {
    (async () => {
      const saved = await storage.getItem<string>(MODE_KEY, "dark");
      if (saved === "system" || saved === "light" || saved === "dark") {
        setModeState(saved);
      }
    })();
  }, []);

  const scheme: Scheme = mode === "system" ? (system === "light" ? "light" : "dark") : mode;
  const colors = scheme === "light" ? lightColors : darkColors;

  const setMode = (m: ThemeMode) => {
    setModeState(m);
    storage.setItem(MODE_KEY, m);
  };

  const toggle = () => setMode(scheme === "dark" ? "light" : "dark");

  const value = useMemo(
    () => ({ colors, scheme, mode, setMode, toggle }),
    [colors, scheme, mode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

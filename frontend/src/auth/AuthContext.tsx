import React, { createContext, useContext, useEffect, useState } from "react";

import { storage } from "@/src/utils/storage";
import {
  apiGet,
  apiPost,
  exchangeGoogleStaffCode,
  requestOtp,
  verifyOtp,
} from "@/src/api/client";
import { stopTripLocationTracking } from "@/src/location/tripTracking";
import { unregisterPushDevice } from "@/src/notifications/pushClient";

const TOKEN_KEY = "tmrmc_token";

export type Me = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
  role_label: string;
  roles: string[];
  plant_id: string | null;
  status: string;
  kyc_status: string;
};

type AuthContextValue = {
  hydrating: boolean;
  token: string | null;
  user: Me | null;
  requestOtp: typeof requestOtp;
  verify: (identifier: string, code: string) => Promise<Me>;
  verifyGoogle: (code: string) => Promise<Me>;
  refreshMe: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [hydrating, setHydrating] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<Me | null>(null);

  useEffect(() => {
    (async () => {
      const saved = await storage.secureGet<string>(TOKEN_KEY, "");
      if (saved) {
        try {
          const me = await apiGet<Me>("/me", saved);
          setToken(saved);
          setUser(me);
        } catch {
          await stopTripLocationTracking();
          await storage.secureRemove(TOKEN_KEY);
        }
      }
      setHydrating(false);
    })();
  }, []);

  const acceptSession = async (accessToken: string): Promise<Me> => {
    const stored = await storage.secureSet(TOKEN_KEY, accessToken);
    if (!stored) throw new Error("Unable to securely store login session");
    try {
      const me = await apiGet<Me>("/me", accessToken);
      setToken(accessToken);
      setUser(me);
      return me;
    } catch (error) {
      await storage.secureRemove(TOKEN_KEY);
      setToken(null);
      setUser(null);
      throw error;
    }
  };

  const verify = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyOtp(identifier, code);
    return acceptSession(res.access_token);
  };

  const verifyGoogle = async (code: string): Promise<Me> => {
    const res = await exchangeGoogleStaffCode(code);
    return acceptSession(res.access_token);
  };

  const refreshMe = async () => {
    if (!token) return;
    try {
      const me = await apiGet<Me>("/me", token);
      setUser(me);
    } catch {
      /* keep existing; explicit auth failures are handled by normal navigation */
    }
  };

  const signOut = async () => {
    await stopTripLocationTracking();
    if (token) {
      try {
        await unregisterPushDevice(token);
      } catch {
        /* push cleanup is best effort; server/session logout must still run */
      }
      try {
        await apiPost("/auth/logout", token);
      } catch {
        /* local logout must still succeed when the network is unavailable */
      }
    }
    await storage.secureRemove(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ hydrating, token, user, requestOtp, verify, verifyGoogle, refreshMe, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

import React, { createContext, useContext, useEffect, useState } from "react";

import { storage } from "@/src/utils/storage";
import { apiGet, apiPost, requestOtp, verifyOtp } from "@/src/api/client";

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
          await storage.secureRemove(TOKEN_KEY);
        }
      }
      setHydrating(false);
    })();
  }, []);

  const verify = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyOtp(identifier, code);
    await storage.secureSet(TOKEN_KEY, res.access_token);
    setToken(res.access_token);
    const me = await apiGet<Me>("/me", res.access_token);
    setUser(me);
    return me;
  };

  const refreshMe = async () => {
    if (!token) return;
    try {
      const me = await apiGet<Me>("/me", token);
      setUser(me);
    } catch {
      /* keep existing */
    }
  };

  const signOut = async () => {
    if (token) {
      try {
        await apiPost("/auth/logout", token);
      } catch {
        /* ignore network errors on logout */
      }
    }
    await storage.secureRemove(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ hydrating, token, user, requestOtp, verify, refreshMe, signOut }}
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

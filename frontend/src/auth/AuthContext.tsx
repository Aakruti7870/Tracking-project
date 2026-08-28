import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { storage } from "@/src/utils/storage";
import {
  apiGet,
  apiPost,
  demoLogin as apiDemoLogin,
  exchangeGoogleStaffCode,
  exchangeStaffPasskeyHandoff,
  playReviewLogin,
  PlayReviewRole,
  requestOtp,
  requestStaffOtp,
  staffAuthMethod,
  verifyOtp,
  verifyStaffOtp,
  verifyStaffRecovery,
  verifyStaffTotp,
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
  mfa_enabled?: boolean;
  mfa_configured?: boolean;
  passkey_enabled?: boolean;
  passkey_count?: number;
};

type AuthContextValue = {
  hydrating: boolean;
  token: string | null;
  user: Me | null;
  requestOtp: typeof requestOtp;
  requestStaffOtp: typeof requestStaffOtp;
  staffAuthMethod: typeof staffAuthMethod;
  verify: (identifier: string, code: string) => Promise<Me>;
  verifyStaff: (identifier: string, code: string) => Promise<Me>;
  verifyStaffAuthenticator: (identifier: string, code: string) => Promise<Me>;
  verifyStaffRecovery: (identifier: string, code: string) => Promise<Me>;
  completeStaffPasskey: (handoffCode: string) => Promise<Me>;
  verifyGoogle: (code: string) => Promise<Me>;
  demoLogin: (role: string) => Promise<Me>;
  verifyPlayReview: (role: PlayReviewRole, accessCode: string) => Promise<Me>;
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

  const acceptSession = useCallback(async (accessToken: string): Promise<Me> => {
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
  }, []);

  const verify = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyOtp(identifier, code);
    return acceptSession(res.access_token);
  };

  const verifyStaff = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyStaffOtp(identifier, code);
    return acceptSession(res.access_token);
  };

  const verifyStaffAuthenticator = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyStaffTotp(identifier, code);
    return acceptSession(res.access_token);
  };

  const verifyStaffRecoveryCode = async (identifier: string, code: string): Promise<Me> => {
    const res = await verifyStaffRecovery(identifier, code);
    return acceptSession(res.access_token);
  };

  const completeStaffPasskey = useCallback(async (handoffCode: string): Promise<Me> => {
    const res = await exchangeStaffPasskeyHandoff(handoffCode);
    return acceptSession(res.access_token);
  }, [acceptSession]);

  // Kept for backward compatibility and rollback safety. The normal Plant Staff
  // login UI no longer exposes Google OAuth.
  const verifyGoogle = async (code: string): Promise<Me> => {
    const res = await exchangeGoogleStaffCode(code);
    return acceptSession(res.access_token);
  };

  const demoLogin = async (role: string): Promise<Me> => {
    const res = await apiDemoLogin(role);
    return acceptSession(res.access_token);
  };

  const verifyPlayReview = async (role: PlayReviewRole, accessCode: string): Promise<Me> => {
    const res = await playReviewLogin(role, accessCode);
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
      value={{
        hydrating,
        token,
        user,
        requestOtp,
        requestStaffOtp,
        staffAuthMethod,
        verify,
        verifyStaff,
        verifyStaffAuthenticator,
        verifyStaffRecovery: verifyStaffRecoveryCode,
        completeStaffPasskey,
        verifyGoogle,
        demoLogin,
        verifyPlayReview,
        refreshMe,
        signOut,
      }}
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

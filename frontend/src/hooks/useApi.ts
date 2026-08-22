import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";

export function useGet<T>(path: string) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (showSpinner = true) => {
      if (!token) return;
      if (showSpinner) setLoading(true);
      setError(null);
      try {
        const res = await apiGet<T>(path, token);
        setData(res);
      } catch (e: any) {
        setError(e.detail || "Something went wrong");
      } finally {
        setLoading(false);
      }
    },
    [path, token],
  );

  useEffect(() => {
    load(true);
  }, [load]);

  return { data, loading, error, refetch: () => load(false), reload: () => load(true) };
}

import { useCallback, useEffect, useRef, useState } from "react";

import { apiErrorDetail, apiGet } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";

export function useGet<T>(path: string | null) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(
    async (showSpinner = true) => {
      const currentRequest = ++requestId.current;
      if (!token || !path) { setLoading(false); return; }
      if (showSpinner) setLoading(true);
      setError(null);
      try {
        const res = await apiGet<T>(path, token);
        if (currentRequest === requestId.current) setData(res);
      } catch (error: unknown) {
        if (currentRequest === requestId.current) setError(apiErrorDetail(error, "Something went wrong"));
      } finally {
        if (currentRequest === requestId.current) setLoading(false);
      }
    },
    [path, token],
  );

  useEffect(() => {
    load(true);
    return () => { requestId.current += 1; };
  }, [load]);

  return { data, loading, error, refetch: () => load(false), reload: () => load(true) };
}

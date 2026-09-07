"use client";

/**
 * Data fetching.
 *
 * Small on purpose: a request, a loading flag, an error and a retry. Every
 * screen gets the same four states, which is what makes §45 enforceable.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, clearSession } from "@/lib/api";

type UseApiResult<T> = {
  data: T | null;
  error: unknown;
  loading: boolean;
  refetch: () => void;
  setData: (data: T) => void;
};

export function useApi<T>(path: string | null, deps: unknown[] = []): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [nonce, setNonce] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);

    api
      .get<T>(path, controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) return;
        setData(payload);
        setError(null);
      })
      .catch((caught) => {
        if (controller.signal.aborted || (caught as Error)?.name === "AbortError") return;
        // An expired token must not leave a half-rendered screen behind.
        if (caught instanceof ApiError && caught.isAuthError) clearSession();
        setError(caught);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce, ...deps]);

  const refetch = useCallback(() => setNonce((value) => value + 1), []);

  return { data, error, loading, refetch, setData };
}

/** For writes: tracks the in-flight state and the resulting error. */
export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setPending(true);
      setError(null);
      try {
        return await action(...args);
      } catch (caught) {
        setError(caught);
        return null;
      } finally {
        setPending(false);
      }
    },
    [action],
  );

  const message =
    error instanceof ApiError ? error.message : error ? "Something went wrong. Please try again." : null;

  return { run, pending, error, message, reset: () => setError(null) };
}

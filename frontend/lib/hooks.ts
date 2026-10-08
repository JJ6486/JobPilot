"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError, type TaskStatus } from "@/lib/api";

type AsyncState<T> = { data: T | null; error: ApiError | null; loading: boolean };

/**
 * Load data on mount (and when `deps` change). State is only set after the promise settles,
 * which keeps effects free of synchronous setState calls.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true });
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  const run = useCallback(
    () =>
      loadRef
        .current()
        .then((data) => setState({ data, error: null, loading: false }))
        .catch((err: unknown) =>
          setState((s) => ({
            data: s.data,
            loading: false,
            error: err instanceof ApiError ? err : new ApiError(0, String(err)),
          })),
        ),
    [],
  );

  useEffect(() => {
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- callers pass explicit deps
  }, deps);

  const setData = useCallback((data: T) => setState({ data, error: null, loading: false }), []);
  return { ...state, reload: run, setData };
}

const POLL_MS = 1500;

/** Poll a background task until it finishes. */
export function useTask(taskId: string | null, onFinish?: (task: TaskStatus) => void) {
  const [task, setTask] = useState<TaskStatus | null>(null);
  const finishRef = useRef(onFinish);
  useEffect(() => {
    finishRef.current = onFinish;
  });

  useEffect(() => {
    if (!taskId) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = () =>
      api
        .task(taskId)
        .then((t) => {
          if (!alive) return;
          setTask(t);
          if (t.state === "done" || t.state === "error") finishRef.current?.(t);
          else timer = setTimeout(tick, POLL_MS);
        })
        .catch(() => {
          if (alive) timer = setTimeout(tick, POLL_MS * 2);
        });
    void tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [taskId]);

  return taskId ? task : null;
}

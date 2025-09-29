export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit & { timeoutMs?: number }
): Promise<Response> {
  const { timeoutMs, signal, ...rest } = init ?? {};

  // If no timeout was supplied, do a plain fetch (no AbortController / no timeout).
  if (timeoutMs === undefined) {
    return fetch(input, init);
  }

  // Timeout branch
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), Math.max(0, timeoutMs));

  // Merge any caller-provided signal with our timeout signal
  const mergedSignal =
    signal
      ? (('any' in AbortSignal)
          ? AbortSignal.any([signal, controller.signal])
          : mergeSignals(signal, controller.signal))
      : controller.signal;

  try {
    return await fetch(input, { ...rest, signal: mergedSignal });
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fallback for environments without AbortSignal.any.
 * Returns a signal that aborts if either `a` or `b` aborts.
 */
function mergeSignals(a: AbortSignal, b: AbortSignal): AbortSignal {
  // If available at runtime, prefer native any()
  if (AbortSignal.any) {
    return AbortSignal.any([a, b]);
  }
  const proxy = new AbortController();

  const forwardAbort = (src: AbortSignal) => {
    if (src.aborted) {
      proxy.abort(src.reason);
    } else {
      src.addEventListener('abort', () => proxy.abort(src.reason), { once: true });
    }
  };

  forwardAbort(a);
  forwardAbort(b);

  return proxy.signal;
}

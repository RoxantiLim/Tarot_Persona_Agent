type LocalStateEnvelope<T> = {
  version: number;
  data: T;
};

export function loadLocalState<T>(key: string, version: number): T | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(key);
    if (!rawValue) {
      return null;
    }

    const parsedValue = JSON.parse(rawValue) as Partial<LocalStateEnvelope<T>>;
    if (parsedValue.version !== version || parsedValue.data === undefined) {
      return null;
    }

    return parsedValue.data;
  } catch {
    return null;
  }
}

export function saveLocalState<T>(key: string, version: number, data: T) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify({ version, data }));
  } catch {
    // Storage can fail in private browsing or when the quota is full.
  }
}

export function clearLocalState(key: string) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore storage failures. The in-memory page state still resets.
  }
}

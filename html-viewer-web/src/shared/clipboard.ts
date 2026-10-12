import { useCallback, useEffect, useRef, useState } from 'react';

/** Copies text and exposes a short-lived "copied" flag for button feedback. */
export function useCopy(resetMs = 1800) {
  const [copied, setCopied] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text: string, key: string = text) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // Clipboard API blocked (permissions, non-secure origin): older route.
        if (!legacyCopy(text)) return;
      }
      setCopied(key);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(null), resetMs);
    },
    [resetMs],
  );

  return { copy, copied };
}

function legacyCopy(text: string): boolean {
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  // Inside an open modal only its own content can take focus.
  const host = document.querySelector('dialog[open]') ?? document.body;
  host.appendChild(area);
  area.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    area.remove();
  }
}

export const absoluteUrl = (path: string) => new URL(path, window.location.origin).toString();

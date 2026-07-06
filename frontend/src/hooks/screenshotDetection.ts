/** Detect OS and browser screenshot shortcuts during a proctored session. */
export function isScreenshotShortcut(event: KeyboardEvent): boolean {
  const { key, code, metaKey, shiftKey, ctrlKey, altKey } = event;

  if (key === 'PrintScreen' || code === 'PrintScreen' || code === 'Snapshot') {
    return true;
  }

  if (altKey && (key === 'PrintScreen' || code === 'PrintScreen')) {
    return true;
  }

  // macOS: Cmd+Shift+3/4/5 — Windows: Win+Shift+S (meta+shift+s)
  if (metaKey && shiftKey) {
    if (['3', '4', '5', 'Digit3', 'Digit4', 'Digit5', 's', 'S'].includes(key)) {
      return true;
    }
  }

  // Some browsers / tools: Ctrl+Shift+S
  if (ctrlKey && shiftKey && (key === 's' || key === 'S')) {
    return true;
  }

  return false;
}

export async function clipboardContainsImage(): Promise<boolean> {
  if (!navigator.clipboard?.read) {
    return false;
  }

  const items = await navigator.clipboard.read();
  return items.some((item) => item.types.some((type) => type.startsWith('image/')));
}

import { useCallback, useEffect, useRef } from 'react';

const VIRTUAL_CAMERA_PATTERNS = [
  /obs/i,
  /manycam/i,
  /droidcam/i,
  /epoccam/i,
  /iriun/i,
  /snap camera/i,
  /virtual/i,
  /camo/i,
  /mmhmm/i,
  /xsplit/i,
];

const POLL_MS = 2000;
const FLAG_COOLDOWN_MS = 5000;

interface UseCameraIntegrityOptions {
  streamRef: React.RefObject<MediaStream | null>;
  enabled: boolean;
  onFlag: (eventType: string, confidence?: number) => void;
}

function isVirtualCameraLabel(label: string): boolean {
  return VIRTUAL_CAMERA_PATTERNS.some((pattern) => pattern.test(label));
}

export function useCameraIntegrity({
  streamRef,
  enabled,
  onFlag,
}: UseCameraIntegrityOptions) {
  const trustedDeviceIdRef = useRef<string | null>(null);
  const trustedLabelRef = useRef<string | null>(null);
  const lastFlagRef = useRef<Record<string, number>>({});

  const flagOnce = useCallback(
    (eventType: string, confidence = 0.9) => {
      const now = Date.now();
      const last = lastFlagRef.current[eventType] ?? 0;
      if (now - last < FLAG_COOLDOWN_MS) return;
      lastFlagRef.current[eventType] = now;
      onFlag(eventType, confidence);
    },
    [onFlag]
  );

  const registerStream = useCallback(
    (stream: MediaStream) => {
      const track = stream.getVideoTracks()[0];
      if (!track) return;

      const settings = track.getSettings();
      trustedDeviceIdRef.current = settings.deviceId ?? null;
      trustedLabelRef.current = track.label;

      if (isVirtualCameraLabel(track.label)) {
        flagOnce('camera_changed', 0.88);
      }

      track.onended = () => {
        flagOnce('camera_disconnected', 1.0);
      };
    },
    [flagOnce]
  );

  useEffect(() => {
    if (!enabled) return;

    const onDeviceChange = () => {
      const track = streamRef.current?.getVideoTracks()[0];
      if (!track) {
        flagOnce('camera_disconnected', 0.95);
        return;
      }

      const settings = track.getSettings();
      const deviceId = settings.deviceId ?? null;
      const label = track.label;

      if (
        trustedDeviceIdRef.current &&
        deviceId &&
        deviceId !== trustedDeviceIdRef.current
      ) {
        flagOnce('camera_changed', 0.95);
        trustedDeviceIdRef.current = deviceId;
        trustedLabelRef.current = label;
      }

      if (isVirtualCameraLabel(label)) {
        flagOnce('camera_changed', 0.9);
      }
    };

    const interval = window.setInterval(() => {
      const stream = streamRef.current;
      const track = stream?.getVideoTracks()[0];
      if (!track || track.readyState === 'ended') {
        flagOnce('camera_disconnected', 1.0);
        return;
      }

      const settings = track.getSettings();
      if (
        trustedDeviceIdRef.current &&
        settings.deviceId &&
        settings.deviceId !== trustedDeviceIdRef.current
      ) {
        flagOnce('camera_changed', 0.95);
        trustedDeviceIdRef.current = settings.deviceId;
      }

      if (trustedLabelRef.current && track.label !== trustedLabelRef.current) {
        flagOnce('camera_changed', 0.92);
        trustedLabelRef.current = track.label;
      }
    }, POLL_MS);

    navigator.mediaDevices?.addEventListener('devicechange', onDeviceChange);

    return () => {
      window.clearInterval(interval);
      navigator.mediaDevices?.removeEventListener('devicechange', onDeviceChange);
    };
  }, [enabled, streamRef, flagOnce]);

  return { registerStream };
}

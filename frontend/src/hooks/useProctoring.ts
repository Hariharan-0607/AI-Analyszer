import { useCallback, useEffect, useRef } from 'react';
import { postVivaEvent, ProctoringConfig, ProctoringEventPayload } from '../api/client';
import { clipboardContainsImage, isScreenshotShortcut } from './screenshotDetection';

export type { ProctoringConfig };

interface UseProctoringOptions {
  sessionId: string | null;
  enabled: boolean;
  config: ProctoringConfig | null;
  onFlag?: (type: string) => void;
}

function isoNow(): string {
  return new Date().toISOString();
}

const SCREENSHOT_STRIKE_COOLDOWN_MS = 1500;
const GAZE_FLAG_COOLDOWN_MS = 4000;
const MULTI_FACE_COOLDOWN_MS = 5000;
const DEVICE_FLAG_COOLDOWN_MS = 5000;

export function useProctoring({ sessionId, enabled, config, onFlag }: UseProctoringOptions) {
  const sentEventsRef = useRef<Set<string>>(new Set());
  const gazeStartRef = useRef<number | null>(null);
  const noFaceStartRef = useRef<number | null>(null);
  const lastHeartbeatRef = useRef<number>(0);
  const lastScreenshotStrikeRef = useRef<number>(0);
  const lastGazeFlagRef = useRef<number>(0);
  const lastMultiFaceFlagRef = useRef<number>(0);
  const lastDeviceFlagRef = useRef<number>(0);

  const emit = useCallback(
    async (event: Omit<ProctoringEventPayload, 'session_id' | 'timestamp'>) => {
      if (!sessionId) return;
      const payload: ProctoringEventPayload = {
        session_id: sessionId,
        timestamp: isoNow(),
        ...event,
      };
      try {
        await postVivaEvent(payload);
        onFlag?.(event.event_type);
      } catch (e) {
        console.error('Failed to post event:', e);
      }
    },
    [sessionId, onFlag]
  );

  const emitOnce = useCallback(
    async (eventType: string, extra?: Partial<ProctoringEventPayload>) => {
      const key = `${eventType}-${extra?.duration_ms ?? 'once'}`;
      if (sentEventsRef.current.has(key) && !eventType.includes('snapshot')) return;
      if (!eventType.includes('snapshot')) {
        sentEventsRef.current.add(key);
      }
      await emit({ event_type: eventType, ...extra });
    },
    [emit]
  );

  const emitScreenshotStrike = useCallback(
    async (confidence = 0.9) => {
      const now = Date.now();
      if (now - lastScreenshotStrikeRef.current < SCREENSHOT_STRIKE_COOLDOWN_MS) {
        return;
      }
      lastScreenshotStrikeRef.current = now;
      await emit({ event_type: 'screenshot_detected', confidence });
    },
    [emit]
  );

  const emitDeviceStrike = useCallback(
    async (eventType: string, confidence = 0.9) => {
      const now = Date.now();
      if (now - lastDeviceFlagRef.current < DEVICE_FLAG_COOLDOWN_MS) {
        return;
      }
      lastDeviceFlagRef.current = now;
      await emit({ event_type: eventType, confidence });
    },
    [emit]
  );

  const processFaceState = useCallback(
    (faceCount: number, gazeOffScreen: boolean, gazeConfidence = 0.81) => {
      if (!enabled || !sessionId) return;
      const now = performance.now();

      if (faceCount === 0) {
        if (noFaceStartRef.current === null) noFaceStartRef.current = now;
        const duration = now - noFaceStartRef.current;
        const threshold = (config?.face_not_detected_sec ?? 5) * 1000;
        if (duration >= threshold) {
          emit({
            event_type: 'face_not_detected',
            duration_ms: Math.round(duration),
            confidence: 0.85,
          });
          noFaceStartRef.current = now;
        }
      } else {
        noFaceStartRef.current = null;
      }

      if (faceCount > 1) {
        const cooledDown = now - lastMultiFaceFlagRef.current >= MULTI_FACE_COOLDOWN_MS;
        if (cooledDown) {
          emit({ event_type: 'multiple_faces_detected', confidence: 0.9 });
          lastMultiFaceFlagRef.current = now;
        }
      }

      if (gazeOffScreen && faceCount > 0) {
        if (gazeStartRef.current === null) gazeStartRef.current = now;
        const duration = now - gazeStartRef.current;
        const sustainedThreshold = (config?.gaze_low_sec ?? 2.0) * 1000;
        const cooledDown = now - lastGazeFlagRef.current >= GAZE_FLAG_COOLDOWN_MS;
        if (duration >= sustainedThreshold && cooledDown) {
          emit({
            event_type: 'gaze_off_screen',
            duration_ms: Math.round(duration),
            confidence: gazeConfidence,
          });
          gazeStartRef.current = now;
          lastGazeFlagRef.current = now;
        }
      } else {
        gazeStartRef.current = null;
      }

      const heartbeatInterval = (config?.heartbeat_interval_sec ?? 15) * 1000;
      if (now - lastHeartbeatRef.current >= heartbeatInterval) {
        lastHeartbeatRef.current = now;
        emit({ event_type: 'snapshot_captured', confidence: 1.0 });
      }
    },
    [enabled, sessionId, config, emit, emitOnce]
  );

  useEffect(() => {
    if (!enabled || !sessionId) return;

    const onVisibility = () => {
      if (document.hidden) {
        emit({ event_type: 'tab_switched', confidence: 1.0 });
      }
    };

    const onScreenshotKey = (event: KeyboardEvent) => {
      if (isScreenshotShortcut(event)) {
        event.preventDefault();
        void emitScreenshotStrike(0.92);
      }
    };

    const onCopy = () => {
      void (async () => {
        try {
          const hasImage = await clipboardContainsImage();
          if (hasImage) {
            await emitScreenshotStrike(0.88);
          }
        } catch {
          // Clipboard read blocked — ignore text-only copies.
        }
      })();
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('keydown', onScreenshotKey, true);
    window.addEventListener('keyup', onScreenshotKey, true);
    document.addEventListener('copy', onCopy);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('keydown', onScreenshotKey, true);
      window.removeEventListener('keyup', onScreenshotKey, true);
      document.removeEventListener('copy', onCopy);
    };
  }, [enabled, sessionId, emit, emitScreenshotStrike]);

  return { emit, emitOnce, processFaceState, emitScreenshotStrike, emitDeviceStrike };
}

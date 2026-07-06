import { useCallback, useEffect, useRef, useState } from 'react';
import { FilesetResolver, ObjectDetector } from '@mediapipe/tasks-vision';

const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite';

const SUSPICIOUS_LABELS = new Set(['cell phone', 'laptop', 'tv', 'remote']);

export interface DetectedObject {
  label: string;
  score: number;
}

export function useObjectDetector(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const detectorRef = useRef<ObjectDetector | null>(null);
  const lastRunRef = useRef(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const vision = await FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm'
        );
        const detector = await ObjectDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: MODEL_URL,
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          scoreThreshold: 0.45,
          categoryAllowlist: [...SUSPICIOUS_LABELS],
          maxResults: 5,
        });
        if (!cancelled) {
          detectorRef.current = detector;
          setReady(true);
        }
      } catch (e) {
        console.error('Object detector init failed:', e);
      }
    }

    void init();
    return () => {
      cancelled = true;
      detectorRef.current?.close();
    };
  }, []);

  const detectSuspiciousObjects = useCallback((): DetectedObject[] => {
    const video = videoRef.current;
    const detector = detectorRef.current;
    if (!video || !detector || video.readyState < 2) {
      return [];
    }

    const now = performance.now();
    if (now - lastRunRef.current < 700) {
      return [];
    }
    lastRunRef.current = now;

    const result = detector.detectForVideo(video, now);
    const found: DetectedObject[] = [];

    for (const detection of result.detections) {
      const category = detection.categories?.[0];
      if (!category?.categoryName || category.score == null) continue;
      if (!SUSPICIOUS_LABELS.has(category.categoryName)) continue;
      found.push({
        label: category.categoryName,
        score: category.score,
      });
    }

    return found;
  }, [videoRef]);

  return { ready, detectSuspiciousObjects };
}

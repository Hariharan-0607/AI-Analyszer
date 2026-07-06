import { useCallback, useEffect, useRef, useState } from 'react';
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import {
  extractGazeFeatures,
  GazeEvaluation,
  GazeFeatures,
  GazeTracker,
  gazeTracker,
} from './gazeTracker';

export interface FaceDetectionResult {
  faceCount: number;
  gazeOffScreen: boolean;
  gazeConfidence: number;
  gazeMethod: 'calibrated' | 'fallback' | 'none';
  gazeFeatures: GazeFeatures | null;
  landmarks: { x: number; y: number }[] | null;
}

export function useFaceLandmarker(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastDetectRef = useRef<FaceDetectionResult>({
    faceCount: 0,
    gazeOffScreen: false,
    gazeConfidence: 0,
    gazeMethod: 'none',
    gazeFeatures: null,
    landmarks: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const vision = await FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm'
        );
        const landmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          numFaces: 2,
          minFaceDetectionConfidence: 0.6,
          minFacePresenceConfidence: 0.6,
          minTrackingConfidence: 0.6,
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
        });
        if (!cancelled) {
          landmarkerRef.current = landmarker;
          setReady(true);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load face model');
        }
      }
    }

    init();
    return () => {
      cancelled = true;
      landmarkerRef.current?.close();
    };
  }, []);

  const detect = useCallback((): FaceDetectionResult => {
    const video = videoRef.current;
    const landmarker = landmarkerRef.current;
    if (!video || !landmarker || video.readyState < 2) {
      return lastDetectRef.current;
    }

    const result = landmarker.detectForVideo(video, performance.now());
    const faceCount = result.faceLandmarks?.length ?? 0;

    let gazeOffScreen = false;
    let gazeConfidence = 0;
    let gazeMethod: FaceDetectionResult['gazeMethod'] = 'none';
    let gazeFeatures: GazeFeatures | null = null;
    let landmarks: { x: number; y: number }[] | null = null;

    if (faceCount > 0 && result.faceLandmarks[0]) {
      const lm = result.faceLandmarks[0];
      landmarks = lm.map((p) => ({ x: p.x, y: p.y }));

      const facialMatrix = result.facialTransformationMatrixes?.[0]?.data;
      const blendshapes = result.faceBlendshapes?.[0]?.categories;
      gazeFeatures = extractGazeFeatures(lm, facialMatrix ?? null, blendshapes);

      const gaze: GazeEvaluation = gazeTracker.evaluate(gazeFeatures);
      gazeOffScreen = gaze.offScreen;
      gazeConfidence = gaze.confidence;
      gazeMethod = gaze.calibrated ? 'calibrated' : gazeFeatures ? 'fallback' : 'none';
    }

    const detection: FaceDetectionResult = {
      faceCount,
      gazeOffScreen,
      gazeConfidence,
      gazeMethod,
      gazeFeatures,
      landmarks,
    };
    lastDetectRef.current = detection;
    return detection;
  }, [videoRef]);

  return { ready, error, detect };
}

export function compareFaceLandmarks(
  a: { x: number; y: number }[],
  b: { x: number; y: number }[]
): number {
  if (!a.length || !b.length) return 0;
  const n = Math.min(a.length, b.length, 50);
  let totalDist = 0;
  for (let i = 0; i < n; i++) {
    const dx = a[i].x - b[i].x;
    const dy = a[i].y - b[i].y;
    totalDist += Math.sqrt(dx * dx + dy * dy);
  }
  const avgDist = totalDist / n;
  return Math.max(0, 1 - avgDist * 8);
}

export { gazeTracker, extractGazeFeatures };
export type { GazeFeatures, GazeTracker };

/**
 * Calibrated gaze tracker: iris landmarks + eye blendshapes + head pose,
 * with temporal smoothing to avoid false flags.
 */

export interface Point2D {
  x: number;
  y: number;
}

export interface Landmark {
  x: number;
  y: number;
  z?: number;
}

export interface BlendshapeCategory {
  categoryName?: string;
  score?: number;
}

export interface GazeFeatures {
  vector: number[];
  hasIris: boolean;
  hasBlendshapes: boolean;
}

export interface GazeEvaluation {
  offScreen: boolean;
  confidence: number;
  deviation: number;
  calibrated: boolean;
}

const IRIS_LEFT = 468;
const IRIS_RIGHT = 473;

const LEFT_EYE = { inner: 133, outer: 33, top: 159, bottom: 145 };
const RIGHT_EYE = { inner: 362, outer: 263, top: 386, bottom: 374 };

const EYE_BLENDSHAPES = [
  'eyeLookDownLeft',
  'eyeLookDownRight',
  'eyeLookInLeft',
  'eyeLookInRight',
  'eyeLookOutLeft',
  'eyeLookOutRight',
  'eyeLookUpLeft',
  'eyeLookUpRight',
] as const;

const CALIBRATED_DEVIATION_THRESHOLD = 2.4;
const FALLBACK_DEVIATION_THRESHOLD = 3.2;
const MIN_STD = 0.06;

const FRAMES_TO_CONFIRM_AWAY = 12;
const FRAMES_TO_CONFIRM_ON_SCREEN = 4;

// iris x4, pose x2, eye blendshapes x8
// eyeLookDown has low weight — reading text at the bottom of screen is normal
// eyeLookOut/In (side) and head pose carry more weight as they signal true distraction
const FEATURE_WEIGHTS = [
  1.4, 0.8, 1.4, 0.8,   // iris x/y left, iris x/y right (vertical less important)
  1.6, 1.2,              // head yaw, head pitch
  0.7, 0.7,              // eyeLookDownLeft, eyeLookDownRight (reduced — normal reading)
  1.4, 1.4,              // eyeLookInLeft, eyeLookInRight
  1.4, 1.4,              // eyeLookOutLeft, eyeLookOutRight
  0.8, 0.8,              // eyeLookUpLeft, eyeLookUpRight
];

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function pointAt(landmarks: Landmark[], index: number): Point2D {
  const p = landmarks[index];
  return { x: p.x, y: p.y };
}

function irisOffsetInEye(
  iris: Point2D,
  inner: Point2D,
  outer: Point2D,
  top: Point2D,
  bottom: Point2D
): Point2D {
  const centerX = (inner.x + outer.x) / 2;
  const centerY = (top.y + bottom.y) / 2;
  const halfW = Math.hypot(outer.x - inner.x, outer.y - inner.y) / 2 || 0.01;
  const halfH = Math.hypot(bottom.x - top.x, bottom.y - top.y) / 2 || 0.01;
  return {
    x: (iris.x - centerX) / halfW,
    y: (iris.y - centerY) / halfH,
  };
}

function headPoseFromMatrix(matrix: ArrayLike<number> | null | undefined): Point2D {
  if (!matrix || matrix.length < 16) {
    return { x: 0, y: 0 };
  }
  const pitch = Math.asin(clamp(-matrix[9], -1, 1));
  const yaw = Math.atan2(matrix[8], matrix[10]);
  return { x: yaw, y: pitch };
}

function blendshapeMap(categories: BlendshapeCategory[] | undefined): Record<string, number> {
  const map: Record<string, number> = {};
  if (!categories) return map;
  for (const c of categories) {
    if (c.categoryName) {
      map[c.categoryName] = c.score ?? 0;
    }
  }
  return map;
}

export function extractGazeFeatures(
  landmarks: Landmark[],
  facialMatrix?: ArrayLike<number> | null,
  blendshapeCategories?: BlendshapeCategory[]
): GazeFeatures | null {
  if (!landmarks.length) return null;

  const blends = blendshapeMap(blendshapeCategories);
  const pose = headPoseFromMatrix(facialMatrix);

  let leftIx = 0;
  let leftIy = 0;
  let rightIx = 0;
  let rightIy = 0;
  let hasIris = false;

  if (landmarks.length >= 478) {
    hasIris = true;
    const leftIris = pointAt(landmarks, IRIS_LEFT);
    const rightIris = pointAt(landmarks, IRIS_RIGHT);

    const left = irisOffsetInEye(
      leftIris,
      pointAt(landmarks, LEFT_EYE.inner),
      pointAt(landmarks, LEFT_EYE.outer),
      pointAt(landmarks, LEFT_EYE.top),
      pointAt(landmarks, LEFT_EYE.bottom)
    );
    const right = irisOffsetInEye(
      rightIris,
      pointAt(landmarks, RIGHT_EYE.inner),
      pointAt(landmarks, RIGHT_EYE.outer),
      pointAt(landmarks, RIGHT_EYE.top),
      pointAt(landmarks, RIGHT_EYE.bottom)
    );
    leftIx = left.x;
    leftIy = left.y;
    rightIx = right.x;
    rightIy = right.y;
  }

  const hasBlendshapes = EYE_BLENDSHAPES.some((name) => name in blends);

  const vector = [
    leftIx,
    leftIy,
    rightIx,
    rightIy,
    pose.x,
    pose.y,
    ...EYE_BLENDSHAPES.map((name) => blends[name] ?? 0),
  ];

  return { vector, hasIris, hasBlendshapes };
}

function mean(values: number[][]): number[] {
  if (!values.length) return [];
  const dim = values[0].length;
  const out = new Array(dim).fill(0);
  for (const row of values) {
    for (let i = 0; i < dim; i++) {
      out[i] += row[i];
    }
  }
  return out.map((v) => v / values.length);
}

function std(values: number[][], avg: number[]): number[] {
  if (values.length < 2) {
    return avg.map(() => MIN_STD);
  }
  const dim = avg.length;
  const out = new Array(dim).fill(0);
  for (const row of values) {
    for (let i = 0; i < dim; i++) {
      const d = row[i] - avg[i];
      out[i] += d * d;
    }
  }
  return out.map((v) => Math.max(MIN_STD, Math.sqrt(v / values.length)));
}

function weightedRmsDeviation(current: number[], avg: number[], spread: number[]): number {
  let sum = 0;
  let weightTotal = 0;
  for (let i = 0; i < current.length; i++) {
    const weight = FEATURE_WEIGHTS[i] ?? 1;
    const z = (current[i] - avg[i]) / spread[i];
    sum += weight * z * z;
    weightTotal += weight;
  }
  return Math.sqrt(sum / weightTotal);
}

export class GazeTracker {
  private calibrationSamples: number[][] = [];
  private baseline: number[] | null = null;
  private spread: number[] | null = null;
  private awayStreak = 0;
  private onStreak = 0;
  private confirmedAway = false;

  reset(): void {
    this.calibrationSamples = [];
    this.baseline = null;
    this.spread = null;
    this.awayStreak = 0;
    this.onStreak = 0;
    this.confirmedAway = false;
  }

  get isCalibrated(): boolean {
    return this.baseline !== null && this.spread !== null;
  }

  addCalibrationSample(features: GazeFeatures | null): void {
    if (!features) return;
    this.calibrationSamples.push([...features.vector]);
  }

  finalizeCalibration(): boolean {
    if (this.calibrationSamples.length < 6) {
      return false;
    }
    this.baseline = mean(this.calibrationSamples);
    this.spread = std(this.calibrationSamples, this.baseline);
    this.awayStreak = 0;
    this.onStreak = 0;
    this.confirmedAway = false;
    return true;
  }

  evaluate(features: GazeFeatures | null): GazeEvaluation {
    if (!features) {
      return { offScreen: false, confidence: 0, deviation: 0, calibrated: this.isCalibrated };
    }

    let deviation = 0;
    let instantAway = false;

    if (this.isCalibrated && this.baseline && this.spread) {
      deviation = weightedRmsDeviation(features.vector, this.baseline, this.spread);
      instantAway = deviation >= CALIBRATED_DEVIATION_THRESHOLD;

      // Only flag looking down if it's a strong, deliberate downward look
      // (not just reading text at the bottom of the screen)
      const lookDown = Math.max(features.vector[6] ?? 0, features.vector[7] ?? 0);
      const baseDown = Math.max(this.baseline[6] ?? 0, this.baseline[7] ?? 0);
      if (lookDown > baseDown + 0.28 && deviation >= CALIBRATED_DEVIATION_THRESHOLD - 0.3) {
        instantAway = true;
      }
    } else {
      deviation = this.fallbackDeviation(features);
      instantAway = deviation >= FALLBACK_DEVIATION_THRESHOLD;
    }

    if (instantAway) {
      this.awayStreak += 1;
      this.onStreak = 0;
    } else {
      this.onStreak += 1;
      this.awayStreak = Math.max(0, this.awayStreak - 1);
    }

    if (!this.confirmedAway && this.awayStreak >= FRAMES_TO_CONFIRM_AWAY) {
      this.confirmedAway = true;
    }
    if (this.confirmedAway && this.onStreak >= FRAMES_TO_CONFIRM_ON_SCREEN) {
      this.confirmedAway = false;
      this.awayStreak = 0;
    }

    const confidence = clamp(0.68 + deviation * 0.12, 0.68, 0.97);

    return {
      offScreen: this.confirmedAway,
      confidence,
      deviation,
      calibrated: this.isCalibrated,
    };
  }

  private fallbackDeviation(features: GazeFeatures): number {
    const [leftIx, leftIy, rightIx, rightIy, yaw, pitch, ...looks] = features.vector;
    const horizontal = Math.max(Math.abs(leftIx), Math.abs(rightIx));
    const vertical = Math.max(Math.abs(leftIy), Math.abs(rightIy));
    const head = Math.sqrt(yaw * yaw + pitch * pitch);

    const lookDown = Math.max(looks[0] ?? 0, looks[1] ?? 0);
    const lookSide = Math.max(
      looks[2] ?? 0,
      looks[3] ?? 0,
      looks[4] ?? 0,
      looks[5] ?? 0
    );
    const lookUp = Math.max(looks[6] ?? 0, looks[7] ?? 0);

    // Horizontal and head-turn are the strongest signals of truly looking away.
    // Vertical (down/up) gets lower weight — reading text lower on screen is normal.
    return (
      horizontal * 1.6 +
      vertical * 0.6 +
      head * 2.0 +
      lookDown * 0.8 +
      lookSide * 1.4 +
      lookUp * 0.9
    );
  }
}

export const gazeTracker = new GazeTracker();

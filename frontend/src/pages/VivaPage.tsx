import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  endVivaSession,
  SkillQuestions,
  startVivaSession,
  VivaStartResponse,
} from '../api/client';
import { CameraPanel } from '../components/CameraPanel';
import { ConsentModal } from '../components/ConsentModal';
import {
  IntegrityNotification,
  IntegrityNotifications,
  messageForFlag,
} from '../components/IntegrityNotifications';
import { QuestionCard } from '../components/QuestionCard';
import { ExamNavigation } from '../components/ExamNavigation';
import { compareFaceLandmarks, gazeTracker, useFaceLandmarker } from '../hooks/useFaceLandmarker';
import { useProctoring } from '../hooks/useProctoring';
import { useFullscreenProctoring } from '../hooks/useFullscreenProctoring';
import { useCameraIntegrity } from '../hooks/useCameraIntegrity';
import { useObjectDetector } from '../hooks/useObjectDetector';
import type { ProctoringConfig } from '../api/client';

type Phase = 'consent' | 'setup' | 'identity' | 'interview' | 'done';

export function VivaPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number>(0);
  const referenceLandmarksRef = useRef<{ x: number; y: number }[] | null>(null);
  const identitySamplesRef = useRef<number[]>([]);

  const [phase, setPhase] = useState<Phase>('consent');
  const [session, setSession] = useState<VivaStartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flatQuestions, setFlatQuestions] = useState<
    { skill: SkillQuestions; qIndex: number }[]
  >([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<string[]>([]);
  const [skippedQuestions, setSkippedQuestions] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [finalResult, setFinalResult] = useState<unknown>(null);
  const [notifications, setNotifications] = useState<IntegrityNotification[]>([]);
  const [identityStatus, setIdentityStatus] = useState<'pending' | 'verified' | 'failed'>(
    'pending'
  );
  const [cameraOn, setCameraOn] = useState(false);
  const [monitoring, setMonitoring] = useState(false);

  const trustedDeviceIdRef = useRef<string | null>(null);

  const { ready: modelReady, error: modelError, detect } = useFaceLandmarker(videoRef);
  const { detectSuspiciousObjects } = useObjectDetector(videoRef);

  const addNotification = useCallback((type: string) => {
    if (type === 'snapshot_captured') return;

    setNotifications((prev) => {
      const recentSame = prev.find(
        (n) => n.type === type && Date.now() - Number(n.id.split('-')[1] || 0) < 4000
      );
      if (recentSame) return prev;

      const entry: IntegrityNotification = {
        id: `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        type,
        message: messageForFlag(type),
        time: new Date().toLocaleTimeString(),
      };
      return [...prev, entry];
    });
  }, []);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const dismissAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const { emitOnce, processFaceState, emitDeviceStrike } = useProctoring({
    sessionId: session?.session_id ?? null,
    enabled: monitoring,
    config: (session?.config as ProctoringConfig | undefined) ?? null,
    onFlag: addNotification,
  });

  const handleDeviceFlag = useCallback(
    (eventType: string, confidence = 0.9) => {
      void emitDeviceStrike(eventType, confidence);
    },
    [emitDeviceStrike]
  );

  const { registerStream } = useCameraIntegrity({
    streamRef,
    enabled: monitoring,
    onFlag: handleDeviceFlag,
  });

  const handleFullscreenExit = useCallback(() => {
    void emitOnce('fullscreen_exited', { confidence: 1.0 });
  }, [emitOnce]);

  useFullscreenProctoring({ enabled: monitoring, onExit: handleFullscreenExit });

  const startCamera = useCallback(async () => {
    if (streamRef.current) {
      setCameraOn(true);
      return;
    }

    try {
      const videoConstraints: MediaTrackConstraints = {
        width: { ideal: 640, max: 640 },
        height: { ideal: 480, max: 480 },
        frameRate: { ideal: 24, max: 30 },
      };

      if (trustedDeviceIdRef.current) {
        videoConstraints.deviceId = { exact: trustedDeviceIdRef.current };
      } else {
        videoConstraints.facingMode = 'user';
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
        audio: false,
      });

      const track = stream.getVideoTracks()[0];
      const deviceId = track?.getSettings().deviceId;
      if (deviceId) {
        trustedDeviceIdRef.current = deviceId;
      }

      streamRef.current = stream;
      const video = videoRef.current;
      if (video && video.srcObject !== stream) {
        video.srcObject = stream;
        video.setAttribute('playsinline', 'true');
        await video.play();
      }
      registerStream(stream);
      setCameraOn(true);
    } catch {
      setError('Camera access denied. This will be flagged as an integrity issue.');
      setCameraOn(false);
    }
  }, [registerStream]);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOn(false);
  }, []);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!analysisId) return;
    startVivaSession(analysisId)
      .then((data) => {
        setSession(data);
        const flat: { skill: SkillQuestions; qIndex: number }[] = [];
        for (const skill of data.questions) {
          for (let i = 0; i < skill.questions.length; i++) {
            flat.push({ skill, qIndex: i });
          }
        }
        setFlatQuestions(flat);
        setAnswers(new Array(flat.length).fill(''));
      })
      .catch((e) => setError(e.message));
  }, [analysisId]);

  const runIdentityCheck = useCallback(async () => {
    if (!modelReady) return;

    gazeTracker.reset();

    const samples: number[] = [];
    for (let i = 0; i < 12; i++) {
      await new Promise((r) => setTimeout(r, 300));
      const result = detect();
      if (result.gazeFeatures) {
        gazeTracker.addCalibrationSample(result.gazeFeatures);
      }
      if (result.landmarks) {
        if (!referenceLandmarksRef.current) {
          referenceLandmarksRef.current = result.landmarks;
        } else {
          const sim = compareFaceLandmarks(referenceLandmarksRef.current, result.landmarks);
          samples.push(sim);
        }
      }
    }

    gazeTracker.finalizeCalibration();

    identitySamplesRef.current = samples;
    const avgSim = samples.length
      ? samples.reduce((a, b) => a + b, 0) / samples.length
      : 0;

    if (avgSim >= 0.55 || (samples.length >= 2 && avgSim >= 0.4)) {
      setIdentityStatus('verified');
      await emitOnce('id_verified', { confidence: avgSim });
    } else {
      setIdentityStatus('failed');
      await emitOnce('id_failed', { confidence: avgSim });
    }
  }, [modelReady, detect, emitOnce]);

  const beginInterview = useCallback(async () => {
    await emitOnce('interview_started');
    setMonitoring(true);
    setPhase('interview');
  }, [emitOnce]);

  useEffect(() => {
    if (phase !== 'identity' || !cameraOn || !modelReady) return;

    const timer = setTimeout(async () => {
      await runIdentityCheck();
      setPhase('setup');
      setTimeout(() => beginInterview(), 1000);
    }, 2000);

    return () => clearTimeout(timer);
  }, [phase, cameraOn, modelReady, runIdentityCheck, beginInterview]);

  useEffect(() => {
    if (!monitoring) return;

    let lastFrame = 0;
    const loop = (now: number) => {
      if (now - lastFrame >= 100) {
        lastFrame = now;
        const result = detect();
        processFaceState(result.faceCount, result.gazeOffScreen, result.gazeConfidence);

        const suspicious = detectSuspiciousObjects();
        if (suspicious.length > 0) {
          const top = suspicious.reduce((a, b) => (a.score > b.score ? a : b));
          void emitDeviceStrike('secondary_device_detected', top.score);
        }
      }
      animFrameRef.current = requestAnimationFrame(loop);
    };
    animFrameRef.current = requestAnimationFrame(loop);

    return () => cancelAnimationFrame(animFrameRef.current);
  }, [monitoring, detect, processFaceState, detectSuspiciousObjects, emitDeviceStrike]);

  const handleConsent = async () => {
    setPhase('setup');
    await startCamera();
    setPhase('identity');
  };

  const handlePrevious = () => {
    if (currentQ > 0) {
      setCurrentQ((q) => q - 1);
    }
  };

  const handleNext = () => {
    if (currentQ < flatQuestions.length - 1) {
      setCurrentQ((q) => q + 1);
    }
  };

  const handleSkip = () => {
    if (currentQ < flatQuestions.length - 1) {
      setSkippedQuestions((prev) => new Set(prev).add(currentQ));
      setCurrentQ((q) => q + 1);
    }
  };

  const handleGoToQuestion = (index: number) => {
    if (index >= 0 && index < flatQuestions.length) {
      setCurrentQ(index);
    }
  };

  const handleSubmitExam = async () => {
    const unanswered = answers.filter((a) => !a.trim()).length;
    const confirmMsg =
      unanswered > 0
        ? `You have ${unanswered} unanswered question(s). Submit the exam anyway?`
        : 'Submit your exam? You cannot change answers after submission.';
    if (!window.confirm(confirmMsg)) return;
    await handleFinish();
  };

  const handleFinish = async () => {
    if (submitting) return;
    setSubmitting(true);
    setMonitoring(false);
    stopCamera();
    if (session) {
      try {
        const answerPayload = flatQuestions.map((item, idx) => {
          const q = item.skill.questions[item.qIndex];
          return {
            skill_name: item.skill.skill_name,
            question_type: q.question_type,
            question_text: q.text,
            reference: q.reference ?? null,
            answer_text: answers[idx] ?? '',
          };
        });
        const result = await endVivaSession(session.session_id, answerPayload);
        setFinalResult(result);
        setPhase('done');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to end session');
        setSubmitting(false);
        setMonitoring(true);
        await startCamera();
      }
    } else {
      setSubmitting(false);
    }
  };

  const handlePaste = () => {
    emitOnce('paste_attempted', { confidence: 1.0 });
  };

  if (error && !session) {
    return (
      <div className="container">
        <div className="error">{error}</div>
        <button className="secondary" onClick={() => navigate('/')}>
          Back
        </button>
      </div>
    );
  }

  if (phase === 'done' && finalResult) {
    const grading = (finalResult as { viva_grading_report?: {
      overall_viva_score: number;
      overall_exam_score: number;
      narrative: string;
      answer_grades: { skill_name: string; score: number; grade: string; feedback: string }[];
    } }).viva_grading_report;
    const proctoring = (finalResult as { proctoring_report?: { integrity_score: number; risk_level: string } }).proctoring_report;

    return (
      <div className="container">
        <h1>Viva Complete</h1>
        {grading && (
          <div className="card">
            <h3>Exam Scores</h3>
            <p><strong>Answer score:</strong> {(grading.overall_viva_score * 100).toFixed(0)}%</p>
            <p><strong>Integrity score:</strong> {((proctoring?.integrity_score ?? 0) * 100).toFixed(0)}%</p>
            <p><strong>Combined exam score:</strong> {(grading.overall_exam_score * 100).toFixed(0)}%</p>
            <p style={{ fontSize: 14, color: '#555' }}>{grading.narrative}</p>
            <h4>Per-answer grades</h4>
            <ul style={{ fontSize: 14 }}>
              {grading.answer_grades.map((g, i) => (
                <li key={i}>
                  <strong>{g.skill_name}</strong> — {g.grade} ({(g.score * 100).toFixed(0)}%): {g.feedback}
                </li>
              ))}
            </ul>
          </div>
        )}
        <button className="secondary" onClick={() => navigate('/')}>
          Back to Home
        </button>
      </div>
    );
  }

  const current = flatQuestions[currentQ];
  const uniqueSkills = session
    ? session.questions.map((s) => s.skill_name)
    : [];
  const currentTechIndex = current
    ? uniqueSkills.indexOf(current.skill.skill_name)
    : 0;

  return (
    <div className="container">
      <h1>Proctored Live Viva</h1>
      {session && <p>Session: {session.session_id}</p>}
      {modelError && <div className="error">Face model: {modelError}</div>}
      {error && <div className="error">{error}</div>}

      {phase === 'consent' && (
        <ConsentModal onAccept={handleConsent} onDecline={() => navigate('/')} />
      )}

      <IntegrityNotifications
        notifications={notifications}
        onDismiss={dismissNotification}
        onDismissAll={dismissAllNotifications}
      />

      {phase === 'interview' && monitoring && (
        <div className="proctoring-banner compact">
          Proctored session — integrity events are monitored.
        </div>
      )}

      <div className="viva-layout">
        <CameraPanel
          videoRef={videoRef}
          cameraOn={cameraOn}
          modelReady={modelReady}
          identityStatus={identityStatus}
          monitoring={monitoring}
        />

        {phase === 'identity' && (
          <div className="card">
            <h3>Identity &amp; Gaze Calibration</h3>
            <p>
              Look directly at the center of your screen. We are verifying your identity and
              calibrating eye-tracking to your neutral gaze.
            </p>
          </div>
        )}

        {phase === 'interview' && current && (
          <div className="exam-panel">
            <QuestionCard
              skill={current.skill}
              questionIndex={current.qIndex}
              answer={answers[currentQ]}
              onAnswerChange={(v) => {
                const next = [...answers];
                next[currentQ] = v;
                setAnswers(next);
                if (v.trim()) {
                  setSkippedQuestions((prev) => {
                    if (!prev.has(currentQ)) return prev;
                    const updated = new Set(prev);
                    updated.delete(currentQ);
                    return updated;
                  });
                }
              }}
              onPaste={handlePaste}
              totalQuestions={flatQuestions.length}
              currentGlobalIndex={currentQ}
              techIndex={currentTechIndex}
              techTotal={uniqueSkills.length}
            />
            <ExamNavigation
              currentIndex={currentQ}
              total={flatQuestions.length}
              answers={answers}
              skipped={skippedQuestions}
              submitting={submitting}
              onPrevious={handlePrevious}
              onSkip={handleSkip}
              onNext={handleNext}
              onGoTo={handleGoToQuestion}
              onSubmit={handleSubmitExam}
            />
          </div>
        )}

        {phase === 'setup' && (
          <div className="card">
            <h3>Preparing session...</h3>
          </div>
        )}
      </div>
    </div>
  );
}

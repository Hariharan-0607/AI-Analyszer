const API_BASE = '';

export interface SuggestedSkill {
  skill_id: string;
  skill_name: string;
  confidence: number;
  rationale: string;
}

export interface Question {
  question_type: string;
  text: string;
  reference?: string | null;
}

export interface SkillQuestions {
  skill_id: string;
  skill_name: string;
  questions: Question[];
}

export interface AnalyzeResponse {
  analysis_id: string;
  project_title: string;
  suggested_skills: SuggestedSkill[];
  evaluation_report: {
    skills: SkillQuestions[];
    summary: Record<string, unknown>;
  };
  metadata: {
    files_analyzed: number;
    extraction_time_ms: number;
    model_tokens_used: number;
  };
  processing_time_ms: number;
  saved_files?: Record<string, string>;
}

export interface ProctoringConfig {
  gaze_low_sec: number;
  gaze_medium_sec: number;
  face_not_detected_sec: number;
  connection_timeout_sec: number;
  heartbeat_interval_sec: number;
}

export interface VivaStartResponse {
  session_id: string;
  analysis_id: string;
  questions: SkillQuestions[];
  config: ProctoringConfig;
}

export interface ProctoringEventPayload {
  session_id: string;
  event_type: string;
  timestamp: string;
  duration_ms?: number;
  confidence?: number;
}

export async function analyzeSubmission(formData: FormData): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze-submission`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

export async function startVivaSession(analysisId: string): Promise<VivaStartResponse> {
  const res = await fetch(`${API_BASE}/viva-session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

export async function postVivaEvent(event: ProctoringEventPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/viva-session/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
}

export interface VivaAnswerPayload {
  skill_name: string;
  question_type: string;
  question_text: string;
  reference?: string | null;
  answer_text: string;
}

export async function endVivaSession(
  sessionId: string,
  answers: VivaAnswerPayload[] = []
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/viva-session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, answers }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

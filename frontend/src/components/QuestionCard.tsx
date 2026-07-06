import { SkillQuestions } from '../api/client';

interface QuestionCardProps {
  skill: SkillQuestions;
  questionIndex: number;
  answer: string;
  onAnswerChange: (value: string) => void;
  onPaste: () => void;
  totalQuestions: number;
  currentGlobalIndex: number;
  techIndex: number;
  techTotal: number;
}

export function QuestionCard({
  skill,
  questionIndex,
  answer,
  onAnswerChange,
  onPaste,
  totalQuestions,
  currentGlobalIndex,
  techIndex,
  techTotal,
}: QuestionCardProps) {
  const q = skill.questions[questionIndex];

  return (
    <div className="card">
      <div className="progress">
        Technology {techIndex + 1} of {techTotal}: {skill.skill_name} — Question{' '}
        {currentGlobalIndex + 1} of {totalQuestions}
      </div>
      <h3>
        {skill.skill_name}{' '}
        <span className="badge ok">{q.question_type.replace('_', ' ')}</span>
      </h3>
      <p>{q.text}</p>
      {q.reference && (
        <p style={{ fontSize: 13, color: '#666' }}>
          Reference: <code>{q.reference}</code>
        </p>
      )}
      <label htmlFor="answer">Your answer (spoken + typed notes)</label>
      <textarea
        id="answer"
        className="answer-textarea"
        value={answer}
        onChange={(e) => onAnswerChange(e.target.value)}
        onPaste={(e) => {
          e.preventDefault();
          onPaste();
        }}
        placeholder="Type your answer here or speak your answer on camera..."
      />
    </div>
  );
}

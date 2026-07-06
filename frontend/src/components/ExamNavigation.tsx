interface ExamNavigationProps {
  currentIndex: number;
  total: number;
  answers: string[];
  skipped: Set<number>;
  submitting: boolean;
  onPrevious: () => void;
  onSkip: () => void;
  onNext: () => void;
  onGoTo: (index: number) => void;
  onSubmit: () => void;
}

export function ExamNavigation({
  currentIndex,
  total,
  answers,
  skipped,
  submitting,
  onPrevious,
  onSkip,
  onNext,
  onGoTo,
  onSubmit,
}: ExamNavigationProps) {
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === total - 1;
  const answeredCount = answers.filter((a) => a.trim().length > 0).length;

  return (
    <div className="exam-navigation">
      <div className="exam-progress-summary">
        Question {currentIndex + 1} of {total} · {answeredCount} answered · {skipped.size} skipped
      </div>

      <div className="exam-question-strip" role="tablist" aria-label="Question navigation">
        {Array.from({ length: total }, (_, i) => {
          const answered = answers[i]?.trim().length > 0;
          const isSkipped = skipped.has(i);
          const isCurrent = i === currentIndex;
          let stateClass = 'unanswered';
          if (isCurrent) stateClass = 'current';
          else if (answered) stateClass = 'answered';
          else if (isSkipped) stateClass = 'skipped';

          return (
            <button
              key={i}
              type="button"
              className={`exam-question-pill ${stateClass}`}
              onClick={() => onGoTo(i)}
              aria-label={`Go to question ${i + 1}`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      <div className="exam-nav-actions">
        <button type="button" className="secondary" onClick={onPrevious} disabled={isFirst || submitting}>
          Previous
        </button>
        <button type="button" className="secondary" onClick={onSkip} disabled={isLast || submitting}>
          Skip
        </button>
        {!isLast && (
          <button type="button" className="primary" onClick={onNext} disabled={submitting}>
            Next
          </button>
        )}
        {isLast && (
          <button type="button" className="primary submit-exam" onClick={onSubmit} disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Exam'}
          </button>
        )}
      </div>
    </div>
  );
}

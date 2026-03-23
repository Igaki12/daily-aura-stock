type TutorialStep = {
  label: string;
  title: string;
  body: string;
  hint: string;
};

type TutorialOverlayProps = {
  isOpen: boolean;
  currentStep: number;
  steps: TutorialStep[];
  onClose: () => void;
  onNext: () => void;
  onPrev: () => void;
};

export function TutorialOverlay({
  isOpen,
  currentStep,
  steps,
  onClose,
  onNext,
  onPrev,
}: TutorialOverlayProps) {
  if (!isOpen) {
    return null;
  }

  const step = steps[currentStep];
  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;

  return (
    <div className="tutorial-backdrop" role="dialog" aria-modal="true">
      <div className="tutorial-card">
        <div className="tutorial-head">
          <div>
            <p className="section-eyebrow tutorial-label">{step.label}</p>
            <h2>{step.title}</h2>
          </div>
          <button type="button" className="tutorial-close" onClick={onClose} aria-label="チュートリアルを閉じる">
            ×
          </button>
        </div>

        <div className="tutorial-progress" aria-label="チュートリアル進行状況">
          {steps.map((item, index) => (
            <span
              key={item.label}
              className={[
                "tutorial-progress-dot",
                index === currentStep ? "active" : "",
                index < currentStep ? "done" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            />
          ))}
        </div>

        <div key={step.label} className="tutorial-content">
          <p className="tutorial-body">{step.body}</p>
          <p className="tutorial-hint">{step.hint}</p>
        </div>

        <div className="tutorial-actions">
          <button type="button" className="ghost" onClick={onPrev} disabled={isFirst}>
            前へ
          </button>
          <div className="tutorial-actions-right">
            <button type="button" className="ghost" onClick={onClose}>
              閉じる
            </button>
            <button type="button" className="primary" onClick={isLast ? onClose : onNext}>
              {isLast ? "完了" : "次へ"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

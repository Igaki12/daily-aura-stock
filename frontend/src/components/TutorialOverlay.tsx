import { useEffect, useState } from "react";

type TutorialStep = {
  label: string;
  title: string;
  body: string;
  hint: string;
  targetId: string;
};

type TutorialOverlayProps = {
  isOpen: boolean;
  currentStep: number;
  steps: TutorialStep[];
  onClose: () => void;
  onNext: () => void;
  onPrev: () => void;
};

type TargetLayout = {
  top: number;
  left: number;
  width: number;
  height: number;
  side: "left" | "right";
};

export function TutorialOverlay({
  isOpen,
  currentStep,
  steps,
  onClose,
  onNext,
  onPrev,
}: TutorialOverlayProps) {
  const [targetLayout, setTargetLayout] = useState<TargetLayout | null>(null);

  const step = steps[currentStep];

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let timeoutId = 0;

    const measureLayout = () => {
      const target = document.querySelector<HTMLElement>(
        `[data-tutorial-id="${step.targetId}"]`,
      );
      if (!target) {
        setTargetLayout(null);
        return;
      }

      const rect = target.getBoundingClientRect();
      const isDesktop = window.innerWidth > 960;
      const side = rect.left + rect.width / 2 < window.innerWidth / 2 ? "right" : "left";
      setTargetLayout({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        side,
      });
    };

    const updateLayout = () => {
      const target = document.querySelector<HTMLElement>(
        `[data-tutorial-id="${step.targetId}"]`,
      );
      if (!target) {
        setTargetLayout(null);
        return;
      }

      const isDesktop = window.innerWidth > 960;
      if (isDesktop) {
        const rect = target.getBoundingClientRect();
        const centeredTop =
          window.scrollY + rect.top - Math.max(24, window.innerHeight / 2 - rect.height / 2);
        window.scrollTo({
          top: Math.max(0, centeredTop),
          behavior: "smooth",
        });
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(measureLayout, 260);
      } else {
        measureLayout();
      }
    };

    updateLayout();
    window.addEventListener("resize", updateLayout);
    return () => {
      window.clearTimeout(timeoutId);
      window.removeEventListener("resize", updateLayout);
    };
  }, [isOpen, step.targetId]);

  if (!isOpen) {
    return null;
  }

  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;
  const isDesktop = typeof window !== "undefined" ? window.innerWidth > 960 : false;
  const panelClassName = [
    "tutorial-panel",
    targetLayout?.side === "left" ? "side-left" : "side-right",
    isDesktop && targetLayout ? "desktop" : "centered",
  ]
    .filter(Boolean)
    .join(" ");

  const panelStyle =
    isDesktop && targetLayout
      ? {
          top: `${Math.max(24, Math.min(targetLayout.top, window.innerHeight - 520))}px`,
          left:
            targetLayout.side === "right"
              ? `${Math.min(targetLayout.left + targetLayout.width + 24, window.innerWidth - 456)}px`
              : `${Math.max(24, targetLayout.left - 440)}px`,
        }
      : undefined;

  return (
    <>
      <div className="tutorial-backdrop" />
      <div className={panelClassName} style={panelStyle} role="dialog" aria-modal="true">
        <div key={step.label} className="tutorial-card">
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

        <div className="tutorial-content">
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
    </>
  );
}

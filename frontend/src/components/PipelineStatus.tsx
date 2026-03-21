import type { PipelineState } from "../types";

const STEPS: Array<{ key: PipelineState; label: string }> = [
  { key: "ready", label: "準備完了" },
  { key: "summarizing", label: "要約" },
  { key: "embedding", label: "ベクトル化" },
  { key: "ranking", label: "類似検索" },
  { key: "predicted", label: "予想表示" },
];

type PipelineStatusProps = {
  state: PipelineState;
};

export function PipelineStatus({ state }: PipelineStatusProps) {
  const activeIndex = STEPS.findIndex((step) => step.key === state);

  return (
    <div className="pipeline-status">
      {STEPS.map((step, index) => (
        <div
          key={step.key}
          className={[
            "pipeline-step",
            index <= activeIndex ? "active" : "",
            state === "error" ? "error" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span>{step.label}</span>
        </div>
      ))}
    </div>
  );
}

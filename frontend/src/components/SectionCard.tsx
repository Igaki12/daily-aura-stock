import { useState } from "react";
import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  eyebrow?: string;
  summary: ReactNode;
  details: ReactNode;
  tutorialId?: string;
  className?: string;
};

export function SectionCard({
  title,
  eyebrow,
  summary,
  details,
  tutorialId,
  className,
}: SectionCardProps) {
  const [tab, setTab] = useState<"summary" | "details">("summary");

  return (
    <section
      className={["section-card", className].filter(Boolean).join(" ")}
      data-tutorial-id={tutorialId}
    >
      <div className="section-head">
        <div>
          {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        <div className="tab-switch">
          <button
            type="button"
            className={tab === "summary" ? "active" : ""}
            onClick={() => setTab("summary")}
          >
            概要
          </button>
          <button
            type="button"
            className={tab === "details" ? "active" : ""}
            onClick={() => setTab("details")}
          >
            詳細
          </button>
        </div>
      </div>
      <div className="section-body">{tab === "summary" ? summary : details}</div>
    </section>
  );
}

import { useState } from "react";
import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  eyebrow?: string;
  summary: ReactNode;
  details: ReactNode;
};

export function SectionCard({
  title,
  eyebrow,
  summary,
  details,
}: SectionCardProps) {
  const [tab, setTab] = useState<"summary" | "details">("summary");

  return (
    <section className="section-card">
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

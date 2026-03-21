import { useEffect, useMemo, useState } from "react";
import { ApiKeyModal } from "./components/ApiKeyModal";
import { PipelineStatus } from "./components/PipelineStatus";
import { SectionCard } from "./components/SectionCard";
import { embedSummary, generateSummary } from "./lib/gemini";
import { formatDateLabel, formatNumber, formatPercent } from "./lib/format";
import { cosineSimilarity, summarizeVector } from "./lib/vector";
import type {
  ActivityLog,
  ApiKeyState,
  DailyRecord,
  DemoData,
  PipelineState,
  SimilarityResult,
} from "./types";

const STORAGE_KEY = "daily-aura-stock-gemini-api-key";
const DATA_PATH = "./assets/data/demo-data.json";

function nowLabel(): string {
  return new Date().toLocaleString("ja-JP");
}

export function App() {
  const [demoData, setDemoData] = useState<DemoData | null>(null);
  const [apiKeyState, setApiKeyState] = useState<ApiKeyState>({ value: "" });
  const [isModalOpen, setIsModalOpen] = useState(true);
  const [pipelineState, setPipelineState] = useState<PipelineState>("idle");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [newsInput, setNewsInput] = useState("");
  const [summaryInput, setSummaryInput] = useState("");
  const [vectorInput, setVectorInput] = useState<number[]>([]);
  const [ranking, setRanking] = useState<SimilarityResult[]>([]);
  const [logs, setLogs] = useState<ActivityLog[]>([]);

  useEffect(() => {
    void fetch(DATA_PATH)
      .then((response) => response.json() as Promise<DemoData>)
      .then((payload) => {
        setDemoData(payload);
        const first = payload.records[0];
        if (first) {
          hydrateFromRecord(first);
        }
        setPipelineState("ready");
      })
      .catch((error) => {
        appendLog("error", `静的データ読込に失敗: ${String(error)}`);
        setPipelineState("error");
      });

    const savedKey = window.localStorage.getItem(STORAGE_KEY) ?? "";
    if (savedKey) {
      setApiKeyState({ value: savedKey, savedAt: nowLabel() });
      setIsModalOpen(false);
    }
  }, []);

  function appendLog(level: ActivityLog["level"], message: string) {
    setLogs((current) => [{ timestamp: nowLabel(), level, message }, ...current].slice(0, 12));
  }

  function hydrateFromRecord(record: DailyRecord) {
    setSelectedDate(record.marketEffectiveDateJst);
    setNewsInput(record.sampleHeadlines.join("\n"));
    setSummaryInput(record.summary);
    setVectorInput(record.embedding);
  }

  const selectedRecord = useMemo(
    () =>
      demoData?.records.find(
        (record) => record.marketEffectiveDateJst === selectedDate,
      ) ?? null,
    [demoData, selectedDate],
  );

  const predicted = useMemo(() => {
    if (!ranking.length || !demoData) {
      return null;
    }

    const top = ranking.slice(0, 3);
    let weightSum = 0;
    let n225 = 0;
    let topix = 0;

    for (const item of top) {
      const record = demoData.records.find(
        (candidate) =>
          candidate.marketEffectiveDateJst === item.marketEffectiveDateJst,
      );
      if (!record) {
        continue;
      }
      const weight = Math.max(item.score, 0.0001);
      weightSum += weight;
      n225 += (record.market.n225PrevCloseChangePct ?? 0) * weight;
      topix += (record.market.topixProxyPrevCloseChangePct ?? 0) * weight;
    }

    if (!weightSum) {
      return null;
    }

    return {
      n225: n225 / weightSum,
      topix: topix / weightSum,
      references: top,
    };
  }, [demoData, ranking]);

  useEffect(() => {
    if (!demoData || !vectorInput.length) {
      return;
    }
    const nextRanking = demoData.records
      .map((record) => {
        const score = cosineSimilarity(vectorInput, record.embedding);
        return {
          marketEffectiveDateJst: record.marketEffectiveDateJst,
          score,
          distance: 1 - score,
        };
      })
      .sort((left, right) => right.score - left.score)
      .slice(0, 6);
    setRanking(nextRanking);
    setPipelineState("predicted");
  }, [demoData, vectorInput]);

  async function handleGenerateSummary() {
    if (!apiKeyState.value) {
      appendLog("warn", "API キー未設定のため要約を実行できません。");
      return;
    }
    try {
      setPipelineState("summarizing");
      appendLog("info", "Gemini で日次サマリーを生成します。");
      const summary = await generateSummary(apiKeyState.value, newsInput);
      setSummaryInput(summary);
      appendLog("info", "サマリー生成が完了しました。");
      setPipelineState("ready");
    } catch (error) {
      appendLog("error", `サマリー生成に失敗: ${String(error)}`);
      setPipelineState("error");
    }
  }

  async function handleGenerateEmbedding() {
    if (!apiKeyState.value) {
      appendLog("warn", "API キー未設定のため埋め込みを実行できません。");
      return;
    }
    try {
      setPipelineState("embedding");
      appendLog("info", "Gemini で 3072 次元埋め込みを生成します。");
      const values = await embedSummary(apiKeyState.value, summaryInput);
      setVectorInput(values);
      appendLog("info", "埋め込み生成が完了しました。");
      setPipelineState("ranking");
    } catch (error) {
      appendLog("error", `埋め込み生成に失敗: ${String(error)}`);
      setPipelineState("error");
    }
  }

  function handleSaveApiKey(value: string) {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, value);
      setApiKeyState({ value, savedAt: nowLabel() });
      appendLog("info", "Gemini API キーを localStorage に保存しました。");
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
      setApiKeyState({ value: "" });
      appendLog("warn", "Gemini API キーを保存せずに続行します。");
    }
    setIsModalOpen(false);
  }

  function handleDeleteApiKey() {
    window.localStorage.removeItem(STORAGE_KEY);
    setApiKeyState({ value: "" });
    appendLog("warn", "Gemini API キーを削除しました。");
  }

  const vectorSummary = summarizeVector(vectorInput);

  return (
    <div className="app-shell">
      <ApiKeyModal
        isOpen={isModalOpen}
        initialValue={apiKeyState.value}
        onSave={handleSaveApiKey}
        onClose={() => setIsModalOpen(false)}
      />

      <header className="hero">
        <div>
          <p className="kicker">DailyAuraStock / GitHub Pages Demo</p>
          <h1>ニュース日次 Aura から株価の参考変動を読むダッシュボード</h1>
          <p className="hero-copy">
            1営業日分のニュースを要約し、3072 次元埋め込みで類似日を探し、
            類似日の当日騰落率を参考表示します。Pages 版は静的デモであり、
            API キーはブラウザ上でのみ扱います。
          </p>
        </div>
        <div className="hero-aside">
          <div className="stat-tile">
            <span>対象営業日</span>
            <strong>{demoData?.records.length ?? 0} days</strong>
          </div>
          <div className="stat-tile">
            <span>ベクトル次元</span>
            <strong>3072</strong>
          </div>
          <div className="stat-tile">
            <span>現在状態</span>
            <strong>{pipelineState}</strong>
          </div>
        </div>
      </header>

      <PipelineStatus state={pipelineState} />

      <main className="dashboard-grid">
        <SectionCard
          title="API 管理"
          eyebrow="Step 0"
          summary={
            <div className="stack">
              <p>
                Gemini API キーはページ表示後に入力し、`localStorage` のみに保存します。
                ブラウザ実行のため秘匿はできません。
              </p>
              <div className="key-row">
                <span>{apiKeyState.value ? "保存済み" : "未設定"}</span>
                <button type="button" className="ghost" onClick={() => setIsModalOpen(true)}>
                  {apiKeyState.value ? "再入力" : "入力"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={handleDeleteApiKey}
                  disabled={!apiKeyState.value}
                >
                  削除
                </button>
              </div>
            </div>
          }
          details={
            <ul className="plain-list">
              <li>API キーは HTML に埋め込まず、環境変数も使いません。</li>
              <li>保存先は `localStorage` のみです。</li>
              <li>共用端末では保存しないでください。</li>
              <li>デモ用途では利用制限付きキーを推奨します。</li>
            </ul>
          }
        />

        <SectionCard
          title="ニュース入力"
          eyebrow="Step 1"
          summary={
            <div className="stack">
              <label className="field">
                <span>ニュース記事または見出し集合</span>
                <textarea
                  rows={10}
                  value={newsInput}
                  onChange={(event) => setNewsInput(event.target.value)}
                />
              </label>
              <div className="button-row">
                {demoData?.records.map((record) => (
                  <button
                    key={record.marketEffectiveDateJst}
                    type="button"
                    className={
                      record.marketEffectiveDateJst === selectedDate ? "pill active" : "pill"
                    }
                    onClick={() => {
                      hydrateFromRecord(record);
                      appendLog("info", `${record.marketEffectiveDateJst} の保存済み日次データを読み込みました。`);
                    }}
                  >
                    {formatDateLabel(record.marketEffectiveDateJst)}
                  </button>
                ))}
              </div>
            </div>
          }
          details={
            <div className="stack">
              <p>自由入力中心ですが、保存済み 6 営業日サンプルも即時読込できます。</p>
              <p>現在の文字数: {newsInput.length}</p>
              {selectedRecord ? (
                <ul className="plain-list">
                  {selectedRecord.sampleHeadlines.map((headline) => (
                    <li key={headline}>{headline}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          }
        />

        <SectionCard
          title="日次サマリー"
          eyebrow="Step 2"
          summary={
            <div className="stack">
              <label className="field">
                <span>サマリー</span>
                <textarea
                  rows={10}
                  value={summaryInput}
                  onChange={(event) => setSummaryInput(event.target.value)}
                />
              </label>
              <div className="button-row">
                <button type="button" className="primary" onClick={handleGenerateSummary} disabled={!apiKeyState.value}>
                  Gemini で再要約
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    if (selectedRecord) {
                      setSummaryInput(selectedRecord.summary);
                      appendLog("info", "保存済みサマリーを復元しました。");
                    }
                  }}
                >
                  保存済みサマリーを使う
                </button>
              </div>
            </div>
          }
          details={
            <div className="stack">
              <p>現在の文字数: {summaryInput.length}</p>
              <p>保存済みデータ選択時は API を使わず、既存サマリーをそのまま利用できます。</p>
            </div>
          }
        />

        <SectionCard
          title="ベクトル"
          eyebrow="Step 3"
          summary={
            <div className="stack">
              <div className="metric-grid">
                <div className="metric">
                  <span>次元数</span>
                  <strong>{vectorSummary.length}</strong>
                </div>
                <div className="metric">
                  <span>最小値</span>
                  <strong>{vectorSummary.min.toFixed(4)}</strong>
                </div>
                <div className="metric">
                  <span>最大値</span>
                  <strong>{vectorSummary.max.toFixed(4)}</strong>
                </div>
                <div className="metric">
                  <span>平均値</span>
                  <strong>{vectorSummary.mean.toFixed(4)}</strong>
                </div>
              </div>
              <div className="button-row">
                <button type="button" className="primary" onClick={handleGenerateEmbedding} disabled={!apiKeyState.value || !summaryInput.trim()}>
                  Gemini でベクトル化
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    if (selectedRecord) {
                      setVectorInput(selectedRecord.embedding);
                      appendLog("info", "保存済み埋め込みベクトルを復元しました。");
                    }
                  }}
                >
                  保存済みベクトルを使う
                </button>
              </div>
            </div>
          }
          details={
            <div className="stack">
              <p>先頭 16 要素のプレビュー</p>
              <div className="vector-strip">
                {vectorSummary.head.map((value, index) => (
                  <div
                    key={`${index}-${value}`}
                    className="vector-bar"
                    style={{
                      height: `${Math.min(Math.abs(value) * 800, 100)}%`,
                      opacity: Math.min(Math.abs(value) * 20, 1),
                    }}
                    title={`${index}: ${value.toFixed(6)}`}
                  />
                ))}
              </div>
            </div>
          }
        />

        <SectionCard
          title="ベクトル類似度ランキング"
          eyebrow="Step 4"
          summary={
            <div className="stack">
              {ranking.map((item, index) => (
                <div key={item.marketEffectiveDateJst} className="ranking-row">
                  <div>
                    <strong>#{index + 1}</strong> {item.marketEffectiveDateJst}
                  </div>
                  <div>score {item.score.toFixed(4)}</div>
                </div>
              ))}
            </div>
          }
          details={
            <div className="stack">
              {ranking.map((item) => {
                const record = demoData?.records.find(
                  (candidate) =>
                    candidate.marketEffectiveDateJst === item.marketEffectiveDateJst,
                );
                return (
                  <article key={item.marketEffectiveDateJst} className="detail-card">
                    <h3>{item.marketEffectiveDateJst}</h3>
                    <p>コサイン類似度: {item.score.toFixed(4)}</p>
                    <p>主要ジャンル: {record?.topics.genres.map((genre) => genre.name).join(", ") || "-"}</p>
                    <p>{record?.summary.slice(0, 180) ?? ""}...</p>
                  </article>
                );
              })}
            </div>
          }
        />

        <SectionCard
          title="予想株価"
          eyebrow="Step 5"
          summary={
            predicted ? (
              <div className="metric-grid">
                <div className="metric">
                  <span>日経平均 参考騰落率</span>
                  <strong>{formatPercent(predicted.n225)}</strong>
                </div>
                <div className="metric">
                  <span>TOPIX連動ETF 参考騰落率</span>
                  <strong>{formatPercent(predicted.topix)}</strong>
                </div>
              </div>
            ) : (
              <p>ベクトルが確定すると類似日ベースの参考騰落率を表示します。</p>
            )
          }
          details={
            predicted ? (
              <div className="stack">
                <p>
                  上位 3 類似日のコサイン類似度を重みとして、当日騰落率の参考値を加重平均しています。
                  投資判断用ではありません。
                </p>
                <ul className="plain-list">
                  {predicted.references.map((item) => (
                    <li key={item.marketEffectiveDateJst}>
                      {item.marketEffectiveDateJst} / score {item.score.toFixed(4)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p>類似度ランキング待ちです。</p>
            )
          }
        />

        <SectionCard
          title="処理ログ"
          eyebrow="Monitor"
          summary={
            <div className="stack">
              {logs.length ? (
                logs.map((log) => (
                  <div key={`${log.timestamp}-${log.message}`} className={`log-row ${log.level}`}>
                    <span>{log.timestamp}</span>
                    <strong>{log.level}</strong>
                    <span>{log.message}</span>
                  </div>
                ))
              ) : (
                <p>まだログはありません。</p>
              )}
            </div>
          }
          details={
            <div className="stack">
              <p>現在選択日: {selectedDate || "-"}</p>
              <p>ニュース件数: {formatNumber(selectedRecord?.articleCount)}</p>
              <p>
                日経平均実績:{" "}
                {formatPercent(selectedRecord?.market.n225PrevCloseChangePct)}
              </p>
              <p>
                TOPIX連動ETF実績:{" "}
                {formatPercent(selectedRecord?.market.topixProxyPrevCloseChangePct)}
              </p>
            </div>
          }
        />
      </main>
    </div>
  );
}

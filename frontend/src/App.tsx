import { useEffect, useMemo, useState } from "react";
import { ApiKeyModal } from "./components/ApiKeyModal";
import { PipelineStatus } from "./components/PipelineStatus";
import { SectionCard } from "./components/SectionCard";
import { TutorialOverlay } from "./components/TutorialOverlay";
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
const TUTORIAL_STORAGE_KEY = "daily-aura-stock-tutorial-completed";
const DATA_PATH = "./assets/data/demo-data.json";

const TUTORIAL_STEPS = [
  {
    label: "Step 0",
    title: "API 管理",
    targetId: "step-0",
    body:
      "このデモでは Gemini API キーをページ表示後に入力し、ブラウザの localStorage にだけ保存します。API キーを設定すると Step 2 の再要約と Step 3 の再ベクトル化を実行できますが、キーはブラウザ上で扱われるため秘匿はできません。",
    hint:
      "初回は API 管理カードや入力モーダルを確認し、共用端末では保存しないことと、デモ用または制限付きキーを使うことを意識してください。",
  },
  {
    label: "Step 1",
    title: "ニュース入力",
    targetId: "step-1",
    body:
      "ここでは 1 営業日分のニュース記事や見出し集合を貼り付けます。既存サンプルの日付ボタンを押せば保存済みデータを読み込めるので、まずは実データの流れを確認し、その後に自由入力へ切り替える使い方ができます。",
    hint:
      "貼り付ける内容は 1 日分のニュース集合が基本です。本文付きでも見出し中心でも動きますが、日次の空気感が分かるまとまりにすると後段の結果が安定します。",
  },
  {
    label: "Step 2",
    title: "要約",
    targetId: "step-2",
    body:
      "Step 2 では、その日のニュース全体を 1 本の文章に要約します。保存済みサマリーをそのまま使うこともでき、API キーがある場合は Gemini で再要約して、入力ニュースから新しい日次サマリーを生成できます。",
    hint:
      "このサマリーは次のベクトル化の元になるので、個別記事の羅列ではなく、その日の主要トピックと全体傾向が分かる文章になっていることが重要です。",
  },
  {
    label: "Step 3",
    title: "ベクトル化",
    targetId: "step-3",
    body:
      "Step 3 では、保存済みベクトルを使う、Gemini でサマリーから埋め込みを生成する、または embedding.txt の JSON を貼り付けて適用する、という 3 通りの使い方ができます。ここで得られたベクトルが類似日検索の核になります。",
    hint:
      "埋め込み JSON 貼り付け欄には `vector_length` と `values` を含む JSON をそのまま貼れます。適用すると、すぐにランキングと予想株価が更新されます。",
  },
  {
    label: "Step 4",
    title: "類似検索",
    targetId: "step-4",
    body:
      "Step 4 では、入力ベクトルと保存済み営業日ベクトルとのコサイン類似度を計算し、ニュースの空気感が近い順にランキング表示します。ここを見ることで、どの日がもっとも近い日として選ばれたかを確認できます。",
    hint:
      "ランキング上位の日は、主要ジャンルやサマリーも合わせて確認すると理解しやすくなります。単に数値だけでなく、どのようなニュース構成の日だったかが重要です。",
  },
  {
    label: "Step 5",
    title: "予想表示",
    targetId: "step-5",
    body:
      "Step 5 では、最もコサイン類似度が高い営業日の当日騰落率を、そのまま参考値として表示します。もし 1 位が複数ある場合だけ、その同率 1 位の日々の平均値を出し、日経平均と TOPIX 連動 ETF の参考変動を示します。",
    hint:
      "これは投資判断用ではなく、ニュースの空気感が近い日に市場がどう動いたかを簡易に見るための指標です。処理ログと合わせて結果の流れを確認してください。",
  },
] as const;

function nowLabel(): string {
  return new Date().toLocaleString("ja-JP");
}

export function App() {
  const [demoData, setDemoData] = useState<DemoData | null>(null);
  const [apiKeyState, setApiKeyState] = useState<ApiKeyState>({ value: "" });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isTutorialOpen, setIsTutorialOpen] = useState(false);
  const [tutorialStepIndex, setTutorialStepIndex] = useState(0);
  const [pipelineState, setPipelineState] = useState<PipelineState>("idle");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [newsInput, setNewsInput] = useState("");
  const [summaryInput, setSummaryInput] = useState("");
  const [vectorInput, setVectorInput] = useState<number[]>([]);
  const [vectorTextInput, setVectorTextInput] = useState("");
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
    }

    const tutorialCompleted = window.localStorage.getItem(TUTORIAL_STORAGE_KEY);
    if (!tutorialCompleted) {
      setIsTutorialOpen(true);
    } else if (!savedKey) {
      setIsModalOpen(true);
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
    setVectorTextInput(
      JSON.stringify(
        {
          vector_length: record.embedding.length,
          values: record.embedding,
        },
        null,
        2,
      ),
    );
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

    const highestScore = ranking[0]?.score;
    if (highestScore === undefined) {
      return null;
    }

    const top = ranking.filter((item) => item.score === highestScore);
    let count = 0;
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
      n225 += record.market.n225PrevCloseChangePct ?? 0;
      topix += record.market.topixProxyPrevCloseChangePct ?? 0;
      count += 1;
    }

    if (!count) {
      return null;
    }

    return {
      n225: n225 / count,
      topix: topix / count,
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
      setVectorTextInput(
        JSON.stringify(
          {
            vector_length: values.length,
            values,
          },
          null,
          2,
        ),
      );
      appendLog("info", "埋め込み生成が完了しました。");
      setPipelineState("ranking");
    } catch (error) {
      appendLog("error", `埋め込み生成に失敗: ${String(error)}`);
      setPipelineState("error");
    }
  }

  function handleApplyVectorText() {
    try {
      const parsed = JSON.parse(vectorTextInput) as
        | { values?: number[]; vector_length?: number }
        | number[];
      const values = Array.isArray(parsed) ? parsed : parsed.values ?? [];
      if (!Array.isArray(values) || !values.length) {
        throw new Error("values 配列が見つかりません。");
      }
      if (!values.every((value) => typeof value === "number")) {
        throw new Error("values は数値配列である必要があります。");
      }
      setVectorInput(values);
      appendLog("info", `貼り付けた埋め込みベクトルを適用しました。(${values.length} 次元)`);
      setPipelineState("ranking");
    } catch (error) {
      appendLog("error", `埋め込み貼り付けの解析に失敗: ${String(error)}`);
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

  function handleOpenTutorial() {
    setTutorialStepIndex(0);
    setIsTutorialOpen(true);
  }

  function handleCloseTutorial() {
    window.localStorage.setItem(TUTORIAL_STORAGE_KEY, "true");
    setIsTutorialOpen(false);
    if (!apiKeyState.value) {
      setIsModalOpen(true);
    }
  }

  const vectorSummary = summarizeVector(vectorInput);
  const activeTutorialTargetId =
    isTutorialOpen && TUTORIAL_STEPS[tutorialStepIndex]
      ? TUTORIAL_STEPS[tutorialStepIndex].targetId
      : "";

  return (
    <div className="app-shell">
      <ApiKeyModal
        isOpen={isModalOpen}
        initialValue={apiKeyState.value}
        onSave={handleSaveApiKey}
        onClose={() => setIsModalOpen(false)}
      />
      <TutorialOverlay
        isOpen={isTutorialOpen}
        currentStep={tutorialStepIndex}
        steps={[...TUTORIAL_STEPS]}
        onClose={handleCloseTutorial}
        onNext={() =>
          setTutorialStepIndex((current) =>
            Math.min(current + 1, TUTORIAL_STEPS.length - 1),
          )
        }
        onPrev={() => setTutorialStepIndex((current) => Math.max(current - 1, 0))}
      />

      <header className="hero">
        <button
          type="button"
          className="tutorial-trigger"
          onClick={handleOpenTutorial}
          aria-label="操作チュートリアルを開く"
          title="操作チュートリアル"
        >
          ?
        </button>
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
          tutorialId="step-0"
          className={activeTutorialTargetId === "step-0" ? "tutorial-target-active" : ""}
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
          tutorialId="step-1"
          className={activeTutorialTargetId === "step-1" ? "tutorial-target-active" : ""}
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
          tutorialId="step-2"
          className={activeTutorialTargetId === "step-2" ? "tutorial-target-active" : ""}
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
          tutorialId="step-3"
          className={activeTutorialTargetId === "step-3" ? "tutorial-target-active" : ""}
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
                      setVectorTextInput(
                        JSON.stringify(
                          {
                            vector_length: selectedRecord.embedding.length,
                            values: selectedRecord.embedding,
                          },
                          null,
                          2,
                        ),
                      );
                      appendLog("info", "保存済み埋め込みベクトルを復元しました。");
                    }
                  }}
                >
                  保存済みベクトルを使う
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={handleApplyVectorText}
                  disabled={!vectorTextInput.trim()}
                >
                  貼り付けたベクトルを適用
                </button>
              </div>
            </div>
          }
          details={
            <div className="stack">
              <label className="field">
                <span>埋め込み JSON 貼り付け</span>
                <textarea
                  rows={10}
                  value={vectorTextInput}
                  onChange={(event) => setVectorTextInput(event.target.value)}
                  placeholder={'{"vector_length":3072,"values":[0.001, ...]}'}
                />
              </label>
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
          tutorialId="step-4"
          className={activeTutorialTargetId === "step-4" ? "tutorial-target-active" : ""}
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
          tutorialId="step-5"
          className={activeTutorialTargetId === "step-5" ? "tutorial-target-active" : ""}
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
                  最もコサイン類似度が高い営業日の当日騰落率をそのまま参考表示しています。
                  同率 1 位が複数ある場合のみ、その営業日群の平均値を表示します。投資判断用ではありません。
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

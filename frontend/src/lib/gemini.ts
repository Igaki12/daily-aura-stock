const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models";

async function postToGemini<TResponse>(
  apiKey: string,
  model: string,
  action: "generateContent" | "embedContent",
  payload: unknown,
): Promise<TResponse> {
  const response = await fetch(
    `${GEMINI_BASE_URL}/${model}:${action}?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Gemini API error ${response.status}: ${body}`);
  }

  return (await response.json()) as TResponse;
}

type GenerateResponse = {
  candidates?: Array<{
    content?: {
      parts?: Array<{ text?: string }>;
    };
  }>;
};

type EmbedResponse = {
  embedding?: { values?: number[] };
  embeddings?: Array<{ values?: number[] }>;
};

export async function generateSummary(
  apiKey: string,
  newsText: string,
): Promise<string> {
  const prompt =
    "あなたはニュース日次集約アシスタントです。入力された1営業日分のニュース本文または箇条書きから、その日の主要論点、国際・国内トピック、マーケットに影響しうる論点を整理し、400〜800文字程度の日本語サマリーを作成してください。事実ベースで、投資助言はせず、全体の空気感が伝わるようにまとめてください。";

  const response = await postToGemini<GenerateResponse>(
    apiKey,
    "gemini-3-flash-preview",
    "generateContent",
    {
      contents: [
        {
          parts: [{ text: `${prompt}\n\n[ニュース入力]\n${newsText}` }],
        },
      ],
    },
  );

  const text =
    response.candidates?.[0]?.content?.parts
      ?.map((part) => part.text ?? "")
      .join("")
      .trim() ?? "";

  if (!text) {
    throw new Error("Gemini summary response did not contain text.");
  }

  return text;
}

export async function embedSummary(
  apiKey: string,
  summaryText: string,
): Promise<number[]> {
  const response = await postToGemini<EmbedResponse>(
    apiKey,
    "gemini-embedding-001",
    "embedContent",
    {
      model: "models/gemini-embedding-001",
      content: {
        parts: [{ text: summaryText }],
      },
      taskType: "SEMANTIC_SIMILARITY",
      outputDimensionality: 3072,
    },
  );

  const values =
    response.embedding?.values ?? response.embeddings?.[0]?.values ?? [];

  if (!values.length) {
    throw new Error("Gemini embedding response did not contain values.");
  }

  return values;
}

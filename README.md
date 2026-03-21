# DailyAuraStock

1営業日分のニュース集合から「その日のニュースの空気感」を要約・ベクトル化し、過去の類似日と株価変動を参照するプロジェクトです。

現在このリポジトリには、以下の2系統があります。

- `backend/`: NewsML 抽出、日次集計、Gemini 要約・埋め込み生成などの前処理
- `frontend/` + `docs/`: GitHub Pages で公開する静的デモ

詳細仕様は [AGENTS.md](/Users/igaki/Documents/GitHub/daily-aura-stock/AGENTS.md) を参照してください。

## GitHub Pages デモ

GitHub Pages 版は `docs/index.html` を入口とする静的デモです。  
ブラウザだけで動作し、保存済みの 6 営業日データを使って、ニュース入力、日次サマリー、埋め込み、類似日ランキング、参考騰落率を確認できます。

### 公開内容

- [docs/index.html](/Users/igaki/Documents/GitHub/daily-aura-stock/docs/index.html)
- [docs/assets/data/demo-data.json](/Users/igaki/Documents/GitHub/daily-aura-stock/docs/assets/data/demo-data.json)

### 前提

- Node.js / npm が使えること
- GitHub リポジトリの Pages 設定で、公開元を `Deploy from a branch` + `main` ブランチ + `/docs` にすること

### ローカルでビルドする

```bash
npm install
npm run build
```

これで以下が更新されます。

- `frontend/public/assets/data/demo-data.json`
- `docs/index.html`
- `docs/assets/*`

### ローカルで確認する

```bash
npm run dev
```

またはビルド済み成果物を確認する場合:

```bash
npm run preview
```

### GitHub Pages に公開する

1. `npm run build` を実行する
2. `docs/` 配下の成果物が更新されていることを確認する
3. 変更をコミットして GitHub に push する
4. GitHub のリポジトリ設定で Pages の公開元を `/docs` に設定する

## Gemini API キーの扱い

GitHub Pages デモでは、Gemini API キーを環境変数ではなく、ページ表示時のモーダル入力で受け取ります。

- API キーはブラウザから直接 Gemini API に送信されます
- キーは `localStorage` に保存されます
- ブラウザ実行のため、キーを秘匿することはできません
- 共用端末では保存しないでください
- デモ用途では利用制限付きキーを推奨します

実キーをソースコード、`docs/` 配下、JSON ファイルへ埋め込まないでください。

## Pages デモのデータ更新

Pages デモは、既存の前処理生成物から軽量 JSON を作って表示します。  
次の順で更新します。

1. `backend/data/...` の前処理生成物を更新する
2. `npm run build` を実行する
3. `frontend/scripts/build_demo_data.py` が `demo-data.json` を再生成する
4. `docs/` を再ビルドする

現在の Pages デモで使う主な入力は以下です。

- `backend/data/daily_comparison/2025-06-22_2025-06-28/daily_comparison.csv`
- `backend/data/gemini_outputs/2025-06-22_2025-06-28/manifest.json`
- `backend/data/gemini_outputs/2025-06-22_2025-06-28/<date>/summary.txt`
- `backend/data/gemini_outputs/2025-06-22_2025-06-28/<date>/embedding.json`

## 注意点

- Pages 版の類似検索母集団は 6 営業日分だけなので、結果は UI 検証用です
- 予想株価は、類似日の当日騰落率を使った参考表示であり、投資判断用ではありません
- 本番では FastAPI + PostgreSQL + `pgvector` に移行する前提です

## 関連ファイル

- [AGENTS.md](/Users/igaki/Documents/GitHub/daily-aura-stock/AGENTS.md)
- [frontend/App.tsx](/Users/igaki/Documents/GitHub/daily-aura-stock/frontend/src/App.tsx)
- [frontend/vite.config.ts](/Users/igaki/Documents/GitHub/daily-aura-stock/frontend/vite.config.ts)
- [build_demo_data.py](/Users/igaki/Documents/GitHub/daily-aura-stock/frontend/scripts/build_demo_data.py)

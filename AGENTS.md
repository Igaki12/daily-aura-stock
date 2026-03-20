# AGENTS.md

## 1. プロジェクト概要 (Project Overview)
**プロジェクト名: DailyAuraStock**

本プロジェクトは、1日の全ニュース記事（共同通信社提供）から「その日のニュースの全体的な方向性・量・トピックのバランス」を抽出し、ベクトル化（Embedding）する。そのベクトルを用いて過去のデータベースから「最もニュースの空気感（Aura）が似ていた日（類似日）」を検索し、その類似日直後の株価（Stock）がどう動いたかを出力・可視化するWebアプリケーション。

## 2. 技術スタック (Tech Stack)
- **Backend**: Python 3.12+, FastAPI, Pandas, SQLAlchemy, `psycopg2-binary`
- **Frontend**: TypeScript, React 18+, Vite, Tailwind CSS, **Chart.js** (via `react-chartjs-2`)
- **Infrastructure**: XServer VPS (Ubuntu 25.04), Nginx, Gunicorn/Uvicorn, **PostgreSQL** (拡張機能 `pgvector` を使用)
- **External APIs**: 
  - 1日サマリー生成: **Google Gemini API (gemini-3-flash-preview)**
  - ベクトル化: **Google Gemini API (gemini-embedding-001)**
  - 株価データ取得: `yfinance` を利用した Yahoo Finance データ取得

## 2.1 参照する公式ドキュメント (Official References)
- [gemini-3-flash-preview.md](./gemini-3-flash-preview.md): Gemini 3 Flash 系の公式仕様。`generateContent`、1M トークン入力 / 64k 出力、`thinking_level`、Preview モデルである点を確認すること。
- [gemini-embedding-001.md](./gemini-embedding-001.md): Embedding API の公式仕様。`embedContent`、`SEMANTIC_SIMILARITY`、`output_dimensionality`、入力トークン上限、正規化の注意点を確認すること。
- 実装時は上記 2 文書を一次情報として扱い、モデル ID、パラメータ名、トークン制約、レスポンス形式をコードに反映すること。

## 3. インフラストラクチャ要求スペック (Infrastructure Specs)
APIによるオフロード処理を前提とした、VPSでの効率的な運用構成。
* **推奨スペック**: CPU 4コア / メモリ 8GB以上。
* **DB要件**: PostgreSQL + `pgvector`。日次集計データのため、数万件規模のニュースでもインデックス検索は高速に動作する。

## 4. データ処理パイプライン (Daily Aggregation Pipeline)

### Step 1: LLMによる「1日のニュースサマリー」生成
1日の全てのニュース記事（または見出し一覧）を **Gemini 3 Flash** に入力。
* 全体的なセンチメント（ポジ/ネガの偏り）と、主要トピックの構成比（政治、経済、災害、スポーツ等）を言語化。
* 実装時は [gemini-3-flash-preview.md](./gemini-3-flash-preview.md) を参照し、`generateContent` API を用いること。大量テキスト投入時は 1M トークンのコンテキスト上限と、Preview モデル差し替えに備えた設定切り替えを考慮すること。

### Step 2: サマリーのベクトル化
生成された「1日の総括テキスト」を Gemini の Embedding API に渡し、高次元の **Daily Meta-Vector** を生成。
* 実装時は [gemini-embedding-001.md](./gemini-embedding-001.md) を参照し、`embedContent` API と `taskType=SEMANTIC_SIMILARITY` を用いること。
* `output_dimensionality` は **3072** を明示設定すること。`gemini-embedding-001` の 3072 次元ベクトルは正規化済みであることを前提に、`pgvector` のコサイン距離検索と整合させること。

### Step 3: 類似日の検索と株価解析
* **検索**: ターゲット日のベクトルに対し、`pgvector` を用いて過去の類似日を上位N件抽出。
* **解析**: `yfinance` から取得した類似日の前後1週間の株価変動を統計的に集計。

## 5. エージェントへの基本指示 (Core Directives)
1. **型安全・非同期**: FrontendはTypeScript、BackendはPydanticと `async/await` を徹底すること。
2. **pgvectorクエリ**: ベクトル検索はコサイン距離（`<=>` 演算子）を用い、SQLAlchemyでの実装または生SQLでの最適化を行うこと。
3. **UI/UX**: ユーザーが「あの日と似ている！」と直感的に理解できるよう、Chart.jsを用いて複数の類似日の株価推移を重ね合わせて表示すること。

## 6. ディレクトリ構成 (Directory Structure)
```text
.
├── backend/               # FastAPI
│   ├── app/
│   │   ├── api/           # 類似日検索、株価データ提供
│   │   ├── db/            # pgvector対応設定
│   │   ├── services/      # Gemini 3 Flash / Embedding 連携ロジック
│   │   └── tasks/         # 日次バッチ処理 (ニュース集計)
│   ├── requirements.txt
│   └── .env
├── frontend/              # React + Vite
│   ├── src/
│   │   ├── components/    # 比較チャート (Chart.js)
│   │   ├── pages/         # 検索・分析ダッシュボード
│   └── vite.config.ts
└── deploy/                # XServer VPS 設定 (Nginx, systemd)
```

## 7. 実装可能性の検証結果 (Feasibility Validation)
- 結論: 本仕様は実装可能。
- 根拠 1: [gemini-3-flash-preview.md](./gemini-3-flash-preview.md) で `gemini-3-flash-preview` の `generateContent` が確認でき、長文要約用途に十分な 1M トークン入力コンテキストがある。
- 根拠 2: [gemini-embedding-001.md](./gemini-embedding-001.md) で `gemini-embedding-001` の `embedContent`、`SEMANTIC_SIMILARITY`、可変次元の埋め込み生成が確認でき、日次サマリー同士の類似検索に適用できる。
- 根拠 3: `pgvector` のコサイン距離検索と PostgreSQL の組み合わせは、日単位のベクトル件数規模に対して実務上十分に現実的。
- 根拠 4: `yfinance` により類似日の前後時系列を取得し、Chart.js で重ね描画する構成は一般的で、Web アプリ構成として成立する。

## 8. 実装上の前提・注意点 (Implementation Notes)
- `gemini-3-flash-preview` は Preview モデルであるため、将来のモデル差し替えに備えて `.env` や設定ファイルでモデル ID を切り替え可能にすること。
- 1日分の全文記事をそのまま投入すると、記事量によっては前処理が必要になる。見出しのみ、記事要約、トピック別分割要約などのフォールバック戦略を用意すること。
- `gemini-embedding-001` はテキスト埋め込み用途として成立するが、1 リクエストの入力トークン上限を超えないよう、日次サマリーは十分に圧縮してから投入すること。
- ベクトル比較は `pgvector` の `<=>` と整合するようコサイン類似ベースで統一すること。
- `yfinance` は Yahoo, Inc. の公式 SDK / 公式業務 API ではなく、公開データを利用する OSS クライアントである。利用条件は Yahoo 側の規約と `YahooFinanceAPI/README.md` の注意書きに従うこと。
- 現時点のリポジトリには `backend/` や `frontend/` の実装本体が未作成のため、本書は「実装可能な設計指針」として扱うこと。

## 9. NewsPack NewsML 取り込み仕様 (News Ingestion Specification)

### 9.1 参照資料
- [NewsPack_NewsMLフォーマット解説書_一般契約社配布用_20230427_v1.25.pdf](./NewsPack_NewsML%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%83%E3%83%88%E8%A7%A3%E8%AA%AC%E6%9B%B8_%E4%B8%80%E8%88%AC%E5%A5%91%E7%B4%84%E7%A4%BE%E9%85%8D%E5%B8%83%E7%94%A8_20230427_v1.25.pdf): NewsPack NewsML の公式解説書。NewsML 構造、NewsText、付加情報、版管理、リンク更新の運用を確認すること。
- [NewsPack_NewsMLフォーマット解説書_一般契約社配布用_20230427_v1.25.txt](./NewsPack_NewsML%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%83%E3%83%88%E8%A7%A3%E8%AA%AC%E6%9B%B8_%E4%B8%80%E8%88%AC%E5%A5%91%E7%B4%84%E7%A4%BE%E9%85%8D%E5%B8%83%E7%94%A8_20230427_v1.25.txt): 上記 PDF の文字起こし版。タグ定義や運用指針をテキスト検索したい場合の補助資料として用いること。
- [CO2025062501000212.1.N.20250625T071704.xml](./CO/2025/06/25/CO2025062501000212.1.N.20250625T071704.xml): CompactNews 実例。見出し、本文、SubjectCode、地域情報、NewsGenre、GroupId の実データ例。
- [CO2025062501000539.2.N.20250625T113406.xml](./CO/2025/06/25/CO2025062501000539.2.N.20250625T113406.xml): 記事版更新と `AssociatedWith` を含む実例。
- [CO2025062501000251.2.N.20250625T135405.xml](./CO/2025/06/25/CO2025062501000251.2.N.20250625T135405.xml): スポーツ系記事と複数国地域情報の実例。

### 9.2 取り込み対象と基本方針
- 日次 Aura 集計の主対象は **記事系 NewsML の本文付きレコード** とする。
- 初期実装では `CO/` 配下の **CompactNews** を優先対応対象とし、`NewsEnvelope/NewsService` または `Metadata/NewsBrandInfo` の商品名で識別すること。
- PhotoNews 向けの画像リンク更新 (`AssociatedWith`) は保存してよいが、日次サマリー本文の主入力には使わない。
- 共同通信の公式解説書に従い、`DataContent/newstext/body/news.content/p` の段落群を本文とみなす。現状 NewsPack 配信では `p` 要素中心であることを前提とする。

### 9.3 XML パーサ実装方針
- XML パーサは Python 標準の `xml.etree.ElementTree` または `lxml` を使用し、DTD の検証までは必須としない。
- ファイルの文字コードは XML 宣言に従って自動判定すること。仕様書には `utf-8` 以外に `utf-16`、`Shift_JIS` の例もあるため、文字コードを固定しないこと。
- `Catalog` や DTD の相対参照は解析上の補助情報として扱い、初期実装では外部参照を解決しなくても本文抽出できる構成にすること。

### 9.4 1記事あたりの保持項目
- `provider_id`: `Identification/NewsIdentifier/ProviderId`
- `date_id`: `Identification/NewsIdentifier/DateId`
- `news_item_id`: `Identification/NewsIdentifier/NewsItemId`
- `revision_id`: `Identification/NewsIdentifier/RevisionId` の数値
- `revision_update`: `RevisionId@Update`
- `public_identifier`: `Identification/NewsIdentifier/PublicIdentifier`
- `transmission_id`: `NewsEnvelope/TransmissionId`
- `sent_at`: `NewsEnvelope/DateAndTime`
- `first_created`: `NewsManagement/FirstCreated`
- `this_revision_created`: `NewsManagement/ThisRevisionCreated`
- `status`: `NewsManagement/Status@FormalName`
- `instruction`: `NewsManagement/Instruction@FormalName`
- `news_service`: `NewsEnvelope/NewsService@FormalName` の配列
- `news_brand`: `Metadata/NewsBrandInfo/NewsBrand@Value`
- `headline`: `NewsLines/HeadLine`
- `subheadline`: `NewsLines/SubHeadLine`
- `keyword_line`: `NewsLines/KeywordLine`。存在しない場合を許容すること。
- `body_text`: `news.content/p` を改行結合した全文
- `subject_codes`: `DescriptiveMetadata/SubjectCode` の配列
- `area_codes`: `NskAreaInformation` 内の `NskCountry` と `NskJpnAreaCode`
- `corporations`: `KyodoCorporationInfo` 内の `StockCode`、`Market`、`Name`
- `news_genres`: `NewsGenreInfo` 内の大分類名と `NewsGenre@Value`
- `group_id`: `MetadataType=GroupId` の `Property@Value`
- `associated_with`: `NewsManagement/AssociatedWith@NewsItem` と `Comment`
- `raw_xml_path`: 取り込み元ファイルパス

### 9.5 日次集計に使う正規化済み本文
- LLM に渡す単位は XML 1件ごとの生本文ではなく、当日有効記事を集約した日次テキストとする。
- 記事ごとの日次集計用テキストは次の順で構成すること。
- `headline`
- `subheadline` があれば追加
- `keyword_line` があれば追加
- `news_brand` と `news_genres`
- `subject_codes` の上位分類
- `body_text`
- 地域情報や企業情報は、日次サマリーの偏りを捉える補助メタ情報として別途集計し、必要に応じて Gemini への入力プロンプトに統計要約として添付すること。

### 9.6 版管理と有効記事判定
- 仕様書 6.1 に従い、同一 `news_item_id` の記事は **最新 revision を 1 件だけ有効** とみなすこと。
- `RevisionId@Update="N"` かつ `Status@FormalName="Usable"` の記事は通常の有効版として扱うこと。
- `RevisionId@Update="A"` かつ `Status@FormalName="Canceled"` の場合は削除通知として扱い、その `news_item_id` は日次集計対象から除外すること。
- `FirstCreated` は初版日時として固定値、`ThisRevisionCreated` は版ごとに更新されるため、日次集計の基準時刻は `ThisRevisionCreated` を優先すること。
- 同一記事の複数版が同日に存在する場合、日次 Aura の入力に含める本文は **最終有効版のみ** とする。

### 9.7 リンク更新と AssociatedWith の扱い
- 仕様書ではリンク更新ファイルも `Update="A"` を利用するが、記事削除とは異なり `Status="Usable"` のままとなる。
- そのため `Update="A"` のみで削除判定してはならず、**`Status` と `NewsComponent` の有無を必ず併用して判定**すること。
- `AssociatedWith` は PhotoNews や関連記事との関連を表す補助情報として保存するが、初期版の Aura 集計ロジックでは本文の代替として使用しない。

### 9.8 分類情報の利用方針
- 記事分類の主キーには `NewsGenre` を用いること。仕様書上、NewsPack ジャンルは全記事に必ず付与される前提であり、UI 集計にも向いている。
- `SubjectCode` は詳細分類として保持し、後段で「政治」「経済」「災害」「スポーツ」などのトピック比率算出に利用すること。
- 地域情報は `NskCountry` を最小単位として必ず保持し、日本記事については `NskJpnAreaCode` も保持すること。
- 企業情報が存在する記事は、銘柄関連分析や将来の株式個別分析に拡張できるよう別テーブル化を前提に保持すること。
- `GroupId` は HeadlineNews / BriefNews / CompactNews 間の同内容派生記事の関連識別子として保存し、将来的な重複排除や商品横断統合に使えるようにすること。

### 9.9 データベース設計方針
- `news_items_raw`: 受信ファイル単位の生レコード格納。`news_item_id + revision_id + raw_xml_path` を一意候補とする。
- `news_items_current`: `news_item_id` ごとの最新有効版ビューまたはマテリアライズドテーブル。
- `daily_news_aggregates`: 日次集計結果。対象日、対象記事件数、ジャンル分布、主要地域、要約テキスト、embedding(3072) を保持する。
- `stock_snapshots` または `market_series`: 類似日比較用の株価系列を保持する。

### 9.10 日次バッチ処理の実装順
1. 対象日の XML ファイル群を走査する。
2. 各 XML から必要項目を抽出し `news_items_raw` に投入する。
3. `news_item_id` 単位で最新 revision を解決し、削除・リンク更新を反映した `news_items_current` を構築する。
4. `news_brand`、`news_genres`、`subject_codes`、地域、企業の統計を日次集計する。
5. 有効記事本文を束ねて 1 日の総括入力を作り、Gemini 3 Flash で日次サマリーを生成する。
6. 生成サマリーを `gemini-embedding-001` に `output_dimensionality=3072` で渡し、日次ベクトルを保存する。
7. `pgvector` で過去類似日を検索し、株価分析結果とともに API で返す。

### 9.11 実装済み前処理スクリプト
- `backend/app/tasks/extract_news_dataset.py`: NewsML XML 群から分析用データセットを抽出する。`market_effective_date_jst`、版管理、削除判定、リンク更新保持を含む。
- `backend/app/tasks/build_daily_llm_inputs.py`: `news_current.csv` を入力として、Gemini に渡す日次 LLM 入力テキストとメタデータ JSON を生成する。
- これらのスクリプトは、初期の検証用データとして `backend/data/news_extracts/` および `backend/data/llm_inputs/` に出力する運用を前提とする。

### 9.12 実装済み出力ファイルの役割
- `news_raw.csv`: XML ファイル単位の生抽出結果。版ごとの差分確認や監査に使う。
- `news_current.csv`: `news_item_id` ごとの最新有効版。日次集計や LLM 入力生成の主入力に使う。
- `daily_summary.json`: `market_effective_date_jst` 単位の件数、上位ジャンル、国、企業、見出しサンプルを保持する。
- `YYYY-MM-DD.txt`: 1営業日分の LLM 入力テキスト。統計サマリーと記事一覧を含む。
- `YYYY-MM-DD.json`: 上記 LLM 入力に対応するメタデータ。
- `manifest.json`: 期間全体の LLM 入力ファイル一覧と件数サマリー。

## 10. 日次区切り仕様 (Daily Boundary Specification)

### 10.1 基本原則
- ニュース保存用の日付と、株価影響を評価するための日付は分けて扱うこと。
- `calendar_date_jst` は JST の暦日 `00:00:00-23:59:59` を表し、ニュース原本の整理・検索・監査に使う。
- `market_effective_date_jst` は「そのニュースが主に日本株へ反映される営業日」を表し、Aura 生成・類似日検索・株価比較に使う。

### 10.2 0:00 基準をそのまま分析に使わない理由
- 暦日 0:00 区切りでは、場中に織り込まれたニュースと引け後に翌営業日へ持ち越されるニュースが同じ日バケットに混在する。
- 日本株の価格反応は市場営業日に依存するため、夜間配信・週末・祝日前後のニュースは翌営業日以降に効きやすい。
- したがって、日次 Aura を `calendar_date_jst` ベースだけで構築すると、ニュースと株価の対応がぼやける。

### 10.3 初期実装で採用する市場反映日ルール
- タイムゾーンは JST に統一する。
- ニュース時刻は原則として `this_revision_created` を基準に評価する。
- `this_revision_created` が営業日 `15:30:00 JST` 以前なら、そのニュースの `market_effective_date_jst` は当日とする。
- `this_revision_created` が営業日 `15:30:00 JST` を超える場合、`market_effective_date_jst` は翌営業日とする。
- 土日祝日および非営業日に配信されたニュースは、次の営業日に繰り越すこと。
- 同一 `news_item_id` の複数版が異なる時間帯にまたがる場合でも、日次 Aura に使うのは最終有効版 1 件とする。

### 10.4 株価比較との対応
- 類似日検索に使う日次ベクトルは `market_effective_date_jst` 単位で生成すること。
- 株価比較は、その `market_effective_date_jst` の終値を起点とした前後営業日リターンで行うこと。
- これにより、夜間ニュースを翌営業日の値動きに対応付けられる。

### 10.5 追加で保持する日付項目
- `calendar_date_jst`: `this_revision_created` の JST 暦日
- `market_effective_date_jst`: 市場反映日
- `is_after_close`: `15:30 JST` 超かどうか
- `source_timestamp_jst`: 市場反映日判定に使った元時刻

### 10.6 将来拡張
- 初期実装では単純な `15:30 JST` カットオフを採用するが、将来は寄り前・場中・引け後で重み付けを変えることを許容する。
- 将来は `JPX` の営業日カレンダーと連動させ、半日取引や臨時休場にも対応可能な設計にすること。

### 10.7 現在の実装上の制約
- 現在の `market_effective_date_jst` 判定は `weekday_only` であり、土日を非営業日として扱う簡易実装である。JPX 祝日や臨時休場は未対応。
- 検証用データ `CO/2025/06/22-28` では、週末配信分が翌営業日である `2025-06-23` および `2025-06-30` に繰り越されることを確認済み。
- 本番実装では `JPX` 営業日カレンダーと連携し、祝日判定を必須とすること。

## 11. Yahoo Finance データ取得仕様の整合確認 (Yahoo Finance Alignment)

### 11.1 参照資料
- [YahooFinanceAPI/README.md](./YahooFinanceAPI/README.md): `yfinance` の利用前提、法的注意、主要コンポーネントの参照元。
- [YahooFinanceAPI/requirements.txt](./YahooFinanceAPI/requirements.txt): `yfinance` の依存関係一覧。

### 11.2 検証結果
- 結論: 現行仕様は `yfinance` ベースの株価取得と概ね整合している。
- `AGENTS.md` の株価取得部分は `yfinance` を利用する前提に修正済みであり、`README.md` の説明と矛盾しない。
- `requirements.txt` に含まれる `pandas`、`numpy`、`pytz` は本プロジェクトの時系列集計と市場反映日判定に適合する。
- 本プロジェクトの Backend 既定スタックにも `pandas` が含まれており、依存の方向性は一致している。

### 11.3 注意点
- `README.md` の記載どおり、`yfinance` は Yahoo の公式 API ではないため、`AGENTS.md` 上でも「公式 API」とは扱わないこと。
- `requirements.txt` のうち `curl_cffi`、`requests_cache`、`requests_ratelimiter`、`websockets` などは `yfinance` 側依存であり、アプリ本体の最低依存とは分けて管理すること。
- 株価時系列は暦日ではなく営業日ベースで返る前提で実装し、`market_effective_date_jst` と結合すること。

## 12. LLM 入力前処理仕様 (LLM Input Preprocessing)

### 12.1 基本方針
- Gemini に渡す入力は、単純な全文連結ではなく、1営業日分の記事集合を「統計サマリー + 記事一覧」の形に整形したテキストとする。
- 入力単位は `market_effective_date_jst` ごとに 1 ファイルとする。
- 元データは `news_current.csv` を利用し、削除済み記事や古い版は含めない。

### 12.2 日次 LLM 入力の構成
- ヘッダ: `market_effective_date_jst`、総記事数、実際に入力へ含めた記事数
- 集計サマリー: 上位ジャンル、上位関連国・地域、上位関連企業、上位キーワード
- 記事一覧: 各記事について見出し、配信時刻、`NewsItemId`、サブ見出し、キーワード、商品種別、ジャンル、関連地域、関連企業、本文要約を列挙する
- 本文は 1 記事あたり最大文字数を制限して圧縮する

### 12.3 現在の実装パラメータ
- `max_articles_per_day=200`
- `max_body_chars=600`
- 記事は `source_timestamp_jst` 昇順で採用する
- キーワードは `KeywordLine` を簡易分割して集計する

### 12.4 現在確認されている注意点
- 地震速報や定型速報のように件数が非常に多いジャンルは、上位ジャンルや記事一覧を占有しやすい。
- 実データ検証では `earthquake` が上位ジャンルに偏りやすく、日次 Aura の表現を歪める可能性がある。
- このため、将来的にはジャンル別サンプリング、重複圧縮、速報系ニュースの重み調整を導入することが望ましい。
- 現在の LLM 入力は検証用のベースライン実装であり、最終仕様ではトークン数・情報密度・ノイズ比率を見ながら調整すること。

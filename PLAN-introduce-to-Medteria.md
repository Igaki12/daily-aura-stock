# Medteria外観への全面統合計画

## Summary
既存のベクトル検索実装は活かしつつ、画面全体を Medteria のドライブ一覧風レイアウトへ再構成する。完成形は「左サイドバー + 上部バー + 中央のドライブ画面」を維持し、その中央領域に `APIキー入力 → 接続確認とサンプル準備 → 検索 → 結果一覧 → PDF詳細プレビュー` を自然に組み込む。

## Key Changes
- 画面骨格を Medteria 参照HTMLに寄せて再設計する。
  - 左側にコミュニティ/スペース風サイドバーを配置。
  - 上部にロゴ・通知/アカウント相当のトップバーを配置。
  - 中央を「Drive / Files」風のメイン領域にし、既存の検索機能をその文脈で見せる。
- 中央メイン領域の情報構造を Medteria ドライブ一覧に合わせて整理する。
  - 上段に API キー接続カードと検索入力を横並びまたは縦積みで配置。
  - その下にサンプルストレージ状態、検索対象数、索引済みページ数を一覧管理UI風に表示。
  - 結果はカード列ではなく、ドライブ一覧に近い「行ベースのランキングリスト」に変更する。
- 検索結果の見せ方を既存要件に合わせて Medteria 文脈へ変換する。
  - 各行にファイル名、種別、最関連ページ/セグメント、最終スコア、抜粋を表示。
  - PDF 行のみクリック可能にし、最関連ページから詳細プレビューを開く。
  - `RESULTS` セクションの濃色強調と3秒演出は維持するが、周囲のUIトーンと干渉しないよう一覧領域内の注目帯として実装する。
- PDF プレビューを既存アプリ風ではなく Medteria 画面の拡張パネルとして見せる。
  - 横長画面では右側固定ペインで開き、中央リストを左へ圧縮。
  - 縦長画面では下部シートとして開く。
  - 全画面暗転オーバーレイは使わず、AGENTS.md の擬似スプリットビュー方針を維持する。
- 追加資料登録は主導線から外したまま、ドライブ画面下部の補助セクションへ移す。
  - `.pdf` / `.txt` 追加、テキストメモ追加、サンプルPDF確認を「補助パネル」または「詳細セクション」として畳み込み可能に整理する。

## Interfaces / Behavior
- 既存の埋め込み・検索ロジック API は維持する。
  - [`src/lib/googleEmbeddings.js`](/Users/igaki/Documents/GitHub/vector-file-search/src/lib/googleEmbeddings.js)
  - [`src/lib/search.js`](/Users/igaki/Documents/GitHub/vector-file-search/src/lib/search.js)
  - [`src/lib/pdf.js`](/Users/igaki/Documents/GitHub/vector-file-search/src/lib/pdf.js)
- 主な変更対象は UI 実装。
  - [`src/App.jsx`](/Users/igaki/Documents/GitHub/vector-file-search/src/App.jsx): レイアウト、表示階層、操作導線、結果行UI、プレビュー開閉導線を再構成。
  - [`src/styles.css`](/Users/igaki/Documents/GitHub/vector-file-search/src/styles.css): Medteria風トークン、2カラム/3エリア骨格、一覧レイアウト、レスポンシブ、プレビューアニメーションを全面更新。
- 新しい公開APIや保存仕様は追加しない。
  - APIキーは引き続き `localStorage`。
  - ストレージは引き続きブラウザメモリ上。
  - サンプルPDF自動ベクトル化の挙動は維持。

## Test Plan
- API キー未入力時に接続確認・追加登録・検索が適切にエラー表示される。
- API 接続確認成功時に `sample-files/` のPDFが重複なく自動ロードされ、PDFページ数とファイル数のサマリーが更新される。
- 検索実行で結果が関連度順に並び、PDF結果には最関連ページ番号が表示される。
- PDF結果クリック時に、横長では右ペイン、縦長では下部シートで該当ページから開く。
- `.txt` 結果はクリック不可のままで、将来拡張余地を壊さない。
- 結果更新時のみ濃色 `RESULTS` 領域の波打つ演出が発火し、`prefers-reduced-motion` では抑制される。
- スマートフォンでもヘッダー2列、状態サマリー3列、主要ボタン右寄せの要件を維持する。

## Assumptions
- 参照HTML/JSは見た目再現の参考として扱い、既存 Medteria の DOM や Next.js 構造をそのまま移植しない。
- 実装は React + 既存CSSベースで行い、MUI の新規導入は前提にしない。
- 「既存アプリの見た目を維持」は、Medteria の画面骨格・余白感・一覧中心のUIトーンを再現する意味で解釈する。
- 検索機能はモックではなく、現行リポジトリの実ベクトル検索ロジックをそのまま使う。

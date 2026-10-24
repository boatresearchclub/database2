# BRC 展開「2着別3着率」管理者読み取りAPI｜2026-10-24 引継ぎ

これは実際のBRC Workerにデプロイした実装ではなく、**安全性を明示する接続契約と候補コード**です。

## 今回実装した範囲

- `workers/brc_scenario_23_admin_route_candidate.mjs` — 管理者限定・read-only GET API候補。存在しない/不正な認証、一般会員、不正パラメータ、未検証の展示後、母数不足、研究原本異常のいずれも情報を広げない。
- `workers/test_brc_scenario_23_admin_route_candidate.mjs` — 未ログイン、一般会員、偽装、不正CORS、JWT検証例外、日付・期間保留、分母一致など11件の模擬テスト。**CI #142 で11/11 PASS**。
- `workers/brc_scenario_23_admin_client_candidate.mjs` — 将来の本体UIで使う読み取りクライアント候補。実際の管理者画面判定とセッショントークン取得は外部から注入する設計。Cookie/localStorageへの新規保存なし。公開表示ではリクエスト前に中止。
- `workers/test_brc_scenario_23_admin_client_candidate.mjs` — 実際のAPI候補とブラウザー候補を**模擬認証・模擬データで結合**し、本人実績と会場実績を混同しないことを確認する回帰テスト。
- `scripts/brc_four_workstream_readiness.py` — 公式Kの研究結果と、**本番Worker認証・KV読み戻し未完了**を別々のステータスにした。

## API契約

- 予定GET: `/api/admin/scenario/2nd3rd`
- 必須パラメータ: `venue=10&course=1&first=1&second=2&method=全体&scope=player&player_reg=1234&stage=before`
- `scope=venue` の場合は `player_reg` を送らない。会場別平均を**本人実績として自動代替しない**。
- `stage=after` は展示後元データの突合がないので拒否。2着別3着の公表値は現状は**2023年以降の全期間ではない**。
- ログイン認証: `Authorization: Bearer ...` は**既存のBRC認証サービスでサーバー側検証して初めて有効**。Token内のメールアドレス、HTML内の `BRC_ADMIN_ACTIVE`、`admin=true` パラメータ等は許可条件にしない。
- Token確認後にのみWorker内の**非公開D1/KVなどのデータ結合**を読む。GitHub Pagesの静的JSONやINDEX内への埋め込みは管理者限定の秘密保護にはならない。
- エラー応答は `no-store` とし、BRCログイン情報の生の値や詳細な障害ログをブラウザーへ出さない。

## なぜINDEXだけでは完成しないのか

現行INDEXの管理者表示判定は画面表示の制御です。開発者ツール等で変えられるため、**研究用集計値を本当に管理者だけへ配信したい場合、Worker側で認証が必須**です。

GitHub ActionsのArtifactsは**非公開の秘密保存場所とは見なさない**でください。今までの研究用マトリックスやオフラインプレビューはレビュー目的で生成していますが、管理者限定機能の正式な安全なデータ配信場所ではありません。

## 本番移行の未解決条件（自動テスト成功と混同しない）

1. BRCが**実際に使用する**ログイン認証の署名・期限・権限検証コードを確認し、Workerの `verifyBearerToken` に接続（期限切れ、一般会員、管理者の公開表示切替も否定試験）。
2. Cloudflareの**実際の管理者向け非公開読み取りバインディング**を用意し、`loadPrivateMatrix` に接続。現状はいずれも未接続。
3. 本体INDEXの `renderPlayerScenario` / `BRC_ADMIN_ACTIVE` / `brc-admin-public-view` という**確認済みの既存表示位置**へAPIクライアントを接続。元の着率・予測・買い目を変更しない。
4. バックエンドから本番同等データで母数・勝者実進入・選手本人/会場全体の一致を読戻し検証し、PC・スマホ・PWAで一般ユーザーへの露出がないか確認。
5. Operatorが本番承認するまで**main / 本番INDEX / KV / Worker を変更しない**。画面・APIどちらも本番導入済みと表記しない。

## 公式Kの現在の検証範囲

合計377日・58,056R、N≥5の条件付き研究セル2,031件。うち会場1901セル、選手固有130セル（105選手）。2023-01-01〜2026-10-23の1392日のうち**1015日が未収録**。真TimeXの「絶対帯別着順実績」や展示後データの欠損とは独立した案件。

このドキュメントとAPI・クライアントは **Draft PR #2 の研究限定**です。


## 2026-10-24 追記：本体ソースに一致するログイン連携候補

確認元はBRC本体INDEX SHA256 7a4e6bd63fa576587851fc5c0d5e886827b9da6e716bd4567b6b74ac8ffefe39（2026-10-24）。認証秘密・会員情報は取得・記録していない。

- INDEX 8375付近の brcStoreSession はSupabase access_token・refresh_token・期限を保持する。
- INDEX 8440付近の brcEnsureFreshSession は1DAYのJST日付期限とアクセストークン更新をチェックする。
- INDEX 8454付近の brcGetUser はSupabase REST /auth/v1/user をベアラートークン付きで呼ぶ。
- INDEX 8466付近の brcCheckMembership は同じアクセストークンを用いて既存BRC API https://brc-api.sk48159212.workers.dev/ の authorized === true を確認する。
- INDEX 8658付近の brcIsAdminUser はブラウザ側メール比較であり、管理者APIを許可する証拠に使わない。

追加候補:
- workers/brc_scenario_supabase_member_auth_candidate.mjs: Supabase本人確認と既存BRC API会員確認が両方成功し、かつWorker側で秘密設定した管理者SupabaseユーザーUUIDに一致する場合だけ管理者として許可する。メール比較や自己申告ロールは拒否。
- workers/brc_scenario_index_session_adapter_candidate.mjs: 既存 brcEnsureFreshSession を使用。管理者・会員・公開表示モードを検査してからトークン取得。新規Cookie/localStorage管理なし。
- workers/brc_scenario_23_admin_client_candidate.mjs: ログアウトや選択切替後の古い非同期結果を破棄するためgeneration/invalidateを実装。

本番条件: 管理者の正しいSupabaseユーザーUUIDをWorker secretとして運営者が設定し、Supabase公開可能なpublishable keyをBRC既存の設定から注入。Worker内でのみ非公開D1/KVの研究行列を読むこと。現在のリポジトリには既存のbrc-api Worker本体実装が無いため、そのルートへの結線、権限情報の本番確認、非公開データ読戻しは**未完成**。研究用の上記ファイルを直接本番にデプロイしない。模擬認証テストの成功を本番認証の証拠としない。


## 2026-10-24 追加：非公開KV読戻しアダプターの検証

- `workers/brc_scenario_23_private_loader_candidate.mjs` を開発ブランチに追加。Workerにのみ渡される **非公開KVバインディング** から固定キー `BRC_SCENARIO_23_RESEARCH_PRIVATE_V1` を読む候補で、GitHub Pages/公開URLへの代替取得は行わない。
- 原本マトリックスのUTF-8テキストに対する事前固定 **SHA-256** が不一致ならデータを返さない。想定外のソース公開状態・欠落した研究行・権限未確認のセッション識別子も保留。
- `workers/test_brc_scenario_23_private_loader_candidate.mjs` に、原本一致・改ざん・不正JSON・不正公開フラグ・バインディング停止のテストを追加。
- 現時点でKVの**実際のバインディング名・キー投入・SHA-256固定値は未設定**。本番のログイン認証も未接続。これは動く設計を検査するオフラインの候補であり、Cloudflare上で読戻しが成功した意味ではない。
- Worker・INDEX・KV のデプロイ、会員の着率変更、研究JSONの一般公開は実施していない。


## 2026-10-24 追補：公開Actionsへの研究マトリックス添付停止・非公開KV原本検査

- GitHub Actions run [#193](https://github.com/boatresearchclub/database2/actions/runs/40062277134) で**新しい研究原本の完全性検査に成功**。集計 58,056R / 377日 / 条件付き確率 2,031セル（会場1,901・本人130・105選手）。
- 非公開KV登録候補の原本JSONは**1,132,967 bytes**。その**完全に変更していないUTF-8生バイト**のSHA-256は `f32d06191e89418f209812d4ef882a81746f9952bfb0b8935077144de8bad6a1`。正確なファイルへの照合であり、改行や整形を変えると値は変化する。ソースが追加更新されれば再生成する。
- 検査には、公式Kの非重複日付区間・日付数、完備R総数、1→2→3の候補4艇の件数・母数一致、場全体/本人データの重複防止、偽の全期間・展示後・本番承認状態の拒否を含む。
- `scripts/brc_scenario_private_kv_review_manifest.py` は**読取専用**で、ハッシュ・件数・日付・保留判定を `brc_scenario_private_kv_review_manifest.json` に出力する。**原本の選手別データを成果物に含めない**。
- リポジトリが公開であることを踏まえ、GitHub Actionsのアップロード対象から **公式Kの研究マトリックスJSON、選手別表示用JSON、実績内包の単体オフラインHTML** を除外。 `scripts/test_scenario_public_artifact_gate.py` が将来の再追加を拒否。公開してよいハッシュ・日付・件数等のレビュー情報は継続して保存する。
- 以前の公開GitHub Actionsの一部成果物に研究マトリックスが含まれていた事実は**今回の変更で遡って無効にならない**。既存成果物を消去した/秘密保護済みだとは主張しない。今後の保管場所は実際の認証付き非公開KV等に限定する。
- **公開・投入判定は HOLD_NO_PUBLICATION**。本番Workerに `verifyBearerToken` と `loadPrivateMatrix` を実結合し、匿名/一般会員のネットワーク拒否、KV実書込・SHA読戻しが成功するまで本番投入しない。INDEX / Worker / KV / 購入者の予測画面には変更を加えていない。


## 2026-10-24 13時台追加：実際のBRC認証・会員判定・KVの統合候補

- `workers/brc_scenario_23_integrated_candidate.mjs`: 既存BRC Workerの**信頼済み内部会員判定コールバック**を必須とし、Supabase `/auth/v1/user`、許可済み管理者UUID、会員有効判定、固定キーの非公開KV SHA-256検査、正確な2着別3着率ルートを**ひとつの読取処理候補**として接続。現在のBRC API Worker自身へのHTTP自己呼出しを避けるため、会員判定callbackの注入が欠けたら初期化を拒否。
- `workers/test_brc_scenario_23_integrated_candidate.mjs`: 統合の**8件**を実行。正規管理者の本人条件、一般/匿名/第三者の拒否、会員失効、KV改ざん/停止、展示後拒否、本人と会場の条件分離をテスト。
- GitHub Actions `BRC Four-Workstream Source Gates` [run #198](https://github.com/boatresearchclub/database2/actions/runs/40062995560) で**統合8/8成功・全ジョブSUCCESS**。これはダミーSupabase応答と模擬プライベートKVでの契約テストであり、**本番Workerの実認証・実KV読戻しではない**。
- 現行非公開KV投入候補の研究用原本照合値は `f32d06191e89418f209812d4ef882a81746f9952bfb0b8935077144de8bad6a1`（1,132,967 bytes; 58,056R/377日/2,031セル）。内容を更新する際はSHAを再発行し、古い値で不一致なら公開を停止する。
- 本番向けに未解決なのは、**元のBRC Worker認証・会員判定のソースコードと実バインディングへの挿入**、運営者管理UUIDの秘密設定、許可ユーザーの実ネットワーク認証、一般ユーザーの実拒否、KVの原本を配置して読戻すこと。GitHub `database2` には元Worker実装が無いため、開発ブランチだけで完了させたとは言えない。
- 今回はBRC main/公開INDEX/Worker/KV/予測/買い目を変更していない。研究JSONのGitHub Actions新規公開添付を停止する既存ゲートも維持。


## 2026-10-24 追加：実K全条件セル照合とPython/JS端数修正

- `workers/brc_scenario_23_full_k_offline_audit.mjs` を開発ブランチへ追加。研究用原本 **58,056R / 377日 / 2,031条件セル / 1,132,967 bytes** を GitHub Actions runner に一時生成し、固定 SHA-256 と照合したのち、研究JSONをメモリ上の**模擬非公開KV**としてロード。匿名/一般ユーザー拒否、管理者仮認証時の本人・場別数値、未検証展示後拒否、KV改ざん時の拒否を原本データで確認。公衆Artifactへ元JSONを添付しない。
- [GitHub Actions #214](https://github.com/boatresearchclub/database2/actions/runs/40063687660) SUCCESS。原本JSON全 2,031条件セル、合計**8,124艇別3着率**をチェックし、数値一致を確認。
- Python `round(100*n/N,1)` と JavaScript `Math.round(...)/10` は、厳密に中間値になる境界で端数処理が異なる。原本では**65件の艇別率**が古いJS丸め式と異なっていた。これを誤って不一致・503扱いしないよう、`workers/brc_scenario_23_percent.mjs` に整数演算による **round half to even** を追加。Worker読込API、ブラウザクライアント、管理者QA INDEXブリッジ側の率照合を修正し、2つの丸め回帰試験と原本全率検査に成功。
- 念のため「丸め境界が実際に生じている元データの1条件セル」を丸ごと模擬KV APIへ通す試験も追加（追加CI検証対象）。これは小さいサンプルだけのテストではなく実Kの検証済み個票をそのまま利用。
- **本番Work​er、実ログイン、KV実読戻し、INDEX配布への接続は実施していない**。全件照合の成功は本番認証と完全2023以降履歴の成功を意味しない。従来の `HOLD_NO_PUBLICATION` を維持。

# 新TimeX v3｜管理者ログインの422エラー調査・引継ぎ（2026-10-24）

**現状判定: STAGING_INGEST_ACKNOWLEDGED / AUTHENTICATED_V3_READBACK_UNVERIFIED**  
**本番導入: HOLD**。管理者用v3画面は存在しても、`v3Verified:true` の実計算結果は未確認。一般利用者には従来TimeX v2を維持する。

## 今回、具体的に確認した事実

- mainブランチのActions [2026-10-24 JST午後相当のStage実行 #40063647802](https://github.com/boatresearchclub/database2/actions/runs/40063647802) のログに `status: STAGE_ACK_RECEIVED_KV_READBACK_PENDING`, `published:168`, `races:168`, `approved_venues:14`, `eligible_venues:14`, `coverage:FULL_SUPPORTED` を確認。
- 当日早い時間の [run #40045207339](https://github.com/boatresearchclub/database2/actions/runs/40045207339) も同じ公式番組SHA-256 `2af4da58e75fba2aa2b5ecc55d0a16bf4aca07a0726dac6497042341be7c1bc5` と、同じ168Rの保存受付を報告。
- **これはWorkerが168Rを受け付けたというACK** であり、KVにその168Rの各キーが残っている・`/predict-timex-v3` から読める・v3の着率が計算できるという証拠ではない。168R×2回を336Rと数えない。
- 前日の [公開診断 #39918569001](https://github.com/boatresearchclub/database2/actions/runs/39918569001) では、未認証の `GET /stage-context-presence` と `POST /predict-timex-v3` はどちらもHTTP 401 (`not_logged_in`) 。正しく認証保護されている可能性はあるが、実際の管理者認証後422はこの検査では再現できない。
- BRCの管理者診断履歴には `admin:true`, `v3Verified:false`, `workerHttp:422`, `workerStatus:unavailable`, `displayedRates:既存TimeX v2（参考）` があった。これを**v3稼働中とは扱わない**。

## ここまで開発ブランチで実装した追加の診断候補

1. `workers/brc_v3_admin_stage_readonly_probe_candidate.mjs`：既存BRC `brcEnsureFreshSession()` 等で取得した短命の認証済みトークンを、固定v3 Workerの **GET /stage-context-presence** にのみ使用するコンポーネント。管理者画面＋会員有効＋公開表示OFFの場合に限る。JWT、メール、選手成績やWorkerの任意文字列をログ／出力しない。POST予測・保存・KV書換え無し。404/422/401/403/503を別のコードへ分類。HTTP 200でも `v3Verified:false` を維持。
2. `workers/brc_v3_stage_context_readback_route_candidate.mjs`：既存Workerへ後で組み込む **管理者認証済み・非公開KV存在確認** のGETルート候補。現在の本物のWorker認証関数と**実際のKVの保存キー形式**を呼出元から注入できなければ起動しない。存在真偽だけを返し、モデル係数・選手情報・元の確率は返さない。単独デプロイ不可。
3. 上記の偽ログイン／公開表示／トークン失効／KV読込失敗／404・422・503／データ漏えいを検査するNodeテスト。 [Actions：BRC V3 Admin Readback Diagnosis](https://github.com/boatresearchclub/database2/actions/runs/40073646753) が成功。**ダミー認証・ダミーKVのテストであって本番readbackの証明ではない**。

## 次に実際のCloudflare Workerで実施すべき検査（管理者のみ）

- 本番と区別したステージングの `brc-timex-v3-test` の**実デプロイWorkerソース**を入手し、`/ingest-race-context` が書くKV名前空間・キー書式と、`/predict-timex-v3` が読むKV名前空間・キー書式の一致を確認する。
- 実際に保存受付済みだった2026-10-24の適格レース1件について、**同一の日付・場コード・レース番号で、管理者認証付きの存在読戻し**を行う。保存確認がない場合は計算には進まず `context_missing` / `KV_READBACK_UNAVAILABLE` を区別する。
- 保存済みなら、そのレースの公式6艇登録番号、会場種別/グレード、進入、オリジナル展示（6艇のTimeX関連数値）を確認し、計算側の入力スキーマ（必須キー）・モデル係数を**Worker内部でのみ**検証する。診断外部応答には短い理由コードだけを返す。
- `/predict-timex-v3` の**認証後実計算**が成功し、6艇の1着・2着・3着・3連対率が既存画面から正しく読めることを確認後に初めて、管理者側で `v3Verified:true` へ昇格する。AI予測/狙い目/BRC BRAINなどの整合も別途回帰検証する。
- v3が失敗するレースでは**管理者も従来v2参照へ安全に戻す**。一般会員のv2、出走データ、事前1着率、TimeX以外の予測・買い目は改変しない。

## 現在のボトルネック

接続済みGitHubの `database2` 等には**実際のv3 Worker本体コードが見つからない**。研究ブランチだけでは本物のKV結線や422の原因を修正できない。Cloudflare Workers上で稼働しているコード／認証依存・バインディングを照合する必要がある。

**管理者でも現状「確実にv3使用中」と断言できない**。本番Worker・INDEX・KVのデプロイや秘密鍵送信は今回行っていない。


## 2026-10-24 実Workerソース照合後の訂正・追加結果

- 過去のBRC Libraryアップロード `brc-timex-v3-admin-stage.js`（2026-10-12）と、既存の `BRC_TimeX_v3_Worker_422_Diagnostic_Patch.js` を発見し、422を返す実装条件を確認した。Libraryに保管されていることは**現在デプロイ中のWorkerとバイト単位で一致する証拠ではない**。これらのモデル係数を研究用GitHub公開ブランチへ複製しない。
- 実際の公開コードでは、対象APIは**管理者認証後の `POST /predict-timex-v3`** で、入力は `{date,venue_code,race_no}`。以前設計していた `GET /stage-context-presence` は2026-10-12の保存済みWorkerソースにはルートが**存在しない**。そのGETを頼りに現在のWorkerのKV状態を断定しない。既存の保護されたKV存在確認GETは、Worker本体へ追加して初めて使用可能になる。
- 保存済みWorkerソースの422条件には、JST当日付の不一致、`brc:race_context:{date}:{venue_code}:{race_no}` のKV欠落・無効、`BRC_LIVE_SERVICE` 経由の展示APIが2xxでない、展示API JSON不正、内部4指標計算失敗がある。展示6艇・進入・TimeX完全性不足は条件により`excluded` 200となるため「確率0%」として扱わない。
- Libraryの既存422診断パッチには `reason=date_not_today_jst`, `race_context_missing`, `race_context_invalid`, `live_service_http_error`（`upstream_http`）、`live_service_invalid_json`, `metrics_failed` が実装済み。**ただし実際にそのパッチがデプロイされているか未確認**。未デプロイなら422応答は従来の `status=unavailable` のみである可能性がある。
- 現在のAPI契約を直接検査するため、`workers/brc_v3_admin_predict_diagnostic_candidate.mjs` を追加。BRC既存の `brcEnsureFreshSession()` で取得したトークンだけを使い、固定ステージングへ**1回だけ**POSTする。管理者表示でない場合は認証情報を取得せず、HTTP422の安全な短縮理由コードだけを保持し、JWTや予測ベクトルを記録しない。成功時は1/2/3/3連対率の6艇×4指標を検算する。**4指標API正常応答だけでは実際のINDEXへのv3適用を証明できない**。
- 2026-10-24の168R/14会場のステージング受付に対し、独立した公開展示APIを14会場×1R/6R/12Rの計42RでGET確認した。**HTTP200＋6艇数値あり35R、HTTP404 7R**。[CI #40074480217](https://github.com/boatresearchclub/database2/actions/runs/40074480217) 成功。後半Rの展示前404は正常な場合もある。**同一レースがWorkerの内部サービスバインディングでも404なら、422の `live_service_http_error` を直接説明する**。公開APIの200から内部バインディングの成功までは推定しない。
- 管理者用POST契約の負ケース、各422理由、4指標整合性の模擬テストは [BRC V3 Admin Readback CI](https://github.com/boatresearchclub/database2/actions/runs/40074291654) 成功。実際の管理者JWTを保存したりログへ出したりする検証はしていない。 **BRC本番INDEX/Cloudflare Worker/KVは未変更**。

### 実稼働の解放条件

Cloudflare Dashboardの**現在のWorkerソース**とバインディング (`BRC_RACE_CONTEXT`, `BRC_LIVE_SERVICE`, `BRC_TIMEX_RATE_LIMITER`) をまず確認。管理者ログインで当日かつ展示確定後の1レースについて `POST /predict-timex-v3` の安全な理由コードとHTTP状態を取得。もし `live_service_http_error` + `upstream_http:404` なら同一date/venue/raceのlive Worker保存状況を修復する。もし `metrics_failed` ならWorker内部のモデル計算入力・基礎率を秘密のまま再検証。再計算成功 + 6艇×4指標整合 + INDEX反映の確認が揃うまでは `v3Verified:false` とし、管理者も旧v2参照・一般会員はv2維持。


### 公開展示API 404の具体的レース（10/24 JST16:35ごろ）

[第2回読み取り検証 #40074719721](https://github.com/boatresearchclub/database2/actions/runs/40074719721) でも 35/42=HTTP200＋6艇数値、7/42=HTTP404 の結果を再確認。404は次のレースに集中：**住之江 6R・12R、若松 1R・6R・12R、大村 6R・12R**。いずれも夜の開催を含む場のため、**展示確定前404である可能性がある**。この7Rをもって「Workerの恒常的故障」だとは判断しない。

逆に当日の**三国 1R・6R・12R**などは公開ライブAPI側でHTTP200＋6艇TimeX数値あり。管理者権限付きの**同一日・同一会場・同一レース `POST /predict-timex-v3`** を行い、もしまだ422なら `race_context_missing` / `metrics_failed` / 内部サービスのレスポンス差異などへ調査対象を絞れる。**当該管理者POSTはこの開発チャットから実行・証明できていない。**

本番BRC一般会員はv2維持。モデルの「準備完了」と「送信受付だけ成功」を混同しない。


## 2026-10-24 追加：KV原本のキーと6艇整合性を個別検査

- 過去にユーザーから提供されたWorkerコード `BRC_TimeX_v3_Worker_422_Diagnostic_Patch.js` を直接確認。非公開KVキーを**`brc:race_context:{date}:{venue_code}:{race_no}`** として生成しており、`/ingest-race-context` と `/predict-timex-v3` の両方が同じ生成関数を使用していた。保存TTLは `expirationTtl:172800`（48時間）で、昔のレースの読戻しを今日の運用確認に代用できない。**保存済みWorkerファイルとデプロイ中のWorkerの一致は未証明**。
- `workers/brc_v3_stage_kv_integrity_candidate.mjs` を追加。保存された日付・会場コード・レース番号、会場名・大会グレード・6艇のコース番号と4桁登録番号の完全性・重複を検査する。戻り値は `context_missing` / `context_invalid` / `context_valid_candidate` の**理由コードだけ**で、艇別データやモデル係数を返さない。
- `workers/brc_v3_stage_context_readback_route_candidate.mjs` はこの理由コードに対応。既存の**Cloudflare Worker管理者サーバー認証と本物のKV bindingを注入**できなければ実装できない。本番には未接続。読み込みエラーは `KV_READBACK_UNAVAILABLE` で区別。
- Node で **12 + 10 + 7 + 6 = 35件**の安全性・API契約テストが成功。GitHub Actions [#40078622850](https://github.com/boatresearchclub/database2/actions/runs/40078622850) が SUCCESS。模擬Worker・模擬KVであり、実管理者JWTを用いたテストではない。
- **通常運用上の最短切り分け**は、実際の管理者画面から当日・展示確定後の同一レースに対し `POST /predict-timex-v3` を1回だけ呼ぶこと。422なら、安全な `reason`（`date_not_today_jst`, `race_context_missing`, `race_context_invalid`, `live_service_http_error`, `live_service_invalid_json`, `metrics_failed`）から原因を分ける。パッチがまだデプロイされていなければ422本文には理由コードがない可能性がある。現行WorkerのソースとKVバインディングの照合が最終的な必須作業。
- **INDEXでの管理者v3表示完了を偽装しない**。計算API成功 + 6艇×4指標の整合 + 実際の画面反映が確認されるまで `v3Verified:false`。一般利用者の旧v2を維持。本番INDEX、Cloudflare Worker、KV、D1には変更を加えていない。


## 2026-10-24 18:58 JST：実ステージングCORS検証と非公開QAの到達範囲

[PR検証Run #40084036981](https://github.com/boatresearchclub/database2/actions/runs/40084036981)で、認証なし・保存なしの**OPTIONSプリフライト**を2つのBRC既知オリジンから模擬し、稼働中のステージングWorkerに問い合わせた。

| 送信Origin | ステータス | POST/Authorization/CORSの許可 |
| --- | --- | --- |
| `https://brcdatabase.pages.dev` | HTTP 204 | 許可 |
| `https://boatresearchclub.github.io` | HTTP 403 | 拒否 |

実際の保存済みv3 Workerには、許可Originの既定値 `https://brcdatabase.pages.dev` と環境変数 `BRC_TIMEX_V3_ALLOWED_ORIGIN` がある。今回の実測は既定Pagesホストからの通信可能性を支持する。ただし**現在のWorkerコードとLibrary保管ソースの同一性、ユーザーが使っている実際のBRCアクセス元、管理者POSTの成功、422の原因は未確認**。

**実装改善：**

- `scripts/brc_v3_stage_cors_preflight_probe.py`：Authorization/JWTの値を使わずOPTIONSのみ送信し、上記2オリジンのステータスと許可ヘッダーをサニタイズして保存。`scripts/test_brc_v3_stage_cors_preflight_probe.py`がno token/no POSTの境界をテスト。どちらもモデルやKVへアクセスしない。
- `scripts/brc_v3_admin_index_qa_bridge.js`：422の公開可能な理由コード（KV欠落、公開展示API 404、Workerの内部計算失敗、日付不一致など）を固定された日本語ガイドへ変換する。**外部Workerが返す任意テキストは表示しない**。
- 同QAブリッジは、診断を実行するページが現在確認済みの `https://brcdatabase.pages.dev` 以外なら**JWT取得もWorkerへの送信も行わない**。GitHub Pages・`file://`のオフラインHTMLでボタンを押しても、そのファイルから実運用Workerへの認証付き通信は実行できない。`scripts/test_v3_admin_index_qa_dom.cjs`に拒否回帰テストを追加。これはオフラインのブラウザUI試験だけを提供し、実ステージング経路のHTTP422を再現できないことを明示するためのガードである。

**次に必要な実運用検証：** BRC本体の許可済みPagesオリジン上で、管理者セッションを保持した状態で**展示確定済みの当日レース1件のみ**実Workerへ認証付き `POST /predict-timex-v3` を実行。公開してよい短い `reason` を確認。もし422が `live_service_http_error` かつ `upstream_http=404` なら同一race/date/venueの `BRC_LIVE_SERVICE` バインディング経由の展示保存データを調べる。 `race_context_missing`なら同じWorkerに結びつく `BRC_RACE_CONTEXT` KVの有効期限とreadbackを確認。`metrics_failed`なら非公開でWorkerの4指標演算を調査する。

**本番INDEX/Worker/KV/D1は未変更。GitHubにある診断パネルは本番へデプロイせず、一般会員v2を維持。**

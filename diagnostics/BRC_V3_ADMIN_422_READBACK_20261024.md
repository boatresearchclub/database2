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

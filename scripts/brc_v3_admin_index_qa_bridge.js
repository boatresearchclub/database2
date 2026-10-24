/* BRC_V3_ADMIN_INDEX_QA_BRIDGE_V1
 * Executed only in a strict, source-hash-gated OFFLINE INDEX QA artifact.
 * It uses the embedded candidate modules. No production deploy, no data writes,
 * no v3 rate replacement, no automatic HTTP calls.
 */
const V3_PANEL_ID="brcV3AdminQAPanel";
const V3_VENUES=["桐生","戸田","江戸川","平和島","多摩川","浜名湖","蒲郡","常滑","津","三国","びわこ","住之江","尼崎","鳴門","丸亀","児島","宮島","徳山","下関","若松","芦屋","福岡","唐津","大村"];
function v3JstToday(){
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Tokyo",
   year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
 const field=k=>parts.find(x=>x.type===k)?.value;
 return field("year")+"-"+field("month")+"-"+field("day");
}
function v3AdminUi(){
 try{
  return typeof BRC_MEMBER_ACTIVE!=="undefined"&&BRC_MEMBER_ACTIVE===true&&
   typeof BRC_ADMIN_ACTIVE!=="undefined"&&BRC_ADMIN_ACTIVE===true&&
   !document.body?.classList.contains("brc-admin-public-view")&&
   !(typeof brcGetAdminViewMode==="function"&&brcGetAdminViewMode()==="public");
 }catch(_){return false;}
}
const v3Diagnostic=createIndexBrcV3AdminDiagnostic({
 ensureFreshSession:async()=>{
  if(typeof brcEnsureFreshSession!=="function")return null;
  return brcEnsureFreshSession();
 },
 readMemberActive:()=>typeof BRC_MEMBER_ACTIVE!=="undefined"&&BRC_MEMBER_ACTIVE===true,
 readAdminActive:()=>typeof BRC_ADMIN_ACTIVE!=="undefined"&&BRC_ADMIN_ACTIVE===true,
 readPublicView:()=>document.body?.classList.contains("brc-admin-public-view")===true||
   (typeof brcGetAdminViewMode==="function"&&brcGetAdminViewMode()==="public"),
 fetchImpl:(url,opts)=>fetch(url,opts)
});
let v3Busy=false;
const v3Attempted=new Set();
// Frozen, non-sensitive Japanese cause labels. Never render arbitrary
// error messages, HTTP response bodies, or private model output.
const V3_QA_CAUSES=Object.freeze({
 STAGE_JST_DATE_MISMATCH:"Worker判定の日付と日本時間の当日が一致しません",
 STAGE_KV_RACE_CONTEXT_MISSING:"公式番組の該当レースがステージングKVで見つかりません",
 STAGE_KV_RACE_CONTEXT_INVALID:"保存済み公式番組の会場・6艇情報が不整合です",
 LIVE_EXHIBITION_KV_RACE_NOT_FOUND:"展示APIに同じレースの保存データがありません（展示前か取得失敗）",
 UPSTREAM_LIVE_API_FAILURE:"展示APIへのWorker内部接続が失敗しました",
 UPSTREAM_LIVE_API_JSON_INVALID:"展示APIからのデータ形式が不正です",
 V3_MODEL_FOUR_METRIC_COMPUTATION_FAILED:"Worker内部の1・2・3・3連対率計算に失敗しました",
 UNDIAGNOSED_422_CHECK_WORKER_PATCH:"Workerの422詳細理由が取得できません。診断パッチの反映状況を確認してください",
 FOUR_METRIC_SERVER_RESPONSE_VALID:"APIの6艇×4指標は整合しています。BRC画面反映は未確認です",
 REQUIRES_FOUR_RATE_VALIDATION:"APIはreadyですが6艇×4指標の整合確認に失敗しました",
 EXHIBITION_OR_ENTRY_EXCLUDED:"展示6艇・進入固定などの条件不足で計算対象外です",
 WORKER_ADMIN_IDENTITY_DENIED:"Worker側で管理者権限を確認できません",
 WORKER_FORBIDDEN_OR_CORS:"Workerのアクセス元または権限の設定を確認してください",
 SESSION_EXPIRED_OR_UNAUTHENTICATED:"管理者セッションの期限切れ・未認証です",
 SESSION_UNVERIFIED:"BRCのログイン状態を確認できません",
 ADMIN_VIEW_REQUIRED:"管理者専用表示でのみ診断できます",
 V3_RATE_LIMITED:"Workerの実行回数制限に達しました",
 PREDICT_ROUTE_NOT_INSTALLED:"Workerのv3予測ルートが見つかりません",
 V3_WORKER_OR_UPSTREAM_INTERNAL_FAILURE:"Workerまたは展示情報取得先のサーバーエラーです",
 NETWORK_OR_CORS_FAILURE:"Worker通信に失敗しました（ネットワークまたはCORS）",
 UNEXPECTED_V3_STATUS:"予期しないWorker応答です",
 UNEXPECTED_STAGE_RESPONSE:"予期しないHTTP応答です"
});
function v3QaCause(phase){
 return Object.prototype.hasOwnProperty.call(V3_QA_CAUSES,phase)
   ?V3_QA_CAUSES[phase]:"未分類の診断結果です";
}
function v3Element(tag,label){
 const el=document.createElement(tag);
 if(label!==undefined)el.textContent=label;
 return el;
}
function v3Mount(){
 const old=document.getElementById(V3_PANEL_ID);
 if(!v3AdminUi()){old?.remove();return false;}
 const pane=document.getElementById("playerScenarioDetail");
 if(!pane)return false;
 if(old&&pane.contains(old))return true;
 old?.remove();
 const host=v3Element("section");host.id=V3_PANEL_ID;
 host.setAttribute("data-brc-v3-qa-only","true");
 const title=v3Element("h3","新TimeX v3｜管理者診断");
 const note=v3Element("p","本番未適用。展示確定後の当日レースを1回だけ診断します。一般会員の着率は変更しません。");
 const row=v3Element("div");row.className="brc-v3-qa-row";
 const date=v3Element("input");date.type="date";date.value=v3JstToday();
 const venue=v3Element("select");
 V3_VENUES.forEach((name,i)=>{
  const code=String(i+1).padStart(2,"0");
  if(code==="03")return;
  const option=v3Element("option",name);option.value=code;venue.appendChild(option);
 });
 const race=v3Element("select");
 for(let i=1;i<=12;i++){const option=v3Element("option",i+"R");option.value=String(i);race.appendChild(option);}
 const run=v3Element("button","管理者として1回診断");
 run.type="button";
 const status=v3Element("p","未実行");status.setAttribute("role","status");
 for(const el of [date,venue,race,run])row.appendChild(el);
 for(const el of [title,note,row,status])host.appendChild(el);
 run.addEventListener("click",async()=>{
  if(!v3AdminUi()){host.remove();return;}
  if(v3Busy)return;
  const selected={date:date.value,venue_code:venue.value,race_no:Number(race.value)};
  if(selected.date!==v3JstToday()){
   status.textContent="当日以外のレースは診断しません。";return;
  }
  const key=[selected.date,selected.venue_code,selected.race_no].join("|");
  if(v3Attempted.has(key)){
   status.textContent="このレースはこの画面で診断済みです。重複送信はしません。";return;
  }
  v3Attempted.add(key);
  v3Busy=true;run.disabled=true;status.textContent="検証中（予測には使用しません）";
  try{
   const result=await v3Diagnostic.check(selected);
   if(!v3AdminUi()||!host.isConnected){host.remove();return;}
   // Only report the validated diagnostic phase and numeric HTTP status.
   // Never show raw Worker output, access tokens or per-boat vectors.
   const phase=typeof result?.phase==="string"&&/^[A-Z0-9_]{1,90}$/.test(result.phase)
     ?result.phase:"UNKNOWN_DIAGNOSTIC_RESULT";
   const http=Number.isInteger(result?.http)?result.http:"-";
   status.textContent="HTTP "+http+"｜"+phase+"｜"+v3QaCause(phase)+"｜本番未適用";
  }catch(_){
   if(v3AdminUi()&&host.isConnected)status.textContent="診断を安全に中止しました。";
  }finally{
   v3Busy=false;
   if(host.isConnected&&v3AdminUi())run.disabled=false;
  }
 });
 const cssId="brc-v3-admin-qa-style";
 if(!document.getElementById(cssId)){
  const style=v3Element("style");
  style.id=cssId;
  style.textContent="#brcV3AdminQAPanel{margin:12px 0;padding:12px;border:1px solid #45627d;border-radius:12px;background:#112033;color:#edf6ff;font-size:12px}"+
   "#brcV3AdminQAPanel h3{font-size:15px;margin:0 0 6px}"+
   "#brcV3AdminQAPanel p{margin:6px 0}"+
   "#brcV3AdminQAPanel .brc-v3-qa-row{display:flex;gap:6px;flex-wrap:wrap}"+
   "#brcV3AdminQAPanel select,#brcV3AdminQAPanel input,#brcV3AdminQAPanel button{background:#152c44;color:#fff;border:1px solid #536c81;border-radius:7px;padding:6px;max-width:100%}";
  document.head.appendChild(style);
 }
 pane.appendChild(host);
 return true;
}
window.BRC_V3AdminQA={
 mount(){try{return v3Mount();}catch(_){return false;}},
 unmount(){document.getElementById(V3_PANEL_ID)?.remove();},
 readyForProduction:false,publicVisible:false
};
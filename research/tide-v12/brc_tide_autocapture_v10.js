/* BRC TIDE V10 - ADMIN SHADOW AUTO-CAPTURE
 * Read-only to BRC forecasts/TimeX. Captures earliest valid predeadline record
 * for the CURRENTLY OPEN eligible race into browser localStorage. No server sync.
 * The user's PC clock is not independent timestamp evidence.
 */
(function(root){
'use strict';
const bridge=root.BRCTideAdminBridgeV7;
if(!bridge)return;
const STORAGE_KEY='brc_tide_v10_first_prerace_snapshots';
const VERSION='BRC_TIDE_V10_AUTOCAPTURE_20261023';
const MAX_ROWS=1500;
const CSV_FIELDS=['observed_at','venue','race_no','race_date','deadline_or_start_time','v3_live_fingerprint',
 'study_recorded_before_deadline','time_kind','time_stability_window_min','port_name','first_course_boat_no',
 'tide_name','tide_phase','tide_level_cm','sample_n','baseline_in_escape_pct','conditional_in_escape_pct',
 'study_shift_pt','v3_display_sum','source',
 ...Array.from({length:6},(_,i)=>'displayed_v3_boat_'+(i+1)),
 ...Array.from({length:6},(_,i)=>'tide_study_boat_'+(i+1)),'winner_boat_no'];
const guard=(ok,msg)=>{if(!ok)throw new Error(msg)};
function blank(){return {version:VERSION,records:{}};}
function load(storage){
 const v=storage.getItem(STORAGE_KEY);if(!v)return blank();
 const obj=JSON.parse(v);
 guard(obj && obj.version===VERSION && obj.records && typeof obj.records==='object' && !Array.isArray(obj.records), '保存形式が不明です（安全停止）');
 guard(Object.keys(obj.records).length<=MAX_ROWS,'保存上限超過（安全停止）');
 return obj;
}
function appendFirst(storage, key, record){
 guard(/^\d{4}-\d{2}-\d{2}\|\d{2}\|(?:[1-9]|1[012])$/.test(key),'レース識別子が不正です');
 guard(record && record.study_recorded_before_deadline===true && record.time_kind==='brc_deadline_proxy','締切前の正式参照記録だけ保存できます');
 const obj=load(storage);
 if(Object.prototype.hasOwnProperty.call(obj.records,key))return {status:'duplicate',count:Object.keys(obj.records).length};
 const count=Object.keys(obj.records).length;
 guard(count<MAX_ROWS,'記録上限です。先にCSVを書き出してください');
 // No clock- or content-based replacement of earlier observations.
 obj.records[key]=record;
 storage.setItem(STORAGE_KEY,JSON.stringify(obj));
 const saved=load(storage);
 guard(Object.prototype.hasOwnProperty.call(saved.records,key),'保存確認に失敗しました');
 return {status:'saved',count:count+1};
}
function rows(storage){return Object.values(load(storage).records).sort((a,b)=>a.observed_at.localeCompare(b.observed_at));}
function csvEscape(x){return '"'+String(x===undefined||x===null?'':x).replaceAll('"','""')+'"';}
function toCsv(items){return '\ufeff'+CSV_FIELDS.map(csvEscape).join(',')+'\r\n'+items.map(r=>CSV_FIELDS.map(k=>csvEscape(r[k])).join(',')).join('\r\n')+'\r\n';}
function makeRecord(snap, result, cutoff, capturedAt){
 guard(snap && snap.status==='ok','照合済みの現在レースが必要です');
 guard(result && result.status==='ok' && result.shadow?.result?.status==='ok','潮汐試算が成功していません');
 guard(result.stabilityMinutes>=10 && result.referenceKind==='deadline_or_manually_entered_time','潮汐10分安定条件がありません');
 guard(cutoff && cutoff.status==='ok' && cutoff.value.slice(0,10)===snap.day,'対象締切の取得不一致');
 const now=Date.parse(capturedAt);
 guard(Number.isFinite(now) && now<Date.parse(cutoff.value+':00+09:00'),'締切後に取得した値は保存できません');
 const {tide}=result.shadow;
 const prediction=result.shadow.result;
 const r={observed_at:capturedAt,venue:snap.venueName,race_no:snap.raceNo,race_date:snap.day,
   deadline_or_start_time:cutoff.value,v3_live_fingerprint:snap.raceFingerprint,
   study_recorded_before_deadline:true,time_kind:'brc_deadline_proxy',time_stability_window_min:10,
   port_name:result.portName||'',first_course_boat_no:snap.firstCourseBoat,
   tide_name:tide.tideName,tide_phase:tide.phase,tide_level_cm:tide.cm,
   sample_n:prediction.condition.n,baseline_in_escape_pct:prediction.condition.avg,
   conditional_in_escape_pct:prediction.condition.p,study_shift_pt:prediction.shiftPt,
   v3_display_sum:snap.displayTotal,source:'v3_display_rounded_normalized',
   winner_boat_no:''};
 for(let i=0;i<6;i++){
   r['displayed_v3_boat_'+(i+1)]=snap.displayedPct[i];
   r['tide_study_boat_'+(i+1)]=prediction.after[i];
 }
 return r;
}
function hasAuth(diag,doc){return bridge.showIfAuthorized(diag,doc) && diag.v3Verified===true && diag.sameRaceLive===true && diag.strictExhibition===true;}
const core=Object.freeze({STORAGE_KEY,VERSION,CSV_FIELDS,appendFirst,load,rows,toCsv,makeRecord,hasAuth});
root.BRCTideAutoCaptureV10=core;
if(!root.document || typeof root.setInterval!=='function')return;
const doc=root.document;
let ui=null,pending=false,attemptKey='',attemptAt=0,cachedPayload=null,cachedVenueDay='',errorMessage='';
function diag(){try{return root.brcV3AdminDiagnostics?.()||null}catch(_){return null}}
function current(){
 const d=diag();if(!hasAuth(d,doc))return {reason:'v3未照合・管理者権限待ち'};
 const texts=Array.from({length:6},(_,i)=>doc.getElementById('predict-win-cell-'+(i+1))?.textContent||'');
 const snap=bridge.snapshot({diag:d,live:root.__currentLiveExhibition,rateTexts:texts,
   verifiedV3SameRace:root.brcV3VerifiedDetailVisible?.()===true});
 if(snap.status!=='ok')return {reason:snap.reason};
 const selectedVenue=doc.getElementById('predictRaceDay')?.value||doc.getElementById('predictVenue')?.value||'';
 const selectedRaceNo=doc.getElementById('predictRaceNo')?.value||'';
 const schedule=typeof RACE_INFO_TODAY!=='undefined'?RACE_INFO_TODAY:root.RACE_INFO_TODAY;
 const cutoff=bridge.deadlineFromRaceInfo({diag:d,raceInfo:schedule,selectedVenue,selectedRaceNo});
 if(cutoff.status!=='ok')return {reason:cutoff.reason};
 const todayJst=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
 if(snap.day!==todayJst)return {reason:'現在のJST日付と選択レースの開催日が異なります'};
 if(!bridge.nowBeforeDeadline({day:snap.day,deadline:cutoff.time}))return {reason:'締切前ではありません'};
 // 60-second buffer for in-flight responses and client clock jitter.
 const remaining=Date.parse(cutoff.value+':00+09:00')-Date.now();
 if(remaining<=60000)return {reason:'締切まで60秒以内のため自動記録しません'};
 return {snap,cutoff,identity:JSON.stringify([snap.raceKey,snap.raceFingerprint,snap.displayedPct,snap.firstCourseBoat,cutoff.value])};
}
function setStatus(){
 if(!ui)return;
 let count='—';try{count=String(rows(root.localStorage).length)}catch(e){count='記録庫エラー'}
 ui.querySelector('[data-auto-count]').textContent='ブラウザ内の事前記録: '+count+'件';
 ui.querySelector('[data-auto-message]').textContent=errorMessage||'照合済みのレースを開いている間だけ、自動で事前記録します。';
}
async function tide(snap){
 const cacheKey=snap.venueId+'|'+snap.day;
 if(cachedVenueDay===cacheKey && cachedPayload)return cachedPayload;
 const v=Object.values(bridge.VENUES).find(x=>x.id===snap.venueId);
 guard(v,'観測地点が未登録');
 const [yr,mn,dy]=snap.day.split('-');
 const url=bridge.API+'?'+new URLSearchParams({pc:v.pc,hc:v.hc,yr,mn,dy,rg:'day'}).toString();
 const controller=new AbortController();const timer=root.setTimeout(()=>controller.abort(),10000);
 try{
   const response=await root.fetch(url,{method:'GET',signal:controller.signal,cache:'no-store',credentials:'omit'});
   guard(response.ok,'潮汐API HTTP '+response.status);
   const payload=await response.json();
   guard(bridge.validateTidePort(payload,snap.venueId).status==='ok','潮汐地点を照合できません');
   cachedPayload=payload;cachedVenueDay=cacheKey;
   return payload;
 }finally{root.clearTimeout(timer)}
}
async function capture(){
 if(pending)return;
 let c=current();if(!c.snap)return;
 let existing;
 try{existing=load(root.localStorage);if(existing.records[c.snap.raceKey])return}
 catch(e){errorMessage='記録領域を確認できません: '+String(e.message||e);setStatus();return}
 const key=c.snap.raceKey;
 if(attemptKey===key && Date.now()-attemptAt<90000)return;
 attemptKey=key;attemptAt=Date.now();pending=true;errorMessage='潮汐確認中…';setStatus();
 try{
  const payload=await tide(c.snap);
  const latest=current();
  if(!latest.snap || latest.identity!==c.identity)throw Error('レース・展示・着率・締切が更新されました');
  const cmp=bridge.stableComparison({snapshotData:latest.snap,referenceJst:latest.cutoff.value,tidePayload:payload});
  if(cmp.status!=='ok' || cmp.shadow?.result?.status!=='ok')throw Error('補正なし: '+(cmp.reason||cmp.shadow?.result?.reason||'不適格'));
  // Re-validate race context and deadline immediately before first write.
  const final=current();
  if(!final.snap || final.identity!==c.identity)throw Error('記録直前にレースが切り替わりました');
  const observedAt=new Date().toISOString();
  const row=makeRecord(final.snap,cmp,final.cutoff,observedAt);
  const status=appendFirst(root.localStorage,final.snap.raceKey,row);
  errorMessage=status.status==='saved'?`${row.venue} ${row.race_no}R：締切前の潮汐試算を自動保存しました`:'同レースの先行記録を保持しています';
 }catch(e){errorMessage='記録なし: '+String(e.message||e)}
 finally{pending=false;setStatus()}
}
function saveFile(){
 try{
   if(!hasAuth(diag(),doc))throw Error('管理者ログイン中のみ出力できます');
   const data=rows(root.localStorage);
   if(!data.length)throw Error('締切前の有効な事前記録はまだありません');
   const text=toCsv(data),blob=new Blob([text],{type:'text/csv;charset=utf-8'});
   const url=URL.createObjectURL(blob),a=doc.createElement('a');
   a.href=url;a.download='BRC_TIDE_PREDEADLINE_AUTO_'+new Date().toISOString().slice(0,10)+'.csv';
   doc.body.append(a);a.click();a.remove();root.setTimeout(()=>URL.revokeObjectURL(url),5000);
   errorMessage=data.length+'件の保存済み記録をCSV出力しました（記録内容は変更しません）';setStatus();
 }catch(e){errorMessage=String(e.message||e);setStatus()}
}
function mount(){
 const d=diag();if(!bridge.showIfAuthorized(d,doc)){
  if(ui){ui.remove();ui=null}return;
 }
 const host=doc.getElementById('brc-tide-shadow-v7') || doc.querySelector('#predictResult #predictTableWrap');
 if(!host || !host.isConnected){if(ui){ui.remove();ui=null}return}
 if(ui && (!ui.isConnected || ui.previousElementSibling!==host)){ui.remove();ui=null}
 if(!ui){
  ui=doc.createElement('details');ui.id='brc-tide-autosave-v10';ui.style.cssText='margin:9px 0;padding:10px;border:1px solid #9eafc8;border-radius:9px;background:#f7faff;font-size:12px;color:#18314f';
  const summary=doc.createElement('summary');summary.textContent='🌊 潮汐V10｜締切前の自動研究記録（管理者専用）';summary.style.cssText='font-weight:700;cursor:pointer';ui.append(summary);
  const explain=doc.createElement('p');explain.textContent='対象レースが管理者画面に表示され、TimeX v3が照合済みの場合のみ記録します。アプリを閉じている間は動作しません。サーバー同期はありません。';ui.append(explain);
  const count=doc.createElement('p');count.setAttribute('data-auto-count','');ui.append(count);
  const button=doc.createElement('button');button.textContent='保存済み全レースをCSV出力';button.type='button';button.style.cssText='padding:7px 10px;border:0;border-radius:6px;background:#135bc0;color:white;cursor:pointer';button.addEventListener('click',saveFile);ui.append(button);
  const status=doc.createElement('p');status.setAttribute('data-auto-message','');ui.append(status);
  const note=doc.createElement('p');note.textContent='ブラウザの保存データは消えることがあります。早めにCSVを退避してください。勝率改善は未確認で、BRC本体の予測・買い目には反映しません。';note.style.fontSize='11px';ui.append(note);
  host.insertAdjacentElement('afterend',ui);
 }
 setStatus();
}
function poll(){try{mount();if(ui)capture()}catch(e){errorMessage='監視停止: '+String(e.message||e);setStatus()}}
function init(){poll();root.setInterval(poll,6000);root.addEventListener?.('focus',poll)}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init,{once:true});else init();
})(typeof window!=='undefined'?window:globalThis);

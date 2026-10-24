/* BRC TIDE V11: optional independent retrospective-context baseline capture.
 * Saves the existing BRC six-boat pctFloat vector BEFORE the deadline,
 * whether or not TimeX v3 is verified and whether or not the tide API is reachable.
 * DOES NOT claim pctFloat is a verified v3 forecast or a user-visible rate.
 * Stored separately from V10 / V9. No mutation of BRC calculations.
 */
(function(root){
'use strict';
const KEY='brc_tide_v11_existing_float_prerace_snapshots';
const VERSION='BRC_TIDE_V11_EXISTING_FLOAT_RESEARCH_20261023';
const MAX=3000;
const VENUES={
 '児島':'16','平和島':'04','下関':'19','福岡':'22','若松':'20','丸亀':'15'
};
const FIELDS=['observed_at','race_date','venue','venue_code','race_no',
 'deadline_jst','minutes_before_deadline','source','baseline_pct_sum','first_course_boat_no',
 'v3_verified_at_capture','live_fingerprint','race_selection_fingerprint',
 ...Array.from({length:6},(_,i)=>'existing_float_boat_'+(i+1)),
 ...Array.from({length:6},(_,i)=>'normalized_existing_boat_'+(i+1))];
const fail=reason=>({status:'skip',reason});
function jstDay(ms){return new Date(ms+9*3600000).toISOString().slice(0,10)}
function cutoff(day,hhmm){
 if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day)||typeof hhmm!=='string'||!/^\d{1,2}:\d{2}$/.test(hhmm))return null;
 const [h,m]=hhmm.split(':').map(Number);
 if(h>23||m>59)return null;
 const text=day+'T'+String(h).padStart(2,'0')+':'+String(m).padStart(2,'0');
 const epoch=Date.parse(text+':00+09:00');
 if(!Number.isFinite(epoch)||jstDay(epoch)!==day||new Date(epoch+9*3600000).toISOString().slice(0,16)!==text)return null;
 return {text,epoch};
}
function buildSnapshot({diag,live,boats,raceInfo,selectedVenue,selectedRaceNo,nowMs=Date.now(),publicPreview=false}={}){
 if(publicPreview||!diag||diag.admin!==true||diag.member!==true)return fail('管理者ログインが必要です');
 if(diag.sameRaceLive!==true||diag.strictExhibition!==true||diag.tableReady!==true)return fail('展示照合・出走表が未完了');
 const match=String(diag.selectedRace||'').match(/^(児島|平和島|下関|福岡|若松|丸亀)\s+(\d{1,2})R$/);
 if(!match)return fail('潮汐対象6会場以外');
 const [_,venue,noText]=match,no=Number(noText),code=VENUES[venue],day=String(diag.date||'');
 if(!Number.isInteger(no)||no<1||no>12||String(selectedVenue)!==venue||Number(selectedRaceNo)!==no)return fail('表示レースの選択状態が不一致');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(nowMs)||jstDay(nowMs)!==day)return fail('開催日と現在日付が不一致');
 if(!live||String(live.date||'')!==day||String(live.venue_code||'').padStart(2,'0')!==code||Number(live.race_no)!==no)return fail('展示のレース不一致');
 const c=cutoff(day,raceInfo?.[venue]?.deadlines?.[String(no)]);
 if(!c)return fail('公式番組由来の締切時刻がありません');
 const remaining=c.epoch-nowMs;
 if(remaining<=60_000)return fail('締切まで60秒以内または締切後');
 if(!Array.isArray(live.boats)||live.boats.length!==6||!Array.isArray(boats)||boats.length!==6)return fail('6艇不揃い');
 const liveBoats=new Map(),courseSet=new Set();let first=null;
 for(const r of live.boats){
   const b=Number(r.boat_no),entry=Number(r.entry_course);
   if(!Number.isInteger(b)||b<1||b>6||liveBoats.has(b)||!Number.isInteger(entry)||entry<1||entry>6||courseSet.has(entry))return fail('展示艇番・進入コースが不正');
   liveBoats.set(b,r);courseSet.add(entry);if(entry===1)first=b;
 }
 if(courseSet.size!==6||liveBoats.size!==6||!first)return fail('進入情報の不足');
 const probs=Array(6).fill(null), regs=Array(6).fill('');
 for(const b of boats){
   // Existing BRC boats.course is boat number, not actual exhibition entry course.
   const no=Number(b?.course),v=Number(b?.pctFloat);
   if(!Number.isInteger(no)||no<1||no>6||probs[no-1]!==null||!Number.isFinite(v)||v<0||v>100)return fail('既存1着率または艇番が不正');
   probs[no-1]=v;regs[no-1]=String(b?.player?.reg||'');
 }
 const sum=probs.reduce((a,b)=>a+b,0);
 if(probs.some(x=>x===null)||Math.abs(sum-100)>5||sum<=0)return fail('既存着率が合計100%と整合しません');
 const fingerprint=[day,code,no,String(live.fixed_course??''),...Array.from(liveBoats.entries()).sort((a,b)=>a[0]-b[0]).map(([n,b])=>[
    n,Number(b.entry_course),String(b.relative_diff??''),String(b.lap_time??''),String(b.status??'')].join(':'))].join('|');
 const context=[day,code,no,...regs,...probs.map(x=>x.toFixed(8)),fingerprint].join('|');
 const record={
   observed_at:new Date(nowMs).toISOString(),race_date:day,venue,venue_code:code,race_no:no,
   deadline_jst:c.text,minutes_before_deadline:remaining/60000,
   source:'existing_boats_pctFloat_not_verified_as_v3',baseline_pct_sum:sum,
   first_course_boat_no:first,v3_verified_at_capture:diag.v3Verified===true,
   live_fingerprint:fingerprint,race_selection_fingerprint:context
 };
 for(let i=0;i<6;i++){record['existing_float_boat_'+(i+1)]=probs[i];record['normalized_existing_boat_'+(i+1)]=100*probs[i]/sum;}
 return {status:'ok',key:`${day}|${code}|${no}`,record};
}
function readStore(storage){
 const raw=storage.getItem(KEY);
 if(!raw)return {version:VERSION,records:{}};
 const v=JSON.parse(raw);
 if(!v||v.version!==VERSION||!v.records||typeof v.records!=='object'||Array.isArray(v.records)||Object.keys(v.records).length>MAX)throw Error('保存庫形式が不正: 自動上書きしません');
 return v;
}
function saveFirst(storage,key,record){
 if(!/^\d{4}-\d{2}-\d{2}\|\d{2}\|(?:[1-9]|1[012])$/.test(key))throw Error('レースID不正');
 if(!record||record.source!=='existing_boats_pctFloat_not_verified_as_v3')throw Error('記録ソースが不正');
 if(record.race_date!==key.slice(0,10)||record.venue_code!==key.slice(11,13)||Number(record.race_no)!==Number(key.split('|')[2]))throw Error('レースID不一致');
 const now=Date.parse(record.observed_at),end=Date.parse(record.deadline_jst+':00+09:00');
 if(!Number.isFinite(now)||!Number.isFinite(end)||end-now<=60000)throw Error('締切前60秒超の記録ではありません');
 const db=readStore(storage);
 if(Object.prototype.hasOwnProperty.call(db.records,key))return {status:'duplicate',count:Object.keys(db.records).length};
 if(Object.keys(db.records).length>=MAX)throw Error('保存上限。CSVへ退避してください');
 db.records[key]=record;
 storage.setItem(KEY,JSON.stringify(db));
 if(!Object.prototype.hasOwnProperty.call(readStore(storage).records,key))throw Error('保存結果の読み戻し失敗');
 return {status:'saved',count:Object.keys(db.records).length};
}
function list(storage){return Object.values(readStore(storage).records).sort((a,b)=>String(a.observed_at).localeCompare(String(b.observed_at)));}
function csvEscape(v){return '"'+String(v===undefined||v===null?'':v).replaceAll('"','""')+'"';}
function exportCsv(records){return '\ufeff'+FIELDS.map(csvEscape).join(',')+'\r\n'+records.map(x=>FIELDS.map(f=>csvEscape(x[f])).join(',')).join('\r\n')+'\r\n';}
const api=Object.freeze({KEY,VERSION,FIELDS,cutoff,buildSnapshot,readStore,saveFirst,list,exportCsv});
root.BRCTideBaselineCaptureV11=api;
if(!root.document||typeof root.setInterval!=='function')return;
const doc=root.document;
let ui=null,lastMsg='';
function isAdmin(d){return d?.admin===true&&d?.member===true&&!doc.body?.classList.contains('brc-admin-public-view')}
function selected(){
 const d=typeof root.brcV3AdminDiagnostics==='function'?root.brcV3AdminDiagnostics():null;
 if(!isAdmin(d))return fail('管理者認証待ち');
 const raceInfo=(typeof RACE_INFO_TODAY!=='undefined'?RACE_INFO_TODAY:root.RACE_INFO_TODAY);
 return buildSnapshot({diag:d,live:root.__currentLiveExhibition,
   boats:root.__predictBoatsCurrent,raceInfo,
   selectedVenue:doc.getElementById('predictRaceDay')?.value||doc.getElementById('predictVenue')?.value||'',
   selectedRaceNo:doc.getElementById('predictRaceNo')?.value||'',
   nowMs:Date.now(),publicPreview:doc.body?.classList.contains('brc-admin-public-view')});
}
function exportFile(){
 try{
   const d=root.brcV3AdminDiagnostics?.();if(!isAdmin(d))throw Error('管理者モードが必要です');
   const saved=list(root.localStorage);if(!saved.length)throw Error('記録はまだありません');
   const csv=exportCsv(saved),url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
   const link=doc.createElement('a');link.href=url;link.download='BRC_TIDE_V11_EXISTING_BASELINE_'+jstDay(Date.now())+'.csv';doc.body.append(link);link.click();link.remove();
   root.setTimeout(()=>URL.revokeObjectURL(url),5000);
   lastMsg=`既存TimeX系の締切前記録${saved.length}件をCSV保存しました。V3用CSVには混ぜないでください。`;
 }catch(e){lastMsg='CSV出力停止: '+String(e.message||e)}
 refresh();
}
function refresh(){
 if(!ui)return;
 let count='—';try{count=list(root.localStorage).length}catch(e){count='記録庫の確認が必要'}
 ui.querySelector('[data-tide-v11-status]').textContent=`記録数 ${count}件。`+lastMsg;
}
function mount(){
 const d=root.brcV3AdminDiagnostics?.();if(!isAdmin(d)){
   if(ui){ui.remove();ui=null}return;
 }
 const host=doc.getElementById('brc-tide-autosave-v10')||doc.getElementById('brc-tide-shadow-v7')||doc.querySelector('#predictResult #predictTableWrap');
 if(!host||!host.isConnected){if(ui){ui.remove();ui=null}return;}
 if(ui && (!ui.isConnected||ui.previousElementSibling!==host)){ui.remove();ui=null}
 if(!ui){
   ui=doc.createElement('details');ui.id='brc-tide-baseline-v11';
   ui.style.cssText='margin:8px 0;padding:10px;border:1px solid #b9c9dc;border-radius:8px;background:#fff;font-size:12px;color:#28324a';
   const title=doc.createElement('summary');title.textContent='🌊 潮汐V11｜既存TimeX系の事前記録（管理者研究）';title.style.fontWeight='bold';ui.append(title);
   const note=doc.createElement('p');note.textContent='v3照合や潮汐API接続に依存せず、画面で開いたレースの既存1着率内部値を保存します。v3予測とは別ソースです。';ui.append(note);
   const btn=doc.createElement('button');btn.type='button';btn.textContent='既存着率の記録CSVを出力';btn.style.cssText='padding:8px;background:#2d5ab5;color:white;border:0;border-radius:6px';btn.addEventListener('click',exportFile);ui.append(btn);
   const state=doc.createElement('p');state.setAttribute('data-tide-v11-status','');ui.append(state);
   const caveat=doc.createElement('p');caveat.textContent='このCSVをV9のv3検証CSVへ混ぜないでください。サーバー同期はなく、ブラウザの保存データは消える場合があります。';caveat.style.fontSize='11px';ui.append(caveat);
   host.insertAdjacentElement('afterend',ui);
 }
 refresh();
}
function poll(){
 try{
   mount();if(!ui)return;
   const result=selected();if(result.status!=='ok')return;
   const saved=saveFirst(root.localStorage,result.key,result.record);
   if(saved.status==='saved')lastMsg=`${result.record.venue} ${result.record.race_no}R 締切前の既存着率を記録しました`;refresh();
 }catch(e){lastMsg='記録できません: '+String(e.message||e);refresh()}
}
function init(){poll();root.setInterval(poll,8000);root.addEventListener?.('focus',poll)}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init,{once:true});else init();
})(typeof window!=='undefined'?window:globalThis);

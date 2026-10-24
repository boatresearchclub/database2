/* BRC TIDE SHADOW V7 — strictly read-only diagnostic UI, no prediction writes.
   Client-side admin UI check is NOT security enforcement. No credentials/secrets included.
   Uses rounded displayed v3 rates for a demonstrative estimate only. */
(function(root){
'use strict';
const CORRECTION=root.BRCTideCorrectionV1;
const RESEARCH=root.BRCTideResearchV2;
if(!CORRECTION || !RESEARCH) return;
const VENUES={
 '児島':{id:'kojima',code:'16',pc:28,hc:9},
 '平和島':{id:'heiwajima',code:'04',pc:13,hc:1},
 '下関':{id:'shimonoseki',code:'19',pc:35,hc:16},
 '福岡':{id:'fukuoka',code:'22',pc:40,hc:20},
 '若松':{id:'wakamatsu',code:'20',pc:40,hc:10},
 '丸亀':{id:'marugame',code:'15',pc:37,hc:10}
};
const API='https://api.tide736.net/get_tide.php';
const BUILDTAG='BRC_TIDE_SHADOW_READONLY_V7_20261023';
const escapeText=x=>String(x==null?'':x);
function fail(reason){return {status:'skip',reason};}
function readPct(text){
 const hits=escapeText(text).match(/(?:^|[^\d])(\d{1,3}(?:\.\d+)?)\s*%/g)||[];
 if(hits.length!==1)return null;
 const m=hits[0].match(/(\d{1,3}(?:\.\d+)?)\s*%/);
 const x=m?Number(m[1]):NaN;
 return Number.isFinite(x)&&x>=0&&x<=100?x:null;
}
// A same-race display can retain the same rounded rates after exhibition data changes.
// Fingerprint raw race/entry/exhibition inputs; invalid/stale asynchronous results must be discarded.
function liveFingerprint(live){
 if(!live || !Array.isArray(live.boats) || live.boats.length!==6)return null;
 const cells=live.boats.map(b=>[String(b.boat_no),String(b.entry_course),
    String(b.relative_diff??''),String(b.lap_time??''),String(b.status??'')]);
 cells.sort((a,b)=>Number(a[0])-Number(b[0]));
 return [String(live.date||''),String(live.venue_code||''),String(live.race_no||''),
    String(live.fixed_course??''),...cells.map(a=>a.join('/'))].join('|');
}
function nowBeforeDeadline({day,deadline,nowMs=Date.now()}={}){
 if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day)||
    typeof deadline!=='string'|| !/^\d{2}:\d{2}$/.test(deadline))return false;
 const epoch=Date.parse(`${day}T${deadline}:00+09:00`);
 return Number.isFinite(epoch) && new Date(epoch+9*3600000).toISOString().slice(0,16)===`${day}T${deadline}` && Number.isFinite(nowMs) && nowMs<epoch;
}
function snapshot({diag,live,rateTexts,verifiedV3SameRace=false}={}){
 if(!diag||diag.admin!==true||diag.member!==true)return fail('管理者ログインが必要です');
 if(diag.v3Verified!==true||verifiedV3SameRace!==true)return fail('最新レースのTimeX v3照合が未成立です');
 if(diag.sameRaceLive!==true || diag.strictExhibition!==true || diag.tableReady!==true)
   return fail('展示確定・レース照合・出走表の条件が未成立です');
 const match=escapeText(diag.selectedRace).match(/^(児島|平和島|下関|福岡|若松|丸亀)\s+(\d{1,2})R$/);
 if(!match)return fail('潮汐対象6会場のレースではありません');
 const venueName=match[1],raceNo=Number(match[2]);
 const venue=VENUES[venueName];
 if(!Number.isInteger(raceNo)||raceNo<1||raceNo>12)return fail('レース番号が不正です');
 const day=escapeText(diag.date), raceCode=escapeText(live?.venue_code).padStart(2,'0');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day) || escapeText(live?.date)!==day || raceCode!==venue.code ||
    Number(live?.race_no)!==raceNo)return fail('展示データの開催日・会場・レース番号が一致しません');
 if(!Array.isArray(live.boats)||live.boats.length!==6)return fail('展示の6艇が揃っていません');
 const boatSet=new Set(),courseSet=new Set();let firstCourseBoat=null;
 for(const row of live.boats){
   const boat=Number(row.boat_no), course=Number(row.entry_course);
   if(!Number.isInteger(boat)||boat<1||boat>6||!Number.isInteger(course)||course<1||course>6||boatSet.has(boat)||courseSet.has(course))
      return fail('艇番・実際の進入コースが不正です');
   boatSet.add(boat);courseSet.add(course);
   if(course===1)firstCourseBoat=boat;
 }
 if(boatSet.size!==6||courseSet.size!==6||!firstCourseBoat)return fail('進入1コースの艇番を確定できません');
 const raceFingerprint=liveFingerprint(live);
 if(!raceFingerprint)return fail('展示のレース指紋を作成できません');
 if(!Array.isArray(rateTexts)||rateTexts.length!==6)return fail('表示されたv3の1着率を取得できません');
 const displayedPct=rateTexts.map(readPct);
 if(displayedPct.some(x=>x===null))return fail('v3表示に複数または不正な着率があります');
 const total=displayedPct.reduce((a,b)=>a+b,0);
 if(Math.abs(total-100)>3.001)return fail('v3表示の6艇合計が100±3%の範囲外です');
 // The displayed six rates are individually rounded. Normalize only for the study,
 // retaining both their observed sum and the raw display for later audit.
 const probabilities=displayedPct.map(v=>v/total*100);
 // IMPORTANT: BRC cells display rounded integer v3 rates. Do not claim this is original raw v3 model output.
 return {status:'ok',venueId:venue.id,venueName,raceNo,day,firstCourseBoat,
   probabilities,displayedPct,displayTotal:total,raceKey:`${day}|${venue.code}|${raceNo}`,raceFingerprint,source:'v3_display_rounded_normalized',
   note:'画面の丸め済みv3着率からの概算。v3内部の高精度値やAI・買い目は変更しない'};
}
function inferJstDateTime(text){
 if(typeof text!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(text))return null;
 // V2 classifier checks real calendar date and time.
 return text;
}
function classifyAndCompare({snapshotData,startJst,tidePayload}={}){
 if(!snapshotData || snapshotData.status!=='ok')return fail('v3着率の取得・照合が未完了です');
 if(!inferJstDateTime(startJst)||startJst.slice(0,10)!==snapshotData.day)
   return fail('対象レースと同日の発走予定日時（JST）を指定してください');
 const r=RESEARCH.shadow({serverVerifiedAdmin:true,v3Verified:true,exhibitionConfirmed:true,
    venueId:snapshotData.venueId,targetJst:startJst,tidePayload,
    probabilities:snapshotData.probabilities,firstCourseBoat:snapshotData.firstCourseBoat});
 return {status:r.status,reason:r.reason,shadow:r,context:snapshotData};
}
function showIfAuthorized(diag,doc){
 return !!(diag&&diag.admin===true&&diag.member===true&&!doc.body?.classList.contains('brc-admin-public-view'));
}

// BRC holds *deadline*, NOT actual race start. Never silently label it "start time".
// Exact selected venue and race must agree with same-race V3 diagnostics.
function deadlineFromRaceInfo({diag,raceInfo,selectedVenue,selectedRaceNo}={}){
 if(!diag||diag.admin!==true||diag.member!==true)return fail('管理者確認不可');
 const m=escapeText(diag.selectedRace).match(/^(児島|平和島|下関|福岡|若松|丸亀)\s+(\d{1,2})R$/);
 if(!m||escapeText(selectedVenue)!==m[1]||Number(selectedRaceNo)!==Number(m[2]))
   return fail('選択中のレースが診断結果と一致しません');
 const day=escapeText(diag.date);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day))return fail('開催日が不明です');
 const info=raceInfo?.[m[1]];
 const time=info?.deadlines?.[String(Number(m[2]))];
 if(typeof time!=='string'||!/^\d{1,2}:\d{2}$/.test(time))return fail('BRC内の締切予定時刻が未取得です');
 const parts=time.split(':').map(Number);
 if(parts[0]>23||parts[1]>59)return fail('締切予定時刻の範囲外です');
 const hhmm=String(parts[0]).padStart(2,'0')+':'+String(parts[1]).padStart(2,'0');
 const value=day+'T'+hhmm;
 if(!RESEARCH.classify)return fail('潮汐分類処理が利用できません');
 return {status:'ok',value,time:hhmm,source:'brc_deadline_proxy',label:'BRC内の締切予定時刻（発走時刻ではありません）'};
}
function addJstMinutes(value,mins){
 if(!inferJstDateTime(value)||!Number.isInteger(mins)||mins<0||mins>60)return null;
 const t=Date.parse(value+':00+09:00');
 if(!Number.isFinite(t))return null;
 // Explicitly format as JST regardless of browser locale.
 return new Date(t+mins*60000+9*3600000).toISOString().slice(0,16);
}
function validateTidePort(payload,venueId){
 const v=Object.values(VENUES).find(x=>x.id===venueId);
 if(!v)return fail('対象会場が未定義です');
 if(payload?.status!==1)return fail('潮汐APIの正常応答ではありません');
 const port=payload?.tide?.port;
 if(!port||typeof port!=='object')return fail('潮汐JSONに地点の識別情報がありません');
 const pc=Number(port.prefecture_code),hc=Number(port.harbor_code);
 if(!Number.isInteger(pc)||!Number.isInteger(hc)||pc!==v.pc||hc!==v.hc)
   return fail('潮汐JSONの地点コードがBRC対象会場と異なります');
 return {status:'ok',point:port.harbor_namej||''};
}
// BRC deadline is a proxy: require identical tide condition at 0, +5, +10 min.
// At low water/slack transitions this deliberately fails closed rather than guessing.
function stableComparison({snapshotData,referenceJst,tidePayload}={}){
 if(!snapshotData||snapshotData.status!=='ok')return fail('TimeX v3照合値がありません');
 const port=validateTidePort(tidePayload,snapshotData.venueId);
 if(port.status!=='ok')return port;
 if(!inferJstDateTime(referenceJst)||referenceJst.slice(0,10)!==snapshotData.day)
   return fail('対象レースと同一日付のJST時刻が必要です');
 let first=null;
 const checks=[];
 for(const offset of [0,5,10]){
  const t=addJstMinutes(referenceJst,offset);
  if(!t||t.slice(0,10)!==snapshotData.day)return fail('締切時刻から10分先まで同日の照合ができません');
  const c=RESEARCH.classify({tidePayload,targetJst:t});
  if(c.status!=='ok')return fail('潮汐が安定して判定できません（+'+offset+'分）：'+c.reason);
  if(first&&(first.tideName!==c.tideName||first.phase!==c.phase))
    return fail('締切〜10分後に潮汐局面が変わるため、発走時刻確定まで補正なし');
  if(!first)first=c;
  checks.push({offset,phase:c.phase,tideName:c.tideName,levelCm:c.cm});
 }
 const result=classifyAndCompare({snapshotData,startJst:referenceJst,tidePayload});
 if(result.status!=='ok')return result;
 return {...result,referenceKind:'deadline_or_manually_entered_time',stabilityMinutes:10,stabilityChecks:checks,portName:port.point};
}

const API_OBJ=Object.freeze({snapshot,classifyAndCompare,deadlineFromRaceInfo,stableComparison,validateTidePort,addJstMinutes,readPct,showIfAuthorized,liveFingerprint,nowBeforeDeadline,VENUES,API,BUILDTAG});
root.BRCTideAdminBridgeV7=API_OBJ;

if(!root.document||typeof root.setInterval!=='function')return;
const doc=root.document;
let ui=null, currentKey='', cachedTide=null, cachedKey='', lastExport=null;
function diagnostics(){try{return typeof root.brcV3AdminDiagnostics==='function'?root.brcV3AdminDiagnostics():null;}catch(_){return null}}
function selectedDeadline(diag){
 const venue=doc.getElementById('predictRaceDay')?.value||doc.getElementById('predictVenue')?.value||'';
 const race=doc.getElementById('predictRaceNo')?.value||'';
 const schedule=(typeof RACE_INFO_TODAY==='undefined')?(root.RACE_INFO_TODAY||null):RACE_INFO_TODAY;
 return deadlineFromRaceInfo({diag,raceInfo:schedule,selectedVenue:venue,selectedRaceNo:race});
}

function rateTextsFromDom(){return Array.from({length:6},(_,i)=>doc.getElementById('predict-win-cell-'+(i+1))?.textContent||'')}
function state(){return snapshot({diag:diagnostics(),live:root.__currentLiveExhibition,rateTexts:rateTextsFromDom(),
  verifiedV3SameRace:typeof root.brcV3VerifiedDetailVisible==='function' && root.brcV3VerifiedDetailVisible()===true})}
function status(message){if(ui)ui.querySelector('[data-tide-status]').textContent=message}
function clearResult(){lastExport=null;if(ui){ui.querySelector('[data-tide-output]').replaceChildren();const csv=ui.querySelector('[data-tide-csv]');if(csv)csv.disabled=true}}
function putText(tag,txt,className){const el=doc.createElement(tag);if(className)el.className=className;el.textContent=txt;return el}
function display(r){
 clearResult();const host=ui.querySelector('[data-tide-output]');
 if(r.status!=='ok'){status('補正なし：'+(r.reason||'判定不可'));return}
 const {result,tide}=r.shadow;
 if(!result || result.status!=='ok'){status('補正なし：'+(result?.reason||'該当条件不明'));return}
 lastExport={observed_at:new Date().toISOString(),venue:r.context.venueName,race_no:r.context.raceNo,
   race_date:r.context.day,deadline_or_start_time:ui?.querySelector('[data-tide-start]')?.value||'',
   v3_live_fingerprint:r.context.raceFingerprint,
   study_recorded_before_deadline:r.validPreDeadline===true,
   time_kind:r.timeSource||'unverified_user_reference',time_stability_window_min:r.stabilityMinutes||0,port_name:r.portName||'',first_course_boat_no:r.context.firstCourseBoat,
   tide_name:tide.tideName,tide_phase:tide.phase,tide_level_cm:tide.cm,
   sample_n:result.condition.n,baseline_in_escape_pct:result.condition.avg,
   conditional_in_escape_pct:result.condition.p,study_shift_pt:result.shiftPt,
   v3_display_sum:r.context.displayTotal,source:r.context.source,
   ...Object.fromEntries(r.context.displayedPct.map((x,i)=>['displayed_v3_boat_'+(i+1),x])),
   ...Object.fromEntries(result.after.map((x,i)=>['tide_study_boat_'+(i+1),x])),
   winner_boat_no:''};
 const csvButton=ui.querySelector('[data-tide-csv]');if(csvButton)csvButton.disabled=r.validPreDeadline!==true;
 status(`${r.context.venueName} ${r.context.raceNo}R ／ ${tide.tideName}・${tide.phase} ／ n=${result.condition.n} ／ 進入1コース ${r.context.firstCourseBoat}号艇 ／ +0〜10分で局面一致 ／ ${r.validPreDeadline?'締切前記録':'時刻未検証・精度評価対象外'}`);
 const table=putText('table','');
 const head=doc.createElement('thead'),tr=doc.createElement('tr');
 for(const col of ['艇番','v3画面表示','正規化後','潮汐試算','差'])tr.appendChild(putText('th',col));
 head.appendChild(tr);table.appendChild(head);
 const body=doc.createElement('tbody');
 for(let i=0;i<6;i++){
  const row=doc.createElement('tr'),arr=[`${i+1}号艇`,r.context.displayedPct[i].toFixed(1)+'%',result.before[i].toFixed(1)+'%',result.displayedAfter[i].toFixed(1)+'%',
   (result.after[i]-result.before[i]>=0?'+':'')+(result.after[i]-result.before[i]).toFixed(2)+'pt'];
  for(const val of arr)row.appendChild(putText('td',val));
  body.appendChild(row);
 }
 table.appendChild(body);host.appendChild(table);
 host.appendChild(putText('p','※v3画面の丸め済み着率を使った探索値です。締切を発走時刻として断定していません。元集計と潮汐局面定義は未照合で予測に採用不可。','brc-tide-small'));
}
async function fetchTideForDay(snap){
 const venue=Object.values(VENUES).find(v=>v.id===snap.venueId);
 if(!venue)throw Error('会場未定義');
 if(cachedKey===`${snap.venueId}|${snap.day}`&&cachedTide)return cachedTide;
 const [yr,mn,dy]=snap.day.split('-');
 const query=new URLSearchParams({pc:String(venue.pc),hc:String(venue.hc),yr,mn,dy,rg:'day'});
 const endpoint=API+'?'+query.toString();
 const controller=new AbortController();const cancel=root.setTimeout(()=>controller.abort(),10000);
 try{
  const response=await root.fetch(endpoint,{method:'GET',signal:controller.signal,cache:'no-store',credentials:'omit'});
  if(!response.ok)throw Error('API HTTP '+response.status);
  const data=await response.json();if(data?.status!==1)throw Error('API不正応答');
  cachedKey=`${snap.venueId}|${snap.day}`;cachedTide=data;return data;
 }finally{root.clearTimeout(cancel)}
}
async function runStudy(){
 const start=ui?.querySelector('[data-tide-start]')?.value||'';
 const captured=state();clearResult();
 if(captured.status!=='ok'){status('補正なし：'+captured.reason);return}
 if(!inferJstDateTime(start)||start.slice(0,10)!==captured.day){status('締切予定時刻または手動JST参照時刻を確認してください');return}
 status('潮汐APIを照会中…');
 const identity=JSON.stringify([captured.raceKey,captured.firstCourseBoat,captured.displayedPct,captured.raceFingerprint]);
 const button=ui.querySelector('[data-tide-run]');button.disabled=true;
 try{
   const pasted=ui.querySelector('[data-tide-json]')?.value.trim()||'';
   if(pasted.length>2_000_000)throw Error('貼付JSONが2MBを超えています');
   const payload=pasted?JSON.parse(pasted):await fetchTideForDay(captured);
   const latest=state();
   if(latest.status!=='ok'||JSON.stringify([latest.raceKey,latest.firstCourseBoat,latest.displayedPct,latest.raceFingerprint])!==identity ||
      ui?.querySelector('[data-tide-start]')?.value!==start){status('レース・v3着率・時刻が更新されました。古い結果を破棄します');return}
   const schedule=selectedDeadline(diagnostics());
   const officialReference=schedule.status==='ok' && schedule.value===start;
   const deadlineGuard=officialReference && nowBeforeDeadline({day:captured.day,deadline:schedule.time});
   // No new records after the source deadline; this prevents result-informed retrospective
   // estimates from being mistaken for genuine out-of-sample predictions.
   if(officialReference && !deadlineGuard){status('締切時刻を過ぎたため新規の事前試算は記録できません。');return}
   const compared=stableComparison({snapshotData:latest,referenceJst:start,tidePayload:payload});
   display(compared.status==='ok' ? {...compared,timeSource:officialReference?'brc_deadline_proxy':'unverified_user_reference',validPreDeadline:deadlineGuard} : compared);
 }catch(e){status('潮汐照会不可：'+String(e.message||e)+'。外部APIの接続/CORS/利用条件を確認してください');}
 finally{if(ui)button.disabled=false}
}
function exportCsv(){
 if(!lastExport||lastExport.study_recorded_before_deadline!==true){status('締切前に記録した検証値のみCSV保存できます');return}
 // V7: generation time must ALSO be predeadline. Never export a stale in-memory
 // study after deadline and pass it off as a committed preregistered forecast.
 const currentDeadline=selectedDeadline(diagnostics());
 if(currentDeadline.status!=='ok'||currentDeadline.value!==lastExport.deadline_or_start_time||
    !nowBeforeDeadline({day:lastExport.race_date,deadline:currentDeadline.time})){
   status('締切後の新規CSV保存は禁止です。事前記録として扱いません。');clearResult();return;
 }
 const checked=state();
 if(checked.status!=='ok'||ui?.querySelector('[data-tide-start]')?.value!==lastExport.deadline_or_start_time||checked.raceKey!==`${lastExport.race_date}|${VENUES[checked.venueName]?.code||''}|${lastExport.race_no}` ||
     (checked.raceFingerprint!==lastExport.v3_live_fingerprint) ||
     checked.displayedPct.some((v,i)=>v!==lastExport['displayed_v3_boat_'+(i+1)])){status('現在のレースまたは着率が変わったためCSVを出力しません');clearResult();return}
 const cols=Object.keys(lastExport);
 const escapeCsv=x=>'"'+String(x==null?'':x).replaceAll('\"','\"\"')+'"';
 const content='\ufeff'+cols.map(escapeCsv).join(',')+'\r\n'+cols.map(k=>escapeCsv(lastExport[k])).join(',')+'\r\n';
 const blob=new Blob([content],{type:'text/csv;charset=utf-8'});
 const url=URL.createObjectURL(blob);const link=doc.createElement('a');link.href=url;link.download=`brc_tide_study_${lastExport.race_date}_${lastExport.venue}_${lastExport.race_no}R.csv`;
 link.click();root.setTimeout(()=>URL.revokeObjectURL(url),5000);
}
function mount(){
 const diag=diagnostics();const authorized=showIfAuthorized(diag,doc);
 if(!authorized){if(ui){ui.remove();ui=null;currentKey='';}return}
 const host=doc.querySelector('#predictResult #predictTableWrap');
 if(!host||!host.isConnected){if(ui){ui.remove();ui=null;currentKey='';}return}
 if(ui && (!ui.isConnected||ui.previousElementSibling!==host)){ui.remove();ui=null}
 if(!ui){
  ui=doc.createElement('details');ui.className='brc-tide-v7';ui.id='brc-tide-shadow-v7';
  const sum=putText('summary','🌊 潮汐補正（管理者研究・着率には未反映）');ui.appendChild(sum);
  const line=putText('div','BRCの締切予定時刻を自動入力します。締切〜10分後まで潮汐局面が一致する場合だけ試算します。','brc-tide-small');ui.appendChild(line);
  const field=doc.createElement('div');field.className='brc-tide-controls';
  const label=putText('label','締切予定日時（JST・自動候補）');
  const inp=doc.createElement('input');inp.setAttribute('data-tide-start','');inp.type='datetime-local';inp.step='60';label.appendChild(inp);inp.addEventListener('input',()=>{clearResult();status('参照時刻が変更されました。再度照会してください。')});
  const button=putText('button','潮汐を照会して試算');button.type='button';button.setAttribute('data-tide-run','');
  button.addEventListener('click',runStudy);field.append(label,button);
  const csvButton=putText('button','試算結果をCSV保存');csvButton.type='button';csvButton.disabled=true;csvButton.setAttribute('data-tide-csv','');
  csvButton.addEventListener('click',exportCsv);field.appendChild(csvButton);ui.appendChild(field);
  const advanced=doc.createElement('details');advanced.className='brc-tide-advanced';
  advanced.appendChild(putText('summary','APIに接続できない場合：潮汐JSONを貼り付ける'));
  const json=doc.createElement('textarea');json.setAttribute('data-tide-json','');json.placeholder='指定日・対象地点のJSON（未入力時はAPI照会）';
  json.rows=3;advanced.appendChild(json);ui.appendChild(advanced);
  const info=putText('p','現状確認中','brc-tide-small');info.setAttribute('data-tide-status','');ui.appendChild(info);
  const output=doc.createElement('div');output.setAttribute('data-tide-output','');ui.appendChild(output);
  const note=putText('p','重要：イン逃げ率≠進入1コース1着率。2021〜25年の参考集計を使う探索的試算です。結果取得後の後付け検証を防ぐため、CSV記録は公式締切前のみ可能です。表のBRC着率、AI予測、買い目、TimeXには書き込みません。','brc-tide-small');ui.appendChild(note);
  host.insertAdjacentElement('afterend',ui);
 }
 const liveSnapshot=state();
 const nextKey=String(diag.date)+'|'+String(diag.selectedRace)+'|'+String(diag.v3Verified)+'|'+String(diag.sameRaceLive)+'|'+
  String(liveSnapshot.firstCourseBoat||'')+'|'+(liveSnapshot.displayedPct||[]).join(',')+'|'+String(liveSnapshot.raceFingerprint||'')+'|'+String(liveSnapshot.status);
 if(nextKey!==currentKey){
  currentKey=nextKey;clearResult();
  const snap=state();status(snap.status==='ok' ? `${snap.venueName} ${snap.raceNo}R：v3照合済み。締切予定時刻を自動照合します。`:snap.reason);
  const input=ui.querySelector('[data-tide-start]');
  if(input){const sd=selectedDeadline(diag);input.value=sd.status==='ok'?sd.value:'';if(snap.status==='ok'&&sd.status!=='ok')status('締切予定時刻の自動取得不可：手入力による研究用照合のみ可能です。');}
 }
}
function initialize(){
 if(doc.getElementById('brc-tide-v7-styles'))return;
 const style=doc.createElement('style');style.id='brc-tide-v7-styles';
 style.textContent='.brc-tide-v7{margin:12px 0;padding:11px 13px;border:1px solid #7a99ca;border-radius:10px;background:#f7faff;color:#18314f;font-size:12px}.brc-tide-v7 summary{cursor:pointer;font-weight:700;font-size:13px}.brc-tide-v7 .brc-tide-small{font-size:11px;line-height:1.6;color:#45617a;margin:8px 0}.brc-tide-v7 .brc-tide-controls{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;padding:9px 0}.brc-tide-v7 label{font-size:11px;display:flex;flex-direction:column;gap:4px}.brc-tide-v7 input{padding:6px;border:1px solid #afbdd0;border-radius:5px;color:#142d4f;background:white}.brc-tide-v7 button{padding:7px 10px;background:#135bc0;color:white;border:0;border-radius:6px;font-weight:700;cursor:pointer}.brc-tide-v7 button:disabled{opacity:.5}.brc-tide-v7 .brc-tide-advanced textarea{margin-top:7px;width:100%;box-sizing:border-box;min-height:60px;font-size:11px;border:1px solid #d2ddeb;border-radius:5px}.brc-tide-v7 .brc-tide-advanced summary{font-size:11px;color:#45617a}.brc-tide-v7 table{border-collapse:collapse;width:100%;font-size:11px}.brc-tide-v7 th,.brc-tide-v7 td{text-align:right;border-bottom:1px solid #dce5f1;padding:6px 3px}.brc-tide-v7 th:first-child,.brc-tide-v7 td:first-child{text-align:left}';
 doc.head.appendChild(style);mount();root.setInterval(mount,3000);
}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',initialize,{once:true});else initialize();
})(typeof window!=='undefined'?window:globalThis);

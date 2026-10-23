/* BRC TIDE V12 — 事前1着率 basePctFloat × 潮汐：管理者研究用シャドー
 * NOT a production prior model. No mutation of basePctFloat, pctFloat, AI, bets.
 * The source table is historical "イン逃げ率", NOT identical to 1コース1着率.
 * Requires same-race pre-forecast, official deadline, exact JST date and tide port.
 */
(function(root){
'use strict';
const CORE=root.BRCTideCorrectionV1,RESEARCH=root.BRCTideResearchV2;
if(!CORE || !RESEARCH)return;
const KEY='brc_tide_v12_pre_win_shadow_first';
const VERSION='BRC_TIDE_V12_PRE_WIN_SHADOW_20261023';
const CODES={'児島':['kojima','16',28,9],'平和島':['heiwajima','04',13,1],'下関':['shimonoseki','19',35,16],'福岡':['fukuoka','22',40,20],'若松':['wakamatsu','20',40,10],'丸亀':['marugame','15',37,10]};
const FIELDS=['captured_at','race_date','venue','venue_code','race_no','deadline_jst','time_proxy','status','source','first_course_boat','first_course_basis','tide_name','tide_phase','sample_n','tide_level_cm','shift_pt','pre_base_total','pre_roster_fingerprint',...Array.from({length:6},(_,i)=>'pre_base_boat_'+(i+1)),...Array.from({length:6},(_,i)=>'tide_shadow_pre_boat_'+(i+1))];
const fail=(reason)=>({status:'skip',reason});
const localDay=ms=>new Date(ms+9*3600000).toISOString().slice(0,10);
const hhmmValid=s=>typeof s==='string'&&/^\d{1,2}:\d{2}$/.test(s)&&Number(s.slice(0,s.indexOf(':')))<24&&Number(s.split(':')[1])<60;
function deadlineEpoch(day,time){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(day||''))||!hhmmValid(time))return null;
 const [h,m]=time.split(':').map(Number);const iso=`${day}T${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
 const t=Date.parse(iso+':00+09:00');
 return Number.isFinite(t)&&new Date(t+9*3600000).toISOString().slice(0,16)===iso?{iso,ms:t}:null;
}
function buildPreSnapshot({diag,boats,rosters,schedule,selectedVenue,selectedRaceNo,nowMs=Date.now(),publicPreview=false,live=null}={}){
 if(publicPreview||!diag||diag.admin!==true||diag.member!==true)return fail('管理者ログインが必要です');
 if(!diag.tableReady)return fail('出走表の計算完了待ち');
 const m=String(diag.selectedRace||'').match(/^(児島|平和島|下関|福岡|若松|丸亀)\s+(\d{1,2})R$/);
 if(!m)return fail('潮汐対象6会場以外');
 const venue=m[1],number=Number(m[2]),codes=CODES[venue],day=String(diag.date||'');
 if(!Number.isInteger(number)||number<1||number>12||selectedVenue!==venue||Number(selectedRaceNo)!==number)return fail('選択中の会場・レースが不一致');
 if(!Number.isFinite(nowMs)||localDay(nowMs)!==day)return fail('選択レースが当日ではありません');
 const cutoff=deadlineEpoch(day,schedule?.[venue]?.deadlines?.[String(number)]);
 if(!cutoff)return fail('締切予定時刻が不明');
 if(cutoff.ms-nowMs<=60000)return fail('締切60秒以内または締切後');
 const r=rosters?.[venue]?.[String(number)];
 if(!Array.isArray(r)||r.length!==6)return fail('当日の出走表が未照合');
 if(!Array.isArray(boats)||boats.length!==6)return fail('事前1着率6艇が未取得');
 const pre=Array(6).fill(null),regs=Array(6).fill(null);
 for(const b of boats){
  // BRC code explicitly assigns basePctFloat from Worker BEFORE TimeX.
  // b.course is original boat number. Must not take b.pctFloat (post exhibition).
  const no=Number(b?.course),x=b?.basePctFloat,reg=String(b?.player?.reg||'');
  if(!Number.isInteger(no)||no<1||no>6||pre[no-1]!==null||typeof x!=='number'||!Number.isFinite(x)||x<0||x>100||!reg)return fail('事前1着率・艇番・選手登録番号が不正');
  pre[no-1]=x;regs[no-1]=reg;
 }
 if(regs.some((v,i)=>String(r[i])!==v))return fail('事前1着率の出走選手と当日番組が一致しません');
 const sum=pre.reduce((a,b)=>a+b,0);
 if(pre.some(x=>x===null)||!(sum>0)||Math.abs(sum-100)>2)return fail('事前1着率の合計が100%と整合しません');
 let first=1,basis='枠なり仮定（展示前）';
 // An explicitly known entry change cannot be folded into pre-race lane-1 assumption.
 if(live && String(live.date||'')===day && String(live.venue_code||'').padStart(2,'0')===codes[1] && Number(live.race_no)===number && Array.isArray(live.boats) && live.boats.length===6){
   const nums=new Set(),courses=new Set();let inBoat=null;
   for(const b of live.boats){
     const no=Number(b.boat_no),course=Number(b.entry_course);
     if(!Number.isInteger(no)||!Number.isInteger(course)||no<1||no>6||course<1||course>6||nums.has(no)||courses.has(course))return fail('展示の進入データに欠損・重複があります');
     nums.add(no);courses.add(course);if(course===1)inBoat=no;
   }
   if(nums.size!==6||courses.size!==6||!inBoat)return fail('展示の進入データが不完全です');
   if(inBoat!==1)return fail('進入変更あり：事前1コース仮定を適用しません');
   basis='展示進入確認済み（1号艇が1コース）';
 }
 return {status:'ok',raceKey:`${day}|${codes[1]}|${number}`,day,venue,code:codes[1],venueId:codes[0],pc:codes[2],hc:codes[3],number,
   firstCourseBoat:first,firstCourseBasis:basis,cutoffJst:cutoff.iso,cutoffMs:cutoff.ms,
   before:pre.map(v=>v/sum*100),rawBefore:pre,rawSum:sum,
   rosterFingerprint:[day,codes[1],number,...regs,...pre.map(v=>v.toFixed(8))].join('|')};
}
function validatePort(payload,snapshot){
 if(payload?.status!==1)return fail('潮汐APIの正常応答ではありません');
 const port=payload?.tide?.port;
 if(!port || Number(port.prefecture_code)!==snapshot.pc || Number(port.harbor_code)!==snapshot.hc)return fail('潮汐地点コード不一致');
 return {status:'ok'};
}
function compare({snapshot:ctx,tidePayload}={}){
 if(!ctx||ctx.status!=='ok')return fail('事前1着率のレース照合が未完了');
 const checked=validatePort(tidePayload,ctx);if(checked.status!=='ok')return checked;
 // Deadline is not a verified start time. Use 0/5/10 min stability only for research.
 const t0=Date.parse(ctx.cutoffJst+':00+09:00');let tide=null;
 for(const min of [0,5,10]){
  const candidate=new Date(t0+min*60000+9*3600000).toISOString().slice(0,16);
  if(candidate.slice(0,10)!==ctx.day)return fail('潮位照会時刻が開催日を越えました');
  const c=RESEARCH.classify({tidePayload,targetJst:candidate});
  if(c.status!=='ok')return fail('潮汐分類不可（+'+min+'分）：'+c.reason);
  if(tide&&(c.tideName!==tide.tideName||c.phase!==tide.phase))return fail('締切から10分以内に潮汐局面が変わるため補正なし');
  tide=c;
 }
 const result=CORE.adjust({venueId:ctx.venueId,tideName:tide.tideName,phase:tide.phase,probabilities:ctx.before,firstCourseBoat:ctx.firstCourseBoat});
 if(result.status!=='ok')return fail(result.reason);
 return {status:'ok',snapshot:ctx,tide,result,
   note:'basePctFloat事前着率からの潮汐シャドー補正。イン逃げ率と1コース勝率は別。実績検証まで本番不採用'};
}
function recordFromComparison(v,nowMs=Date.now()){
 if(!v||v.status!=='ok')throw Error('未検証の補正は保存できません');
 const s=v.snapshot;
 if(!Number.isFinite(nowMs)||nowMs>=s.cutoffMs-60000)throw Error('締切60秒以内/締切後の保存禁止');
 const record={captured_at:new Date(nowMs).toISOString(),race_date:s.day,venue:s.venue,venue_code:s.code,race_no:s.number,
  deadline_jst:s.cutoffJst,time_proxy:'BRC公式番組の締切時刻（発走時刻の代用）',status:'research_only',
  source:'worker_pre_exhibition_basePctFloat',first_course_boat:s.firstCourseBoat,first_course_basis:s.firstCourseBasis,
  tide_name:v.tide.tideName,tide_phase:v.tide.phase,sample_n:v.result.condition.n,tide_level_cm:v.tide.cm,
  shift_pt:v.result.shiftPt,pre_base_total:s.rawSum,pre_roster_fingerprint:s.rosterFingerprint};
 for(let i=0;i<6;i++){record['pre_base_boat_'+(i+1)]=s.before[i];record['tide_shadow_pre_boat_'+(i+1)]=v.result.after[i];}
 return record;
}
function readStore(storage){
 const str=storage.getItem(KEY);
 if(!str)return {version:VERSION,records:{}};
 const v=JSON.parse(str);
 if(!v||v.version!==VERSION||!v.records||typeof v.records!=='object'||Array.isArray(v.records)||Object.keys(v.records).length>3000)throw Error('保存庫が不正です。上書きしません');
 return v;
}
function saveFirst(storage,r){
 if(!r||r.source!=='worker_pre_exhibition_basePctFloat'||r.status!=='research_only')throw Error('不正な保存データ');
 const key=`${r.race_date}|${r.venue_code}|${r.race_no}`;
 if(!/^\d{4}-\d{2}-\d{2}\|\d{2}\|(?:[1-9]|1[012])$/.test(key))throw Error('レースキー不正');
 const captured=Date.parse(r.captured_at),cutoff=Date.parse(r.deadline_jst+':00+09:00');
 if(!Number.isFinite(captured)||!Number.isFinite(cutoff)||captured>=cutoff-60000)throw Error('保存時刻が締切直前/締切後');
 const db=readStore(storage);
 if(Object.hasOwn(db.records,key))return {status:'duplicate',count:Object.keys(db.records).length};
 if(Object.keys(db.records).length>=3000)throw Error('保存件数上限');
 db.records[key]=r;storage.setItem(KEY,JSON.stringify(db));
 if(!Object.hasOwn(readStore(storage).records,key))throw Error('書込後の照合失敗');
 return {status:'saved',count:Object.keys(db.records).length};
}
function csv(records){
 const esc=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 return '\ufeff'+FIELDS.map(esc).join(',')+'\r\n'+records.map(r=>FIELDS.map(k=>esc(r[k])).join(',')).join('\r\n')+'\r\n';
}
const API=Object.freeze({KEY,VERSION,FIELDS,CODES,deadlineEpoch,buildPreSnapshot,validatePort,compare,recordFromComparison,saveFirst,readStore,csv});
root.BRCTidePriorV12=API;
if(!root.document||typeof root.setInterval!=='function')return;
const doc=root.document;
let panel=null,lastStatus='',autoAttemptKey='',running=false;
const admin=()=>{try{const d=root.brcV3AdminDiagnostics?.();return d?.admin===true&&d?.member===true&&!doc.body.classList.contains('brc-admin-public-view')?d:null;}catch(_){return null}};
const schedule=()=>typeof RACE_INFO_TODAY!=='undefined'?RACE_INFO_TODAY:root.RACE_INFO_TODAY;
const roster=()=>typeof RACE_CARDS_TODAY!=='undefined'?RACE_CARDS_TODAY:root.RACE_CARDS_TODAY;
function current(){
 const diag=admin();if(!diag)return fail('管理者権限なし');
 return buildPreSnapshot({diag,boats:root.__predictBoatsCurrent,rosters:roster(),schedule:schedule(),
  selectedVenue:doc.getElementById('predictRaceDay')?.value||doc.getElementById('predictVenue')?.value,
  selectedRaceNo:doc.getElementById('predictRaceNo')?.value,live:root.__currentLiveExhibition,nowMs:Date.now()});
}
function showStatus(t){lastStatus=t;if(panel)panel.querySelector('[data-brc-tide12-status]').textContent=t}
function showTable(v){
 const body=panel.querySelector('[data-brc-tide12-result]');body.replaceChildren();
 const heading=doc.createElement('p');heading.textContent=`${v.snapshot.venue} ${v.snapshot.number}R 事前着率／${v.tide.tideName}・${v.tide.phase}（n=${v.result.condition.n}、補正 ${v.result.shiftPt>=0?'+':''}${v.result.shiftPt.toFixed(2)}pt）`;body.append(heading);
 const table=doc.createElement('table');table.style.cssText='width:100%;font-size:12px;border-collapse:collapse';
 const titles=doc.createElement('tr');for(const col of ['艇','事前1着率','潮汐研究値','差']){const td=doc.createElement('th');td.textContent=col;td.style.textAlign='right';titles.append(td)}table.append(titles);
 for(let i=0;i<6;i++){const tr=doc.createElement('tr'),row=[`${i+1}号艇`,v.snapshot.before[i].toFixed(1)+'%',v.result.after[i].toFixed(1)+'%',(v.result.after[i]-v.snapshot.before[i]).toFixed(2)+'pt'];for(const val of row){const cell=doc.createElement('td');cell.textContent=val;cell.style.textAlign='right';cell.style.borderTop='1px solid #ddd';tr.append(cell)}table.append(tr)}
 body.append(table);const foot=doc.createElement('p');foot.textContent='締切時刻を参照した研究値です。事前率・TimeX・AI予測・買い目は変更していません。';body.append(foot);
}
function exportCsv(){
 try{if(!admin())throw Error('管理者ログインが必要です');const records=Object.values(readStore(root.localStorage).records);if(!records.length)throw Error('まだ記録はありません');
 const blob=new Blob([csv(records)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=doc.createElement('a');a.href=url;a.download='BRC_TIDE_PRE_V12_'+localDay(Date.now())+'.csv';doc.body.append(a);a.click();a.remove();root.setTimeout(()=>URL.revokeObjectURL(url),5000);
 showStatus(`${records.length}件の事前着率研究CSVを出力しました`);
 }catch(e){showStatus('CSV出力不可：'+String(e.message||e))}
}
async function run(){
 if(running)return;
 running=true;
 const s=current();if(s.status!=='ok'){showStatus('補正なし：'+s.reason);running=false;return}
 const requested=[s.raceKey,s.rosterFingerprint,s.cutoffJst].join('|');
 const runButton=panel.querySelector('[data-brc-tide12-run]');runButton.disabled=true;showStatus('対象レースの潮汐を照会中…');
 try{
  const json=panel.querySelector('[data-brc-tide12-json]')?.value.trim()||'';if(json.length>2_000_000)throw Error('潮汐JSONが2MB超');
  let payload;
  if(json)payload=JSON.parse(json);
  else{
    const controller=new AbortController(),abort=root.setTimeout(()=>controller.abort(),9000);
    try{const p=new URLSearchParams({pc:String(s.pc),hc:String(s.hc),yr:s.day.slice(0,4),mn:String(Number(s.day.slice(5,7))),dy:String(Number(s.day.slice(8,10))),rg:'day'});
    const r=await root.fetch('https://api.tide736.net/get_tide.php?'+p.toString(),{method:'GET',cache:'no-store',credentials:'omit',signal:controller.signal});
    if(!r.ok)throw Error('潮汐API HTTP '+r.status);payload=await r.json();
    }finally{root.clearTimeout(abort)}
  }
  const latest=current();if(latest.status!=='ok'||[latest.raceKey,latest.rosterFingerprint,latest.cutoffJst].join('|')!==requested)throw Error('レース・事前着率・締切が変化。古い結果を破棄');
  const v=compare({snapshot:s,tidePayload:payload});if(v.status!=='ok'){showStatus('補正なし：'+v.reason);return}
  showTable(v);
  const rec=recordFromComparison(v,Date.now());
  const saved=saveFirst(root.localStorage,rec);showStatus(saved.status==='saved'?'事前着率の潮汐比較を初回保存しました':'同一レースの初回保存済み記録を保持しています');
 }catch(e){showStatus('補正なし：'+String(e.message||e))}
 finally{runButton.disabled=false;running=false}
}
function mount(){
 const diag=admin(),host=doc.getElementById('brc-tide-baseline-v11')||doc.getElementById('brc-tide-shadow-v7')||doc.querySelector('#predictResult #predictTableWrap');
 if(!diag||!host||!host.isConnected){if(panel){panel.remove();panel=null}return}
 if(panel&&(!panel.isConnected||panel.previousElementSibling!==host)){panel.remove();panel=null}
 if(panel)return;
 panel=doc.createElement('details');panel.id='brc-tide-pre-v12';panel.style.cssText='margin:8px 0;padding:12px;border:1px solid #afc8e6;border-radius:8px;background:#fff;font-size:12px;color:#243547';
 const title=doc.createElement('summary');title.style.fontWeight='bold';title.textContent='🌊 事前1着率 × 潮汐補正（管理者研究・V12）';panel.append(title);
 const desc=doc.createElement('p');desc.textContent='BRC Workerの展示前 basePctFloat を使用します。展示後 pctFloat やv3整数表示とは別の研究値です。';panel.append(desc);
 const b=doc.createElement('button');b.type='button';b.textContent='現在のレースを潮汐補正して比較';b.setAttribute('data-brc-tide12-run','');b.style.cssText='padding:8px;border:0;border-radius:6px;background:#1466ae;color:white;font-weight:bold;margin-right:8px';b.addEventListener('click',run);panel.append(b);
 const ex=doc.createElement('button');ex.type='button';ex.textContent='締切前の研究記録をCSV出力';ex.style.cssText='padding:8px;border:1px solid #1466ae;border-radius:6px;background:#fff;color:#1466ae';ex.addEventListener('click',exportCsv);panel.append(ex);
 const sub=doc.createElement('details');const ss=doc.createElement('summary');ss.textContent='潮汐APIが使えない場合：当日の潮汐JSONを貼り付け';sub.append(ss);const textarea=doc.createElement('textarea');textarea.setAttribute('data-brc-tide12-json','');textarea.style.cssText='width:100%;min-height:70px';sub.append(textarea);panel.append(sub);
 const status=doc.createElement('p');status.setAttribute('data-brc-tide12-status','');status.textContent=lastStatus||'研究用です。実レースでの予測精度改善は未確認。';panel.append(status);
 const result=doc.createElement('div');result.setAttribute('data-brc-tide12-result','');panel.append(result);
 host.insertAdjacentElement('afterend',panel);
}
function tick(){
 try{
   mount();if(!panel)return;
   const s=current();if(s.status!=='ok')return;
   const key=s.raceKey+'|'+s.rosterFingerprint+'|'+s.cutoffJst;
   if(autoAttemptKey===key)return;
   // The API is queried at most once per exact pre-race snapshot in this page session.
   // Failure is left to the manual retry button; no repeated network polling.
   autoAttemptKey=key;
   const db=readStore(root.localStorage);
   if(Object.hasOwn(db.records,s.raceKey))return;
   run();
 }catch(e){showStatus('自動照合を見合わせました：'+String(e.message||e))}
}
root.setInterval(tick,4000);
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',tick,{once:true});else tick();
})(typeof window!=='undefined'?window:globalThis);

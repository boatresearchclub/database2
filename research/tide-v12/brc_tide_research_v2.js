/* BRC 潮汐補正・研究版 v1
 * 元データ: ユーザー提供 index潮汐表.html 内の2021～2025年イン逃げ率
 * 注意: イン逃げ率 != 1コース1着率。予測性能未検証。
 * 既存BRC本体の計算には自動的に介入しない。
 */
(function (root) {
"use strict";
const DATA = {"kojima":{"label":"児島","point":"下津井","avg":55.6,"races":"11,218","rows":{"大潮":[[69.4,85],[49.8,641],[55.2,1606],[72.7,231]],"中潮":[[53.0,1143],[49.1,1011],[58.8,1956],[61.8,411]],"小潮":[[50.7,1576],[59.6,456],[69.7,142],[59.5,388]],"若潮":[[64.2,193],null,[53.8,325],[58.0,226]],"長潮":[[61.6,359],[50.0,6],[57.6,191],[50.7,272]]}},"heiwajima":{"label":"平和島","point":"築地","avg":44.7,"races":"10,453","rows":{"大潮":[[44.5,1706],[57.7,215],[27.9,43],[36.3,581]],"中潮":[[46.3,1935],[51.1,370],[42.3,832],[42.9,961]],"小潮":[[44.9,276],[39.6,182],[44.1,1377],[49.6,452]],"若潮":[[41.3,288],[42.6,244],[48.8,211],null],"長潮":[[34.4,163],[46.0,226],[51.3,372],[52.6,19]]}},"shimonoseki":{"label":"下関","point":"岩黒","avg":59.7,"races":"10,764","rows":{"大潮":[[57.6,1633],[67.4,325],[66.7,30],[46.9,448]],"中潮":[[62.3,2123],[69.1,475],[54.8,869],[54.6,1047]],"小潮":[[74.3,140],[55.0,202],[59.1,1481],[71.2,504]],"若潮":[[55.0,240],[59.6,250],[68.7,230],null],"長潮":[[51.3,113],[55.7,235],[63.7,408],[54.5,11]]}},"fukuoka":{"label":"福岡","point":"博多船だまり","avg":55.0,"races":"11,344","rows":{"大潮":[[66.5,409],[51.2,80],[49.5,1478],[58.2,867]],"中潮":[[60.5,837],[46.9,646],[53.3,2287],[56.9,897]],"小潮":[[54.0,882],[53.0,673],[62.2,645],[66.0,47]],"若潮":[[60.5,473],[56.0,25],[53.4,58],[50.0,224]],"長潮":[[53.1,550],[62.4,101],[52.2,23],[50.0,142]]}},"wakamatsu":{"label":"若松","point":"若松","avg":56.9,"races":"11,648","rows":{"大潮":[[60.3,1855],[60.3,121],[42.2,135],[47.2,868]],"中潮":[[60.9,2020],[60.7,410],[49.4,1244],[60.2,1194]],"小潮":[[52.9,189],[51.6,378],[57.7,1375],[63.6,305]],"若潮":[[47.8,441],[59.8,261],[65.1,109],null],"長潮":[[47.0,266],[60.7,262],[68.9,212],[100.0,3]]}},"marugame":{"label":"丸亀","point":"丸亀","avg":56.1,"races":"11,549","rows":{"大潮":[[66.1,1085],[100.0,3],[50.2,711],[57.9,986]],"中潮":[[59.3,1233],[63.8,235],[48.3,1944],[61.1,1272]],"小潮":[[45.8,286],[48.1,752],[60.2,1352],[78.7,47]],"若潮":[[47.4,500],[65.9,220],[71.4,28],[48.6,37]],"長潮":[[47.2,422],[60.1,291],[62.8,145],null]}}};
const PHASES = ["上げ潮","満潮付近","下げ潮","干潮付近"];
const SETTINGS = Object.freeze({influence:0.5, priorRaces:500, minSample:100, maxChangePt:3});
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
const logit=p=>Math.log(p/(1-p));
const sigmoid=x=>1/(1+Math.exp(-x));
function oneDecimalSum100(a) {
  // Largest remainder rounding in 0.1pt, sum exactly 100.0
  const units=a.map(x=>x*10);
  const lows=units.map(x=>Math.floor(x+1e-10));
  let diff=1000-lows.reduce((s,n)=>s+n,0);
  const order=units.map((v,i)=>({i,frac:v-lows[i]})).sort((a,b)=>b.frac-a.frac||a.i-b.i);
  for(let k=0;k<diff;k++) lows[order[k%6].i]++;
  return lows.map(x=>x/10);
}
function unchanged(result, reason) {
  return {...result, status:"skip", reason, applied:false, after:result.before.slice(), displayedAfter:oneDecimalSum100(result.before)};
}
function condition({venueId, tideName, phase}) {
  const venue=DATA[venueId];
  const phaseIndex=PHASES.indexOf(phase);
  if (!venue || phaseIndex<0 || !(tideName in venue.rows)) return null;
  const hit=venue.rows[tideName][phaseIndex];
  return hit ? {venue:venue.label, avg:venue.avg, tideName, phase, p:hit[0], n:hit[1]} : null;
}
function adjust({venueId,tideName,phase,probabilities,firstCourseBoat=1,
  influence=SETTINGS.influence,priorRaces=SETTINGS.priorRaces,
  minSample=SETTINGS.minSample,maxChangePt=SETTINGS.maxChangePt}={}) {
  if(!Array.isArray(probabilities)||probabilities.length!==6||probabilities.some(x=>!Number.isFinite(x)||x<0))
    throw new Error("probabilities は0以上の有限数値6件（%）が必要です");
  const s=probabilities.reduce((a,b)=>a+b,0);
  if(!(s>0)||Math.abs(s-100)>2) throw new Error("6艇の確率合計は約100%にしてください");
  if(!Number.isInteger(firstCourseBoat)||firstCourseBoat<1||firstCourseBoat>6)
    throw new Error("firstCourseBoat は1～6の艇番です");
  if(![influence,priorRaces,minSample,maxChangePt].every(Number.isFinite)
    || influence<0||influence>1||priorRaces<0||minSample<0||maxChangePt<0||maxChangePt>100)
    throw new Error("補正パラメータが範囲外です");
  const before=probabilities.map(x=>x/s*100);
  const found=condition({venueId,tideName,phase});
  const base={before,firstCourseBoat,venueId,tideName,phase,condition:found,
    settings:{influence,priorRaces,minSample,maxChangePt},shiftPt:0,rawDiffPt:null,weight:null};
  if(!found) return unchanged(base,"該当条件の集計がありません");
  if(found.n<minSample) return unchanged({...base,rawDiffPt:found.p-found.avg},"サンプル数不足");
  if(!Number.isFinite(found.avg)||found.avg<=0||found.avg>=100)
    return unchanged(base,"基準データが不正です");
  const i=firstCourseBoat-1, p=before[i]/100;
  if(p<=0||p>=1) return unchanged(base,"基準1着率が0%または100%で補正できません");
  const safeCond=clamp((found.p/100*found.n+0.5)/(found.n+1),1e-6,1-1e-6);
  const reference=clamp(found.avg/100,1e-6,1-1e-6);
  const weight=influence*(found.n/(found.n+priorRaces));
  const logOddsShift=weight*(logit(safeCond)-logit(reference));
  const theoretical=sigmoid(logit(p)+logOddsShift);
  const revised=clamp(theoretical,p-maxChangePt/100,p+maxChangePt/100);
  const after=before.map((v,j)=>(j===i ? revised*100 : v*(1-revised)/(1-p)));
  // Roundoff: after should sum to 100, and the remainder goes to non-first boats pro rata
  const sumAfter=after.reduce((a,b)=>a+b,0);
  const normalized=after.map(x=>x/sumAfter*100);
  return {...base,status:"ok",reason:"潮汐条件による探索的補正",applied:true,
    rawDiffPt:found.p-found.avg,weight,logOddsShift,shiftPt:normalized[i]-before[i],
    after:normalized,displayedAfter:oneDecimalSum100(normalized)};
}
root.BRCTideCorrectionV1=Object.freeze({
  data:DATA,phases:PHASES,defaults:SETTINGS,condition,adjust
});
})(typeof window!=="undefined"?window:globalThis);


/* V2: 本番計算に触れない潮汐分類と管理者シャドー判定 */
(function(root){
'use strict';
const core=root.BRCTideCorrectionV1;
const VALID_TIDES=new Set(['大潮','中潮','小潮','若潮','長潮']);
const DAY=86400000;
const fail=(reason, meta={})=>({status:'skip',reason,...meta});
function localParts(targetJst){
  if(typeof targetJst!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(targetJst)) return null;
  const iso=targetJst.length===16?targetJst+':00':targetJst;
  const epoch=Date.parse(iso+'+09:00');
  if(!Number.isFinite(epoch))return null;
  const d=new Date(epoch+9*3600000);
  if([d.getUTCFullYear(),d.getUTCMonth()+1,d.getUTCDate(),d.getUTCHours(),d.getUTCMinutes()].join('|')!==
    [Number(iso.slice(0,4)),Number(iso.slice(5,7)),Number(iso.slice(8,10)),Number(iso.slice(11,13)),Number(iso.slice(14,16))].join('|'))return null;
  return {epoch,day:iso.slice(0,10),clock:iso.slice(11,16),min:Number(iso.slice(11,13))*60+Number(iso.slice(14,16))};
}
function parseUnix(v){
  const n=Number(v);
  if(!Number.isFinite(n)||n<=0)return NaN;
  return n>=1e11?n:n*1000;
}
function getMap(payload){
  if(payload&&payload.tide&&payload.tide.chart)return payload.tide.chart;
  if(payload&&payload.chart)return payload.chart;
  return payload;
}
function chooseChart(payload,date){
  const map=getMap(payload);
  return map&&typeof map==='object'&&Object.prototype.hasOwnProperty.call(map,date)?map[date]:null;
}
function eventTimes(chart,day){
  const evs=[];
  for(const [k,label] of [['flood','満潮付近'],['edd','干潮付近']]){
    for(const ev of (Array.isArray(chart[k])?chart[k]:[])){
      if(typeof ev.time!=='string'||!/^\d{1,2}:\d{2}$/.test(ev.time))continue;
      const [h,m]=ev.time.split(':').map(Number);
      if(h>23||m>59)continue;
      const t=Date.parse(`${day}T${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:00+09:00`);
      evs.push({t,label});
    }
  }
  return evs;
}
function classify({tidePayload,targetJst,nearMinutes=25,flatCmPerMinute=0.015}={}){
  const at=localParts(targetJst);
  if(!at)return fail('発走予定時刻が不正です');
  if(!Number.isFinite(nearMinutes)||nearMinutes<0||nearMinutes>90||!Number.isFinite(flatCmPerMinute)||flatCmPerMinute<0)return fail('潮汐分類設定が不正です');
  const chart=chooseChart(tidePayload,at.day);
  if(!chart || !Array.isArray(chart.tide) || chart.tide.length<2)return fail('指定日の潮汐データなし（他の日付への代用禁止）',{day:at.day});
  const tideName=chart.moon?.title||chart.tide_name||'';
  if(!VALID_TIDES.has(tideName))return fail('潮回り名が不明です',{day:at.day});
  if(at.min<=nearMinutes || at.min>=1440-nearMinutes){
    // 近接日の潮時刻が省略されると境界を誤判定するため安全側で停止
    const baseDay=Date.parse(at.day+'T00:00:00+09:00');
    const prev=new Date(baseDay-DAY+9*3600000).toISOString().slice(0,10);
    const next=new Date(baseDay+DAY+9*3600000).toISOString().slice(0,10);
    if(!chooseChart(tidePayload,prev)||!chooseChart(tidePayload,next))return fail('日付境界付近：前日と翌日の潮汐が必要',{day:at.day});
  }
  const points=chart.tide.map(p=>({t:parseUnix(p.unix),cm:Number(p.cm)}));
  if(points.some(x=>!Number.isFinite(x.t)||!Number.isFinite(x.cm)) ||points.some((x,i)=>i>0&&x.t<=points[i-1].t))return fail('潮位点の形式・時刻順が不正です',{day:at.day});
  if(at.epoch<points[0].t||at.epoch>points[points.length-1].t)return fail('時刻が潮位点の観測範囲外です',{day:at.day});
  let pos=-1;
  for(let i=0;i<points.length-1;i++)if(points[i].t<=at.epoch&&at.epoch<=points[i+1].t){pos=i;break;}
  if(pos<0)return fail('潮位点を補間できません',{day:at.day});
  const p=points[pos], q=points[pos+1], frac=(at.epoch-p.t)/(q.t-p.t);
  const cm=p.cm+(q.cm-p.cm)*frac;
  const events=eventTimes(chart,at.day);
  if(at.min<=nearMinutes||at.min>=1440-nearMinutes){
    // Correct calendar keys in Asia/Tokyo
    const midnightLocal=Date.parse(at.day+'T00:00:00+09:00');
    const prevKey=new Date(midnightLocal-DAY+9*3600000).toISOString().slice(0,10);
    const nextKey=new Date(midnightLocal+DAY+9*3600000).toISOString().slice(0,10);
    events.push(...eventTimes(chooseChart(tidePayload,prevKey),prevKey),...eventTimes(chooseChart(tidePayload,nextKey),nextKey));
  }
  const nearest=events.filter(e=>Math.abs(e.t-at.epoch)<=nearMinutes*60000)
      .sort((a,b)=>Math.abs(a.t-at.epoch)-Math.abs(b.t-at.epoch));
  if(nearest.length>1&&nearest[0].label!==nearest[1].label&&Math.abs(nearest[0].t-at.epoch)===Math.abs(nearest[1].t-at.epoch))
    return fail('満干潮局面が同時に最接近（判定不可）',{day:at.day});
  let phase,method;
  if(nearest.length){phase=nearest[0].label;method='event';}
  else {
    const rate=(q.cm-p.cm)/((q.t-p.t)/60000);
    if(Math.abs(rate)<flatCmPerMinute)return fail('潮位変化が小さく、潮の向きを確定できません',{day:at.day});
    phase=rate>0?'上げ潮':'下げ潮';method='slope';
  }
  return {status:'ok',day:at.day,time:at.clock,tideName,phase,cm,method,
    note:'元集計における潮の局面分類と完全一致する保証はありません'};
}
function shadow({serverVerifiedAdmin=false,v3Verified=false,exhibitionConfirmed=false,
                   venueId,targetJst,tidePayload,probabilities,firstCourseBoat,...options}={}){
  if(serverVerifiedAdmin!==true)return {status:'hidden',reason:'管理者以外には表示しない（サーバー認証必須）'};
  if(v3Verified!==true)return fail('TimeX v3未検証：予測値への接続は停止');
  if(exhibitionConfirmed!==true)return fail('展示・進入が未確定のため停止');
  const tide=classify({tidePayload,targetJst});
  if(tide.status!=='ok')return {status:'skip',reason:tide.reason,tide};
  const result=core.adjust({venueId,tideName:tide.tideName,phase:tide.phase,probabilities,firstCourseBoat,...options});
  return {status:result.status,reason:result.reason,tide,result,
    note:'シャドー比較のみ。BRC表示・確率本体は変更しない'};
}
root.BRCTideResearchV2=Object.freeze({classify,shadow,chooseChart});
})(typeof window!=='undefined'?window:globalThis);

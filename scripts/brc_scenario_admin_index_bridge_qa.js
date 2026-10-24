/* BRC_SCENARIO_2ND3RD_ADMIN_QA_BRIDGE_V1
 * REVIEW-ONLY: no server-side authorization. DO NOT deploy without
 * authenticated Worker read path and explicit release approval.
 */
(function(){
"use strict";
if(window.BRC_Scenario23Admin)return;
const ID="brcScenario23AdminContainer",PANEL="playerScenarioDetail";
function officialPct(n,d){const q=Math.floor(1000*n/d),r=1000*n%d;return (q+(2*r>d||(2*r===d&&q%2===1)?1:0))/10;}
const MODES=["全体","差し","まくり","まくり差し"];
const VENUES=["桐生","戸田","江戸川","平和島","多摩川","浜名湖","蒲郡","常滑","津","三国","びわこ","住之江","尼崎","鳴門","丸亀","児島","宮島","徳山","下関","若松","芦屋","福岡","唐津","大村"];
let data=null,selectedReg="";
const state={venue:"10",course:1,first:1,second:2,scope:"player",mode:"全体",stage:"before"};
function admin(){
  try{
    return (typeof BRC_ADMIN_ACTIVE!=="undefined"&&BRC_ADMIN_ACTIVE===true)
      &&(typeof BRC_MEMBER_ACTIVE!=="undefined"&&BRC_MEMBER_ACTIVE===true)
      &&!document.body?.classList.contains("brc-admin-public-view")
      &&!(typeof window.brcGetAdminViewMode==="function" && window.brcGetAdminViewMode()==="public");
  }catch(_){return false;}
}
function el(tag,text,cls){
  const x=document.createElement(tag);if(text!=null)x.textContent=String(text);
  if(cls)x.className=cls;return x;
}
function validate(m){
  if(!m||m.schema!=="BRC_123_OFFICIAL_RESEARCH_V1"
      ||m.source_coverage_kind!=="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"
      ||m.productionApproved!==false||m.publicVisible!==false
      ||m.complete_history_from_2023_approved!==false
      ||!(m.minimum_n_per_conditional_cell>=5)||!Array.isArray(m.source_windows)
      ||!m.source_windows.length||!Array.isArray(m.research_rows))throw Error("BAD_SOURCE");
  const lookup=new Map();
  for(const r of m.research_rows){
    const v=r.venue_code,c=r.winning_course,f=r.first_boat,s=r.second_boat;
    const n=r.denominator_n,cells=r.third_boat_rates,reg=r.winner_reg;
    if(!/^(0[1-9]|1\d|2[0-4])$/.test(v)||!Number.isInteger(c)||c<1||c>6
      ||!MODES.includes(r.method)||!(reg==="*"||/^\d{4}$/.test(reg))
      ||!Number.isInteger(f)||!Number.isInteger(s)||f<1||f>6||s<1||s>6||f===s
      ||!Number.isInteger(n)||n<5||!Array.isArray(cells)||cells.length!==4)
      throw Error("BAD_COHORT");
    const available=[1,2,3,4,5,6].filter(b=>b!==f&&b!==s);
    if(cells.some(x=>!x||!available.includes(x.boat)||!Number.isInteger(x.n)
      ||x.n<0||!Number.isFinite(x.pct)||Math.abs(x.pct-officialPct(x.n,n))>0.001)
      ||new Set(cells.map(x=>x.boat)).size!==4
      ||cells.reduce((z,x)=>z+x.n,0)!==n)throw Error("BAD_COUNTS");
    const key=[v,c,r.method,reg,f,s].join("|");
    if(lookup.has(key))throw Error("DUPLICATE");lookup.set(key,r);
  }
  if(!lookup.size)throw Error("EMPTY");return lookup;
}
function selector(host,label,values,current,setter){
  const wrap=el("label",null,"brc-s23-field");wrap.appendChild(el("span",label));
  const pick=el("select");for(const [val,text] of values){
    const opt=el("option",text);opt.value=String(val);pick.appendChild(opt);
  }
  pick.value=String(current);pick.addEventListener("change",()=>{setter(pick.value);draw();});
  wrap.appendChild(pick);host.appendChild(wrap);
}
function draw(){
  const root=document.getElementById(ID);if(!root)return;
  if(!admin()){root.remove();data=null;return;}
  const msg=root.querySelector("[data-brc-s23-status]");
  const nEl=root.querySelector("[data-brc-s23-n]");
  const grid=root.querySelector("[data-brc-s23-grid]");
  if(!msg||!nEl||!grid)return;grid.replaceChildren();
  let row=null;
  if(state.stage==="after")msg.textContent="展示後の条件は未照合のため非表示です。";
  else if(state.first===state.second)msg.textContent="1着と2着は別の艇を選んでください。";
  else if(!data)msg.textContent="公式K研究JSONを手動で読み込んでください（本番接続なし）。";
  else{
    row=data.get([state.venue,state.course,state.mode,state.scope==="player"?selectedReg:"*",state.first,state.second].join("|"))||null;
    msg.textContent=row?(state.scope==="player"?"選手本人の条件付き公式K実績":"会場全体の実績（選手本人の確率ではありません）")
      :(state.scope==="player"?"本人の母数5未満／未収録。会場実績は手動切替してください。":"会場条件の母数5未満／未収録（0%の意味ではありません）。");
  }
  nEl.textContent=row?"集計母数 N="+row.denominator_n:"母数未確認";
  for(let boat=1;boat<=6;boat++){
    const excluded=boat===state.first||boat===state.second;
    const stat=row?.third_boat_rates?.find(x=>x.boat===boat);
    const tile=el("div",null,"brc-s23-boat brc-s23-boat-"+boat+(excluded?" is-excluded":""));
    tile.appendChild(el("b",boat+"号艇"));
    tile.appendChild(el("strong",excluded?"—":stat?stat.pct.toFixed(1)+"%":"—"));
    tile.appendChild(el("small",excluded?"着外条件":stat?"n="+stat.n:"未算出"));
    grid.appendChild(tile);
  }
}
function mount(reg){
  const pane=document.getElementById(PANEL);if(!pane)return false;
  const old=document.getElementById(ID);if(old)old.remove();
  if(!admin()){data=null;selectedReg="";return false;}
  selectedReg=String(reg||"");if(!/^\d{4}$/.test(selectedReg))return false;
  const root=el("section",null,"brc-s23-qa");root.id=ID;
  root.appendChild(el("h3","2着別3着率｜管理者検証"));
  root.appendChild(el("p","2023年以降の全履歴ではありません。既存の展開率・予測値には加算しません。","brc-s23-note"));
  const fields=el("div",null,"brc-s23-controls");root.appendChild(fields);
  selector(fields,"会場",VENUES.map((x,i)=>[String(i+1).padStart(2,"0"),x]),state.venue,x=>state.venue=x);
  const boatValues=[1,2,3,4,5,6].map(i=>[i,i+"号艇"]);
  selector(fields,"勝者実進入",[1,2,3,4,5,6].map(i=>[i,i]),state.course,x=>state.course=+x);
  selector(fields,"1着艇",boatValues,state.first,x=>state.first=+x);
  selector(fields,"2着艇",boatValues,state.second,x=>state.second=+x);
  selector(fields,"比較区分",[["player","選手本人"],["venue","会場全体"]],state.scope,x=>state.scope=x);
  selector(fields,"展示",[["before","展示前"],["after","展示後（未検証）"]],state.stage,x=>state.stage=x);
  const modes=el("div",null,"brc-s23-modes");root.appendChild(modes);
  for(const m of MODES){
    const btn=el("button",m);btn.type="button";btn.setAttribute("aria-pressed",String(m===state.mode));
    btn.addEventListener("click",()=>{state.mode=m;for(const x of modes.children)x.setAttribute("aria-pressed",String(x===btn));draw();});
    modes.appendChild(btn);
  }
  const status=el("p",null,"brc-s23-note");status.setAttribute("data-brc-s23-status","");root.appendChild(status);
  const nEl=el("p",null,"brc-s23-note");nEl.setAttribute("data-brc-s23-n","");root.appendChild(nEl);
  const grid=el("div",null,"brc-s23-grid");grid.setAttribute("data-brc-s23-grid","");root.appendChild(grid);
  const local=el("label",null,"brc-s23-note");local.appendChild(el("span","検証用JSONファイルを読み込み（研究データをサイトへ配信しません）"));
  const file=el("input");file.type="file";file.accept=".json,application/json";
  file.addEventListener("change",async()=>{
    if(!admin()){root.remove();return;}
    const picked=file.files&&file.files[0];if(!picked)return;
    try{
      if(picked.size>6_000_000)throw Error("SIZE");
      const loaded=validate(JSON.parse(await picked.text()));
      if(!admin()){root.remove();return;}data=loaded;draw();
    }catch(_){data=null;draw();status.textContent="JSON検証失敗。表示を中止しました。";}
  });
  local.appendChild(file);root.appendChild(local);
  pane.appendChild(root);draw();return true;
}
const css=[
"#brcScenario23AdminContainer{margin:16px 0 0;border:1px solid #41627b;border-radius:12px;padding:12px;background:#101e32;color:#f0f5ff}",
".brc-s23-note{font-size:12px;color:#b1c8da}.brc-s23-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:7px}",
".brc-s23-field{display:flex;flex-direction:column;gap:3px;font-size:12px;color:#acc4d8}",
".brc-s23-field select,.brc-s23-note input{background:#071523;color:#f0f5ff;padding:7px;border:1px solid #39536a;border-radius:7px;max-width:100%}",
".brc-s23-modes{display:flex;gap:5px;flex-wrap:wrap;margin:12px 0}.brc-s23-modes button{background:#102b46;color:#edf4ff;border:1px solid #3c5e7a;border-radius:7px;padding:6px}",
".brc-s23-modes button[aria-pressed=true]{border-color:#6bbbef;background:#214f74}",
".brc-s23-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px}",
".brc-s23-boat{position:relative;display:flex;flex-direction:column;gap:2px;align-items:center;min-width:0;padding:8px 1px 5px;border:1px solid #34516a;border-radius:7px;font-size:12px}",
".brc-s23-boat:before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:var(--c)}",
".brc-s23-boat-1{--c:#e3e8ef}.brc-s23-boat-2{--c:#999}.brc-s23-boat-3{--c:#ea656a}",
".brc-s23-boat-4{--c:#569dff}.brc-s23-boat-5{--c:#f9ce56}.brc-s23-boat-6{--c:#58ca83}",
".brc-s23-boat strong{font-size:15px}.brc-s23-boat small{font-size:10px}.brc-s23-boat.is-excluded{opacity:.35}"
].join("\n");
const style=el("style",css);style.id="brc-s23-qa-style";
if(!document.getElementById(style.id))document.head.appendChild(style);
window.BRC_Scenario23Admin={
  onPlayerRendered(reg){try{return mount(reg);}catch(_){return false;}},
  unmount(){const x=document.getElementById(ID);if(x)x.remove();data=null;selectedReg="";},
  readyForPublic:false,readyForProduction:false
};
})();

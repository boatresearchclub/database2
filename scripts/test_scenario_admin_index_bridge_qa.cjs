/* Offline DOM behavioral tests for native admin-only player scenario bridge. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
class Elem{
  constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.listeners={};
    this.parent=null;this.textContent="";this.className="";this.value="";}
  appendChild(child){child.parent=this;this.children.push(child);return child;}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}
  replaceChildren(){this.children=[];}
  setAttribute(k,v){this.attributes[k]=String(v);}
  getAttribute(k){return this.attributes[k];}
  addEventListener(k,fn){this.listeners[k]=fn;}
  walk(pred){if(pred(this))return this;for(const x of this.children){const found=x.walk(pred);if(found)return found;}return null;}
  findAll(pred){return [...(pred(this)?[this]:[]),...this.children.flatMap(x=>x.findAll(pred))];}
  querySelector(sel){
    const m=/^\[([a-z0-9-]+)\]$/.exec(sel);
    if(!m)throw Error("Unsupported fixture selector "+sel);
    return this.walk(x=>Object.prototype.hasOwnProperty.call(x.attributes,m[1]));
  }
}
const html=new Elem("html"),head=new Elem("head"),body=new Elem("body");
const pane=new Elem("div");pane.id="playerScenarioDetail";
body.appendChild(pane);html.appendChild(head);html.appendChild(body);
let publicView=false;
body.classList={contains:x=>x==="brc-admin-public-view"&&publicView};
const doc={head,body,createElement:tag=>new Elem(tag),
 getElementById:id=>html.walk(x=>x.id===id)};
const context={document:doc,window:{brcGetAdminViewMode:()=>"admin"},
 BRC_ADMIN_ACTIVE:false,BRC_MEMBER_ACTIVE:true};
vm.createContext(context);
vm.runInContext(fs.readFileSync("scripts/brc_scenario_admin_index_bridge_qa.js","utf8"),context);
const bridge=context.window.BRC_Scenario23Admin;
assert.ok(bridge);
assert.equal(bridge.readyForPublic,false);
assert.equal(bridge.readyForProduction,false);
assert.equal(bridge.onPlayerRendered("1234"),false);
assert.equal(doc.getElementById("brcScenario23AdminContainer"),null);
context.BRC_ADMIN_ACTIVE=true;
assert.equal(bridge.onPlayerRendered("1234"),true);
let root=doc.getElementById("brcScenario23AdminContainer");
assert.ok(root);
let selects=root.findAll(x=>x.tag==="select"),file=root.findAll(x=>x.tag==="input")[0];
assert.equal(selects.length,6);
assert.ok(file);assert.equal(file.type,"file");
const row=(reg,n,counts)=>({
 venue_code:"10",winning_course:1,method:"全体",winner_reg:reg,first_boat:1,second_boat:2,
 denominator_n:n,third_boat_rates:[3,4,5,6].map((boat,i)=>({
  boat,n:counts[i],pct:Math.round(1000*counts[i]/n)/10
 }))
});
const source={
 schema:"BRC_123_OFFICIAL_RESEARCH_V1",
 source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
 source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
 minimum_n_per_conditional_cell:5,
 complete_history_from_2023_approved:false,productionApproved:false,publicVisible:false,
 research_rows:[row("1234",5,[1,2,1,1]),row("*",10,[3,3,2,2])]
};
(async()=>{
file.files=[{size:1300,text:async()=>JSON.stringify(source)}];
await file.listeners.change();
const n=root.querySelector("[data-brc-s23-n]");
let grid=root.querySelector("[data-brc-s23-grid]");
let status=root.querySelector("[data-brc-s23-status]");
assert.match(n.textContent,/N=5/);
assert.equal(grid.children.length,6);
assert.equal(grid.children[2].children[1].textContent,"20.0%");
assert.match(status.textContent,/選手本人/);
selects[4].value="venue";selects[4].listeners.change();
assert.match(n.textContent,/N=10/);
assert.match(status.textContent,/会場全体/);
selects[5].value="after";selects[5].listeners.change();
assert.equal(n.textContent,"母数未確認");
assert.match(status.textContent,/未照合/);
context.window.brcGetAdminViewMode=()=>"public";
assert.equal(bridge.onPlayerRendered("1234"),false);
assert.equal(doc.getElementById("brcScenario23AdminContainer"),null);
context.window.brcGetAdminViewMode=()=>"admin";context.BRC_ADMIN_ACTIVE=false;
assert.equal(bridge.onPlayerRendered("1234"),false);
assert.equal(doc.getElementById("brcScenario23AdminContainer"),null);
console.log("SELFTEST_PASS: native player detail admin-only mount, 5N player/10N venue, exhibition and public logout fail closed");
})().catch(err=>{console.error(err);process.exitCode=1;});

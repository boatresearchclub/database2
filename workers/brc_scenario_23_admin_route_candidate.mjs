/**
 * BRC scenario (1st->2nd->3rd) admin read route — INTEGRATION CANDIDATE.
 *
 * IMPORTANT:
 * - NOT a standalone deployable Worker and NOT a substitute for existing
 *   authentication. The only caller is a future existing Worker where
 *   verifyBearerToken() checks real session credentials server-side.
 * - Never authorize using JS globals, a supplied email, "admin=true",
 *   BRC_ADMIN_ACTIVE, or an unverified JWT payload.
 * - loadPrivateMatrix() MUST read a protected Worker binding or private D1
 *   after a validated admin session, NEVER GitHub Pages or static INDEX.
 * - No production approval. No data/prediction/INDEX changes.
 */

import {officialKPercent} from "./brc_scenario_23_percent.mjs";

const MODES = new Set(["全体", "差し", "まくり", "まくり差し"]);
const DATA_SCHEMA = "BRC_123_OFFICIAL_RESEARCH_V1";
const COVERAGE = "DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS";
const API_PATH = "/api/admin/scenario/2nd3rd";
const jsonHeaders = Object.freeze({
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, max-age=0, private",
  "pragma": "no-cache",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "vary": "Origin, Authorization"
});

function safeResponse(status, code, extra={}, headers={}) {
  return new Response(JSON.stringify({ ok: false, error: code, ...extra }), {
    status, headers: { ...jsonHeaders, ...headers }
  });
}
function requireSingle(q,key) {
  const all=q.getAll(key);
  if(all.length!==1)throw Error("INVALID_QUERY");
  return all[0];
}
function boundNumber(value,min,max) {
  if(!/^[0-9]+$/.test(value))throw Error("INVALID_QUERY");
  const result=Number(value);
  if(!Number.isSafeInteger(result)||result<min||result>max)throw Error("INVALID_QUERY");
  return result;
}
function validatedQuery(url) {
  const q=url.searchParams;
  const keys=["venue","course","first","second","method","scope","stage","player_reg"];
  for(const key of q.keys())if(!keys.includes(key))throw Error("INVALID_QUERY");
  for(const key of keys.filter(x=>x!=="player_reg"))requireSingle(q,key);
  const venue=requireSingle(q,"venue");
  if(!/^(0[1-9]|1[0-9]|2[0-4])$/.test(venue))throw Error("INVALID_QUERY");
  const course=boundNumber(requireSingle(q,"course"),1,6);
  const first=boundNumber(requireSingle(q,"first"),1,6);
  const second=boundNumber(requireSingle(q,"second"),1,6);
  if(first===second)throw Error("INVALID_QUERY");
  const method=requireSingle(q,"method");
  if(!MODES.has(method))throw Error("INVALID_QUERY");
  const stage=requireSingle(q,"stage");
  if(stage!=="before" && stage!=="after")throw Error("INVALID_QUERY");
  const scope=requireSingle(q,"scope");
  if(!["player","venue"].includes(scope))throw Error("INVALID_QUERY");
  let reg="*";
  if(scope==="player") {
    reg=requireSingle(q,"player_reg");
    if(!/^[0-9]{4}$/.test(reg))throw Error("INVALID_QUERY");
  }else if(q.has("player_reg")) {
    throw Error("INVALID_QUERY");
  }
  return {venue,course,first,second,method,stage,scope,reg};
}
function validateStoredMatrix(m) {
  if(!m||m.schema!==DATA_SCHEMA||m.source_coverage_kind!==COVERAGE
    ||m.productionApproved!==false||m.publicVisible!==false
    ||m.complete_history_from_2023_approved!==false
    ||!Number.isInteger(m.minimum_n_per_conditional_cell)
    ||m.minimum_n_per_conditional_cell<5
    ||!Array.isArray(m.source_windows)||!m.source_windows.length
    ||!Array.isArray(m.research_rows)||!m.research_rows.length
    ||!Number.isInteger(m.number_of_verified_races)
    ||m.number_of_verified_races<1)throw Error("SOURCE_NOT_VERIFIED");
  for(const win of m.source_windows) {
    if(!/^\d{4}-\d\d-\d\d$/.test(win.start)
        || !/^\d{4}-\d\d-\d\d$/.test(win.end)
        || !Number.isInteger(win.verified_calendar_days)
        || win.verified_calendar_days<1)throw Error("SOURCE_NOT_VERIFIED");
  }
}
function validateCohort(row,p) {
  if(row.venue_code!==p.venue||row.winning_course!==p.course
    ||row.method!==p.method||row.winner_reg!==p.reg
    ||row.first_boat!==p.first||row.second_boat!==p.second
    ||!Number.isInteger(row.denominator_n)||row.denominator_n<5
    ||!Array.isArray(row.third_boat_rates)
    ||row.third_boat_rates.length!==4)throw Error("BAD_COHORT");
  const allowed=[1,2,3,4,5,6].filter(x=>x!==p.first && x!==p.second);
  const boats=new Set();
  let count=0;
  for(const x of row.third_boat_rates){
    if(!x||!allowed.includes(x.boat)||boats.has(x.boat)
      ||!Number.isInteger(x.n)||x.n<0
      ||!Number.isFinite(x.pct)
      ||Math.abs(x.pct-officialKPercent(x.n,row.denominator_n))>0.001)
      throw Error("BAD_COHORT");
    boats.add(x.boat);count+=x.n;
  }
  if(boats.size!==4||count!==row.denominator_n)throw Error("BAD_COHORT");
}
/**
 * Inject these functions ONLY from the existing Worker implementation:
 *
 * verifyBearerToken(token, request) => Promise<{
 *   authenticated:true, member:true, admin:true, subject:string
 * }>
 *
 * loadPrivateMatrix(authenticatedSubject) => Promise<matrix>
 *
 * The verify callback must derive identity and privileges entirely from
 * trusted server-side verification, not a client request/header/JSON claim.
 */
export function createScenario23AdminHandler({
  verifyBearerToken, loadPrivateMatrix, allowedOrigin
}={}) {
  // Nothing loads unless all required server services are truly configured.
  if(typeof verifyBearerToken!=="function"
      ||typeof loadPrivateMatrix!=="function"
      ||typeof allowedOrigin!=="string"
      ||!/^https:\/\//.test(allowedOrigin)
      ||allowedOrigin.endsWith("/"))
    throw Error("SERVER_INTEGRATION_REQUIRED");
  return async function handleScenario23Admin(request) {
    const headers={...jsonHeaders};
    const origin=request.headers.get("Origin");
    if(origin && origin!==allowedOrigin)
      return safeResponse(403,"ORIGIN_NOT_ALLOWED");
    if(origin===allowedOrigin){
      headers["access-control-allow-origin"]=allowedOrigin;
      headers["vary"]="Origin, Authorization";
    }
    const url=new URL(request.url);
    if(url.pathname!==API_PATH)
      return safeResponse(404,"NOT_FOUND",{},headers);
    if(request.method==="OPTIONS"){
      if(origin!==allowedOrigin)
        return safeResponse(403,"ORIGIN_NOT_ALLOWED");
      return new Response(null,{status:204,headers:{
        ...headers,
        "access-control-allow-methods":"GET, OPTIONS",
        "access-control-allow-headers":"Authorization",
        "access-control-max-age":"0"
      }});
    }
    if(request.method!=="GET")
      return safeResponse(405,"METHOD_NOT_ALLOWED",{},headers);

    const authorization=request.headers.get("Authorization")||"";
    const bearer=/^Bearer ([A-Za-z0-9._~+/-]{16,4096})$/.exec(authorization);
    if(!bearer)
      return safeResponse(401,"LOGIN_REQUIRED",{},headers);
    // In particular, an Authorization header containing "admin" is NOT
    // authority; only the injected server verifier can establish it.
    let actor;
    try {
      actor=await verifyBearerToken(bearer[1],request);
    }catch(_){
      return safeResponse(401,"LOGIN_REQUIRED",{},headers);
    }
    if(!actor || actor.authenticated!==true || actor.member!==true
      ||actor.admin!==true ||typeof actor.subject!=="string"
      ||actor.subject.length===0)
      return safeResponse(403,"ADMIN_REQUIRED",{},headers);

    let p;
    try {p=validatedQuery(url);}
    catch(_){return safeResponse(400,"INVALID_QUERY",{},headers);}

    if(p.stage==="after")
      return safeResponse(409,"AFTER_EXHIBITION_NOT_VERIFIED",{},headers);

    let source;
    try{
      source=await loadPrivateMatrix(actor.subject);
      validateStoredMatrix(source);
    }catch(_){
      return safeResponse(503,"RESEARCH_DATA_UNAVAILABLE",{},headers);
    }
    const matches=source.research_rows.filter(row=>
      row.venue_code===p.venue && row.winning_course===p.course
      && row.method===p.method && row.winner_reg===p.reg
      && row.first_boat===p.first && row.second_boat===p.second
    );
    if(matches.length>1)
      return safeResponse(503,"RESEARCH_DATA_UNAVAILABLE",{},headers);
    if(!matches.length)
      return new Response(JSON.stringify({
        ok:true,status:"MISSING_OR_N_LT_5",scope:p.scope,
        denominator_n:null,third_boat_rates:[],
        not_zero_percent:true,approvedForPredictions:false
      }),{status:200,headers});
    const row=matches[0];
    try{validateCohort(row,p);}
    catch(_){return safeResponse(503,"RESEARCH_DATA_UNAVAILABLE",{},headers);}
    return new Response(JSON.stringify({
      ok:true,status:"RESEARCH_N_GE_5",scope:p.scope,
      venue_code:p.venue,winning_course:p.course,
      method:p.method,winner_reg:p.reg,
      first_boat:p.first,second_boat:p.second,
      denominator_n:row.denominator_n,
      third_boat_rates:row.third_boat_rates.map(x=>({
        boat:x.boat,n:x.n,pct:officialKPercent(x.n,row.denominator_n)
      })),
      source_windows:source.source_windows.map(x=>({
        start:x.start,end:x.end,verified_calendar_days:x.verified_calendar_days
      })),
      complete_history_from_2023_approved:false,
      after_exhibition_verified:false,
      approvedForPredictions:false,
      productionApproved:false
    }),{status:200,headers});
  };
}

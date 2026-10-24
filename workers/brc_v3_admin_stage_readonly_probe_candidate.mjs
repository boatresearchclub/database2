/**
 * DEPRECATED FOR CURRENT WORKER: the historical Worker does not implement
 * GET /stage-context-presence. Use brc_v3_admin_predict_diagnostic_candidate.mjs
 * with authenticated POST /predict-timex-v3 instead.
 *
 * BRC TimeX v3 admin-only staging diagnostic CLIENT CANDIDATE.
 *
 * READ-ONLY GET of fixed stage endpoint: /stage-context-presence
 * NEVER performs predictions, KV writes or Worker deployments.
 * NEVER reads localStorage, cookies, global bearer strings or exposes JWT.
 * Neither HTTP 200 nor a presence probe alone proves v3 math is operational.
 *
 * Future use in existing BRC admin UI:
 *   getSession = () => brcEnsureFreshSession()
 *   isAdminUi = () => BRC_ADMIN_ACTIVE === true &&
 *                BRC_MEMBER_ACTIVE === true &&
 *                brcGetAdminViewMode() !== "public"
 *
 * The full BRC INDEX is not changed here. This is a diagnostic candidate
 * until reviewed with the deployed Worker/INDEX and live admin account.
 */
export const V3_STAGE_ORIGIN="https://brc-timex-v3-test.sk48159212.workers.dev";
const PATH="/stage-context-presence";
const ALLOWED_CODES=new Set(Array.from({length:24},(_,i)=>String(i+1).padStart(2,"0")));
const TOKEN=/^[A-Za-z0-9._~+/-]{16,4096}$/;
const SAFE_META_CODES=new Set([
 "ok","ready","available","unavailable","missing","context_missing",
 "stored_context_found","not_logged_in","unauthorized","not_found",
 "error","stale","no_context","BRC_V3_STAGE_KV_READONLY_V3"
]);

function classify(code,details){
  if(code===401)return "AUTH_REQUIRED_OR_SESSION_EXPIRED";
  if(code===403)return "ADMIN_NOT_AUTHORIZED";
  if(code===404)return "PRESENCE_ROUTE_NOT_INSTALLED_OR_CONTEXT_MISSING";
  if(code===422)return "STAGE_CONTEXT_UNAVAILABLE_REPORTED";
  if(code===429)return "WORKER_RATE_LIMITED";
  if(code>=500)return "WORKER_INTERNAL_FAILURE";
  if(code!==200)return "UNEXPECTED_STAGE_STATUS";
  // A 200 can be either a presence metadata response or unrelated Worker
  // response. Never elevate v3Verified without an actual calculated result.
  if(details?.status==="unavailable"||details?.error==="unavailable")
    return "STAGE_CONTEXT_UNAVAILABLE_REPORTED";
  if(details?.present===false||details?.exists===false)
    return "STAGE_CONTEXT_NOT_STORED";
  if(details?.present===true||details?.exists===true)
    return "STAGE_CONTEXT_PRESENT_CALCULATION_UNTESTED";
  return "STAGE_METADATA_ROUTE_REACHED_CONTENT_UNCONFIRMED";
}
function sanitizePayload(json) {
  if(!json||typeof json!=="object"||Array.isArray(json))return {};
  const x={};
  for(const key of ["status","error","reason","code","probe_version"]){
    if(typeof json[key]==="string"&&SAFE_META_CODES.has(json[key])) x[key]=json[key];
  }
  // Presence booleans are metadata only, no boat data, names, rates or tokens.
  for(const key of ["present","exists"]){
    if(typeof json[key]==="boolean")x[key]=json[key];
  }
  return x;
}
function dateOnly(value){
 if(typeof value!=="string"||!/^20\d\d-\d\d-\d\d$/.test(value))throw Error("INVALID_SELECTION");
 const t=new Date(value+"T00:00:00Z");
 if(!Number.isFinite(t.getTime())||t.toISOString().slice(0,10)!==value)
   throw Error("INVALID_SELECTION");
 return value;
}
export function createV3AdminStageProbe({
 getFreshSession,isAdminUi,fetchImpl,origin=V3_STAGE_ORIGIN
}={}){
 if(typeof getFreshSession!=="function"||typeof isAdminUi!=="function"
   ||typeof fetchImpl!=="function"||origin!==V3_STAGE_ORIGIN)
   throw Error("NATIVE_ADMIN_SESSION_INTEGRATION_REQUIRED");
 return Object.freeze({
  readyForProduction:false,
  async run({date,venue_code,race_no}={}){
   if(isAdminUi()!==true)return {status:"ADMIN_VIEW_REQUIRED",v3Verified:false};
   const day=dateOnly(date);
   if(!ALLOWED_CODES.has(venue_code)||!Number.isInteger(race_no)||race_no<1||race_no>12)
     throw Error("INVALID_SELECTION");
   let session;
   try{session=await getFreshSession();}
   catch(_){return {status:"SESSION_UNVERIFIED",v3Verified:false};}
   const token=session?.access_token;
   if(typeof token!=="string"||!TOKEN.test(token))
     return {status:"SESSION_UNVERIFIED",v3Verified:false};
   if(isAdminUi()!==true)return {status:"ADMIN_VIEW_REQUIRED",v3Verified:false};
   const q=new URLSearchParams({date:day,venue_code,race_no:String(race_no)});
   let response;
   try{
    response=await fetchImpl(origin+PATH+"?"+q.toString(),{
      method:"GET",mode:"cors",cache:"no-store",
      credentials:"omit",redirect:"error",
      headers:{Authorization:"Bearer "+token,Accept:"application/json"}
    });
   }catch(_){
    return {status:"STAGE_NETWORK_OR_CORS_UNAVAILABLE",v3Verified:false};
   }
   // Never store, log or return the bearer token, arbitrary Worker response,
   // PII, event names, per-racer data, coefficients or prediction output.
   let meta={};
   const type=(response?.headers?.get("content-type")||"").toLowerCase();
   const length=response?.headers?.get("content-length");
   if(type.includes("application/json")&&
      (length===null||(/^\d+$/.test(length)&&Number(length)<=4096))){
     try{
       const body=await response.text();
       if(body.length<=4096)meta=sanitizePayload(JSON.parse(body));
     }catch(_){}
   }
   const code=Number.isInteger(response?.status)?response.status:0;
   return {
     schema:"BRC_V3_ADMIN_STAGE_PRESENCE_PROBE_V1",
     date:day,venue_code,race_no,
     http:code,status:classify(code,meta),
     metadata:meta,
     v3Verified:false,kv_readback_proven:false,
     v3_prediction_verified:false,
     public_v2_unchanged:true,
     productionApproved:false,
     nextStep:code===422
       ?"Examine authenticated Worker context key/date, binding, and input validation internally; never copy JWT"
       :"Require authenticated v3 prediction + four-rate consistency before enabling the admin UI"
   };
  }
 });
}

/**
 * TimeX v3 administrator authenticated PREDICTION diagnostic for the actual
 * deployed staging contract: POST /predict-timex-v3. Non-production candidate.
 * This method can use a rate-limiter token; call once per manually selected
 * race, NEVER polling. It does not ingest or modify race/forecast KV.
 *
 * Native session comes from BRC brcEnsureFreshSession; no localStorage/secret
 * harvesting; origin is hardcoded to the existing staging Worker. No JWT,
 * raw forecast, individual player data, or error body is returned or logged.
 */
export const V3_PREDICT_STAGE="https://brc-timex-v3-test.sk48159212.workers.dev";
const SAFE_REASON=new Set([
 "date_not_today_jst","race_context_missing","race_context_invalid",
 "live_service_http_error","live_service_invalid_json","metrics_failed",
 "strict_live_exhibition_requirements_not_met","not_logged_in",
 "invalid_session","invalid_user","membership_inactive","admin_only",
 "forbidden_origin","server_not_configured","rate_limited",
 "unavailable","excluded","ready","invalid_race"
]);
const TOKEN=/^[A-Za-z0-9._~+/-]{16,4096}$/;
const DATE=/^20\d\d-\d\d-\d\d$/;
function inputCheck({date,venue_code,race_no}={}){
 if(typeof date!=="string"||!DATE.test(date)||
    !Number.isFinite(new Date(date+"T00:00:00Z").getTime())||
    new Date(date+"T00:00:00Z").toISOString().slice(0,10)!==date||
    typeof venue_code!=="string"||
    !/^(0[1-9]|1[0-9]|2[0-4])$/.test(venue_code)||
    venue_code==="03"||
    !Number.isInteger(race_no)||race_no<1||race_no>12)
   throw Error("INVALID_RACE_SELECTION");
 return {date,venue_code,race_no};
}
function inspectRates(payload){
 const arrays=["wins","seconds","thirds","top3s"];
 const grouped=[];
 for(const name of arrays){
  const values=payload?.[name];
  if(!Array.isArray(values)||values.length!==6)return false;
  const n=new Map();
  for(const x of values){
   const c=x?.course,p=x?.pctFloat;
   if(!Number.isInteger(c)||c<1||c>6||n.has(c)||
      typeof p!=="number"||!Number.isFinite(p)||p<0||p>100)return false;
   n.set(c,p);
  }
  if(n.size!==6)return false;
  grouped.push(n);
 }
 const sums=grouped.map(g=>[...g.values()].reduce((a,b)=>a+b,0));
 if(Math.abs(sums[0]-100)>0.01||Math.abs(sums[1]-100)>0.01||
    Math.abs(sums[2]-100)>0.01||Math.abs(sums[3]-300)>0.02)
    return false;
 for(let i=1;i<=6;i++){
  const [w,sec,third,top3]=grouped.map(g=>g.get(i));
  if(Math.abs(w+sec+third-top3)>0.01||w+sec+third>100.01)
    return false;
 }
 return true;
}
function metadata(json){
 if(!json||typeof json!=="object"||Array.isArray(json))return {};
 const x={};
 for(const key of ["reason","error","status"]){
  const v=json[key];
  if(typeof v==="string"&&SAFE_REASON.has(v))x[key]=v;
 }
 if(typeof json.upstream_http==="number"&&
    Number.isInteger(json.upstream_http)&&json.upstream_http>=100&&json.upstream_http<=599)
  x.upstream_http=json.upstream_http;
 if(json.diagnostic_version==="brc-v3-422-phase-v1")
  x.diagnostic_version=json.diagnostic_version;
 return x;
}
function classification(code,info){
 if(code===401)return "SESSION_EXPIRED_OR_UNAUTHENTICATED";
 if(code===403)return info.error==="admin_only"?"WORKER_ADMIN_IDENTITY_DENIED":"WORKER_FORBIDDEN_OR_CORS";
 if(code===404)return "PREDICT_ROUTE_NOT_INSTALLED";
 if(code===429)return "V3_RATE_LIMITED";
 if(code===422){
  if(info.reason==="live_service_http_error"&&info.upstream_http===404)
   return "LIVE_EXHIBITION_KV_RACE_NOT_FOUND";
  if(info.reason==="race_context_missing")return "STAGE_KV_RACE_CONTEXT_MISSING";
  if(info.reason==="race_context_invalid")return "STAGE_KV_RACE_CONTEXT_INVALID";
  if(info.reason==="date_not_today_jst")return "STAGE_JST_DATE_MISMATCH";
  if(info.reason==="live_service_http_error")return "UPSTREAM_LIVE_API_FAILURE";
  if(info.reason==="live_service_invalid_json")return "UPSTREAM_LIVE_API_JSON_INVALID";
  if(info.reason==="metrics_failed")return "V3_MODEL_FOUR_METRIC_COMPUTATION_FAILED";
  return "UNDIAGNOSED_422_CHECK_WORKER_PATCH";
 }
 if(code>=500)return "V3_WORKER_OR_UPSTREAM_INTERNAL_FAILURE";
 if(code!==200)return "UNEXPECTED_STAGE_RESPONSE";
 if(info.status==="excluded")return "EXHIBITION_OR_ENTRY_EXCLUDED";
 if(info.status==="ready")return "REQUIRES_FOUR_RATE_VALIDATION";
 return "UNEXPECTED_V3_STATUS";
}
export function createAdminV3PredictionDiagnostic({
 getFreshSession,isAdminUi,fetchImpl
}={}){
 if(typeof getFreshSession!=="function"||typeof isAdminUi!=="function"||
    typeof fetchImpl!=="function")throw Error("NATIVE_ADMIN_SESSION_REQUIRED");
 let busy=false;
 return Object.freeze({
  readyForProduction:false,
  async check(selection){
   if(isAdminUi()!==true)return {phase:"ADMIN_VIEW_REQUIRED",serverFourMetricsValid:false,displayedV3Verified:false};
   const id=inputCheck(selection);
   if(busy)return {phase:"DIAGNOSTIC_ALREADY_RUNNING",serverFourMetricsValid:false,displayedV3Verified:false};
   busy=true;
   try{
    let session;
    try{session=await getFreshSession();}
    catch(_){return {phase:"SESSION_UNVERIFIED",serverFourMetricsValid:false,displayedV3Verified:false};}
    const token=session?.access_token;
    if(typeof token!=="string"||!TOKEN.test(token))
      return {phase:"SESSION_UNVERIFIED",serverFourMetricsValid:false,displayedV3Verified:false};
    if(isAdminUi()!==true)return {phase:"ADMIN_VIEW_REQUIRED",serverFourMetricsValid:false,displayedV3Verified:false};
    let resp;
    try{
     resp=await fetchImpl(V3_PREDICT_STAGE+"/predict-timex-v3",{
      method:"POST",mode:"cors",redirect:"error",credentials:"omit",cache:"no-store",
      headers:{"Authorization":"Bearer "+token,"Accept":"application/json",
               "Content-Type":"application/json"},
      body:JSON.stringify(id)
     });
    }catch(_){return {phase:"NETWORK_OR_CORS_FAILURE",serverFourMetricsValid:false,displayedV3Verified:false};}
    let json={};
    const ct=(resp?.headers?.get("content-type")||"").toLowerCase();
    const len=resp?.headers?.get("content-length");
    if(ct.includes("application/json")&&(len===null||(/^\d+$/.test(len)&&Number(len)<=16384))){
      try{
       const raw=await resp.text();
       if(raw.length<=16384){const parsed=JSON.parse(raw);if(parsed&&typeof parsed==="object"&&!Array.isArray(parsed))json=parsed;}
      }catch(_){}
    }
    // The user may log out, lose membership or switch to public view while
    // the authenticated request is in flight. Discard even a valid 200 response
    // instead of presenting stale admin-only diagnostic information.
    if(isAdminUi()!==true)return {
      phase:"ADMIN_VIEW_REQUIRED",serverFourMetricsValid:false,displayedV3Verified:false
    };
    // A successful HTTP request alone does not prove v3 is applied in INDEX.
    const code=Number.isInteger(resp?.status)?resp.status:0;
    const meta=metadata(json);
    const valid=code===200&&meta.status==="ready"&&
      json.date===id.date&&json.venue_code===id.venue_code&&
      json.race_no===id.race_no&&inspectRates(json);
    const phase=valid?"FOUR_METRIC_SERVER_RESPONSE_VALID":classification(code,meta);
    return {
     schema:"BRC_ADMIN_V3_AUTH_PREDICT_QA_V1",
     selection:id,http:code,phase,
     error_code:meta.reason||meta.error||null,
     upstream_http:meta.upstream_http??null,
     worker_reason_codes_available:meta.diagnostic_version==="brc-v3-422-phase-v1",
     serverFourMetricsValid:valid,
     displayedV3Verified:false,
     generalMemberV2Unchanged:true,
     workerOrKvModified:false,
     nextStep:valid?"Compare returned four metrics to actual admin DOM; keep v2 for ordinary users":
       "Inspect stage KV identity, current-date live-exhibition response, or Worker model according to phase"
    };
   }finally{busy=false;}
  }
 });
}

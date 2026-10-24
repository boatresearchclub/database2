/**
 * Read-only frontend client for the FUTURE BRC manager scenario Worker route.
 * NOT WIRED to live BRC session, not emitted by INDEX, NOT deployed.
 *
 * The UI check below is convenience only. Authorization occurs exclusively
 * in the server's verifyBearerToken, and API route is not live yet.
 */
const METHODS=new Set(["全体","差し","まくり","まくり差し"]);
export function createScenario23ReadClient({getSessionToken,isAdminUi,fetchImpl,workerOrigin}={}){
  if(typeof getSessionToken!=="function"||typeof isAdminUi!=="function"
    ||typeof fetchImpl!=="function"
    ||typeof workerOrigin!=="string"
    ||!/^https:\/\//.test(workerOrigin)||workerOrigin.endsWith("/"))
    throw Error("AUTH_INTEGRATION_NOT_CONFIGURED");
  let url;
  try{url=new URL(workerOrigin);}
  catch(_){throw Error("AUTH_INTEGRATION_NOT_CONFIGURED");}
  if(url.pathname!=="/"||url.search||url.hash)
    throw Error("AUTH_INTEGRATION_NOT_CONFIGURED");
  function params({venue,course,first,second,method,scope,playerReg,stage="before"}){
    if(!/^(0[1-9]|1\d|2[0-4])$/.test(venue)
      ||![course,first,second].every(n=>Number.isInteger(n)&&n>=1&&n<=6)
      ||first===second||!METHODS.has(method)
      ||!["venue","player"].includes(scope)
      ||(scope==="player"&&!/^[0-9]{4}$/.test(playerReg))
      ||stage!=="before")throw Error("INVALID_SELECTION_OR_UNVERIFIED_EXHIBITION");
    const q=new URLSearchParams({venue,course:String(course),
      first:String(first),second:String(second),method,scope,stage});
    if(scope==="player")q.set("player_reg",playerReg);
    return q;
  }
  // One mounted player/venue panel may switch race or account while an
  // async read is in flight. The newest selection owns the render result.
  let generation=0;
  const stale=(mine)=>mine!==generation || isAdminUi()!==true;
  return {
    invalidate(){generation++;},
    async load(selection){
      const mine=++generation;
      // No storage, cookie, broad response/cache, redirects, generic requests
      // or personal-identifying contact details are needed.
      if(isAdminUi()!==true)return {status:"ADMIN_VIEW_REQUIRED",rates:[]};
      const q=params(selection);
      let token;
      try{token=await getSessionToken();}
      catch(_){return {status:"SESSION_UNVERIFIED",rates:[]};}
      if(stale(mine))return {status:"STALE_REQUEST_SUPPRESSED",rates:[]};
      if(typeof token!=="string"||!/^[-._~+\/A-Za-z0-9]{16,4096}$/.test(token))
        return {status:"SESSION_UNVERIFIED",rates:[]};
      if(isAdminUi()!==true)return {status:"ADMIN_VIEW_REQUIRED",rates:[]};
      let resp;
      try{
        resp=await fetchImpl(workerOrigin+"/api/admin/scenario/2nd3rd?"+q.toString(),{
          method:"GET",
          headers:{"Authorization":"Bearer "+token,"Accept":"application/json"},
          credentials:"omit",redirect:"error",cache:"no-store",mode:"cors"
        });
      }catch(_){return {status:"SERVER_UNAVAILABLE",rates:[]};}
      if(stale(mine))return {status:"STALE_REQUEST_SUPPRESSED",rates:[]};
      if(resp.status===401||resp.status===403)
        return {status:"SERVER_ADMIN_AUTH_DENIED",rates:[]};
      if(resp.status===409)return {status:"AFTER_EXHIBITION_NOT_VERIFIED",rates:[]};
      if(resp.status!==200)return {status:"SERVER_UNAVAILABLE",rates:[]};
      let out;
      try{out=await resp.json();}
      catch(_){return {status:"UNTRUSTED_RESPONSE",rates:[]};}
      if(stale(mine))return {status:"STALE_REQUEST_SUPPRESSED",rates:[]};
      if(isAdminUi()!==true)return {status:"ADMIN_VIEW_REQUIRED",rates:[]};
      if(out?.ok!==true)return {status:"UNTRUSTED_RESPONSE",rates:[]};
      if(out.status==="MISSING_OR_N_LT_5"&&out.denominator_n===null
          &&out.not_zero_percent===true)
        return {status:"NO_VERIFIED_COHORT_N_GE_5",rates:[],denominatorN:null};
      const n=out.denominator_n,rates=out.third_boat_rates;
      if(out.status!=="RESEARCH_N_GE_5"
        ||out.scope!==selection.scope
        ||out.venue_code!==selection.venue
        ||out.winning_course!==selection.course
        ||out.first_boat!==selection.first||out.second_boat!==selection.second
        ||out.method!==selection.method
        ||out.winner_reg!==(selection.scope==="venue"?"*":selection.playerReg)
        ||!Number.isInteger(n)||n<5
        ||out.approvedForPredictions!==false
        ||out.complete_history_from_2023_approved!==false
        ||!Array.isArray(rates)||rates.length!==4)
        return {status:"UNTRUSTED_RESPONSE",rates:[]};
      const allowed=[1,2,3,4,5,6].filter(b=>b!==selection.first&&b!==selection.second);
      const unique=new Set();
      let total=0;
      for(const x of rates){
        if(!x||!allowed.includes(x.boat)||unique.has(x.boat)
           ||!Number.isInteger(x.n)||x.n<0
           ||!Number.isFinite(x.pct)
           ||Math.abs(x.pct-Math.round(1000*x.n/n)/10)>.011)
          return {status:"UNTRUSTED_RESPONSE",rates:[]};
        unique.add(x.boat);total+=x.n;
      }
      if(total!==n)return {status:"UNTRUSTED_RESPONSE",rates:[]};
      return {status:"RESEARCH_N_GE_5",denominatorN:n,rates:rates.map(x=>({
        boat:x.boat,n:x.n,pct:Math.round(1000*x.n/n)/10
      })),scope:selection.scope,productionApproved:false};
    },
    readyForProduction:false
  };
}

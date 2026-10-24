/**
 * READ-ONLY staging context presence ROUTE CANDIDATE for existing TimeX v3 Worker.
 *
 * Not deployable by itself: the deployed v3 Worker source is not in the
 * connected GitHub repositories. Caller MUST inject existing trusted server
 * admin authentication and the real KV context-read function (including the
 * ACTUAL deployed key format) rather than guessing a KV key/binding.
 *
 * It never returns full boats, coefficients, rates or identity details.
 */
const PATH="/stage-context-presence";
const jsonHeaders=Object.freeze({
  "content-type":"application/json; charset=utf-8",
  "cache-control":"no-store, max-age=0, private",
  "x-content-type-options":"nosniff",
  "pragma":"no-cache",
  "vary":"Authorization, Origin"
});
function respond(status,body){
 return new Response(JSON.stringify(body),{status,headers:jsonHeaders});
}
function parse(request){
 const url=new URL(request.url);
 if(url.pathname!==PATH)throw Error("NOT_FOUND");
 const q=url.searchParams;
 for(const k of q.keys()){
  if(!["date","venue_code","race_no"].includes(k)||q.getAll(k).length!==1)
    throw Error("INVALID_QUERY");
 }
 if([...q.keys()].length!==3)throw Error("INVALID_QUERY");
 const date=q.get("date"),venue=q.get("venue_code"),r=q.get("race_no");
 if(!/^20\d\d-\d\d-\d\d$/.test(date||"")||
    !/^(0[1-9]|1[0-9]|2[0-4])$/.test(venue||"")||
    !/^(?:[1-9]|1[0-2])$/.test(r||""))
   throw Error("INVALID_QUERY");
 const dt=new Date(date+"T00:00:00Z");
 if(!Number.isFinite(dt.getTime())||dt.toISOString().slice(0,10)!==date)
  throw Error("INVALID_QUERY");
 return {date,venue_code:venue,race_no:Number(r)};
}
export function createV3AdminContextReadbackCandidate({
  verifyExistingWorkerAdmin,readExistingRaceContext
}={}){
 if(typeof verifyExistingWorkerAdmin!=="function"||
    typeof readExistingRaceContext!=="function")
   throw Error("EXISTING_AUTH_AND_KV_READERS_REQUIRED");
 return Object.freeze({
  productionApproved:false,
  async handle(request){
   if(request.method!=="GET")return respond(405,{ok:false,error:"METHOD_NOT_ALLOWED"});
   let chosen;
   try{chosen=parse(request);}
   catch(err){
     return err.message==="NOT_FOUND"?
       respond(404,{ok:false,error:"NOT_FOUND"}):
       respond(400,{ok:false,error:"INVALID_QUERY"});
   }
   let actor;
   try{actor=await verifyExistingWorkerAdmin(request);}
   catch(_){return respond(401,{ok:false,error:"LOGIN_REQUIRED"});}
   if(!actor||actor.authenticated!==true||actor.member!==true||
      actor.admin!==true||typeof actor.subject!=="string"||
      !actor.subject.length)
      return respond(403,{ok:false,error:"ADMIN_REQUIRED"});

   let context;
   try{context=await readExistingRaceContext(chosen,actor);}
   catch(_){return respond(503,{ok:false,error:"KV_READBACK_UNAVAILABLE"});}
   if(context===null||context===undefined)
     return respond(200,{
       ok:true,present:false,status:"context_missing",
       v3Verified:false,productionApproved:false
     });
   // A stored object alone is NOT a proven valid model input. This route
   // intentionally does not check or expose cohort-specific contents.
   return respond(200,{
      ok:true,present:true,status:"stored_context_found",
      v3Verified:false,modelVerified:false,productionApproved:false
   });
  }
 });
}

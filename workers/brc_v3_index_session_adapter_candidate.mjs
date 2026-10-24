/**
 * BRC native INDEX -> new TimeX v3 administrator diagnostic adapter.
 *
 * RESEARCH ONLY, NO PRODUCTION DEPLOY: reuse the currently authenticated
 * brcEnsureFreshSession() callback; never parse or persist a JWT yourself.
 * Existing INDEX callers MUST supply the real member/admin/public-view flags.
 * The staging origin is fixed in the underlying diagnostic module.
 *
 * A valid v3 API result is ONLY a server-side four-metric check; even then,
 * this adapter never sets v3Verified=true or changes ordinary members' v2.
 */
import {createAdminV3PredictionDiagnostic} from "./brc_v3_admin_predict_diagnostic_candidate.mjs";

export function createIndexBrcV3AdminDiagnostic({
 ensureFreshSession,readMemberActive,readAdminActive,readPublicView,fetchImpl
}={}){
 if(typeof ensureFreshSession!=="function"||
    typeof readMemberActive!=="function"||
    typeof readAdminActive!=="function"||
    typeof readPublicView!=="function"||
    typeof fetchImpl!=="function")
   throw Error("NATIVE_BRC_V3_SESSION_BINDINGS_REQUIRED");

 const isAdminUi=()=>{
  try{
   return readMemberActive()===true &&
     readAdminActive()===true &&
     readPublicView()===false;
  }catch(_){return false;}
 };
 const getFreshSession=async()=>{
  if(!isAdminUi())return null;
  let session;
  try{session=await ensureFreshSession();}
  catch(_){return null;}
  // A logout or a switch into the public display mode while awaiting a
  // session refresh must revoke the right to send a staging request.
  return isAdminUi()?session:null;
 };
 return createAdminV3PredictionDiagnostic({getFreshSession,isAdminUi,fetchImpl});
}

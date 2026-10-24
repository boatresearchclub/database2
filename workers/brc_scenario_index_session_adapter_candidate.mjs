/**
 * Real BRC INDEX session shape adapter — source-confirmed 2026-10-24.
 * NOT DEPLOYED. This is not a new login system.
 *
 * Existing INDEX uses brcEnsureFreshSession() which verifies JST one-day
 * passes and rotates Supabase refresh tokens before returning access_token.
 * Existing view flags: BRC_MEMBER_ACTIVE, BRC_ADMIN_ACTIVE,
 * body.brc-admin-public-view, brcGetAdminViewMode().
 *
 * Server still MUST reject non-admin user IDs and inactive members.
 */
import {createScenario23ReadClient} from "./brc_scenario_23_admin_client_candidate.mjs";

export const LIVE_BRC_API_ORIGIN="https://brc-api.sk48159212.workers.dev";
export function createIndexBrcScenarioReader({
  ensureFreshSession,readMemberActive,readAdminActive,
  readPublicView,fetchImpl,workerOrigin=LIVE_BRC_API_ORIGIN
}={}){
  if(typeof ensureFreshSession!=="function"
    ||typeof readMemberActive!=="function"
    ||typeof readAdminActive!=="function"
    ||typeof readPublicView!=="function"
    ||typeof fetchImpl!=="function"
    ||workerOrigin!==LIVE_BRC_API_ORIGIN)
    throw Error("NATIVE_BRC_SESSION_BINDINGS_MISSING");
  const isAdminUi=()=>{
    try{
      return readMemberActive()===true&&readAdminActive()===true
        &&readPublicView()===false;
    }catch(_){return false;}
  };
  const getSessionToken=async()=>{
    if(!isAdminUi())return null;
    let session;
    try {session=await ensureFreshSession();}
    catch(_){return null;}
    if(!isAdminUi())return null;
    // NEVER read localStorage independently or use an old cached token:
    // existing brcEnsureFreshSession checks expiry and one-day pass rollover.
    return typeof session?.access_token==="string"?session.access_token:null;
  };
  return createScenario23ReadClient({
    workerOrigin,fetchImpl,isAdminUi,getSessionToken
  });
}

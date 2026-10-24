/**
 * BRC 2着別3着率 — full server-side composition candidate (NEVER DEPLOYED).
 *
 * The real BRC API Worker currently owns its membership-checking logic; this
 * bridge MUST be installed INSIDE that Worker with the existing membership
 * verifier injected. Requiring this callback avoids recursive HTTP calls to
 * the very same brc-api Worker.
 *
 * Only a valid Supabase /auth/v1/user result matching a secret pinned admin
 * UUID AND the existing membership validator returning boolean true can
 * reach the private fixed-key KV matrix. Browser JS flags grant nothing.
 *
 * This file exports a factory, not a Worker fetch handler. There is no
 * wrangler configuration or deployment path.
 */
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
import {createVerifiedBrcActor,APPROVED_BRC_AUTH_ORIGINS} from "./brc_scenario_supabase_member_auth_candidate.mjs";
import {createPrivateScenarioMatrixLoader} from "./brc_scenario_23_private_loader_candidate.mjs";

export const SCENARIO_23_PATH="/api/admin/scenario/2nd3rd";
const PUBLIC_ORIGIN="https://boatresearchclub.github.io";
const FIXED_KV_KEY="BRC_SCENARIO_23_RESEARCH_PRIVATE_V1";

/**
 * Required configuration, all trusted Worker-side (never from an HTTP request):
 *   env.BRC_SCENARIO_PRIVATE_KV        private KV namespace binding
 *   env.BRC_SCENARIO_PRIVATE_SHA256    exact original official-K JSON digest
 *   env.BRC_ADMIN_SUPABASE_USER_ID     approved user UUID, configured privately
 *   env.BRC_SUPABASE_PUBLISHABLE_KEY   public project key, not a service_role key
 *   verifyMembershipInWorker         existing BRC Worker membership validator
 *
 * The caller is responsible for installing this narrowly at SCENARIO_23_PATH,
 * for preserving all other existing API routes, and for current auth secrets.
 */
export function createBrcScenario23IntegratedCandidate({
  env, fetchImpl, verifyMembershipInWorker
}={}){
  if(!env || typeof env!=="object"
      ||typeof fetchImpl!=="function"
      ||typeof verifyMembershipInWorker!=="function"
      ||!env.BRC_SCENARIO_PRIVATE_KV
      ||typeof env.BRC_SCENARIO_PRIVATE_KV.get!=="function"
      ||typeof env.BRC_ADMIN_SUPABASE_USER_ID!=="string"
      ||typeof env.BRC_SUPABASE_PUBLISHABLE_KEY!=="string"
      ||typeof env.BRC_SCENARIO_PRIVATE_SHA256!=="string")
    throw Error("BRC_EXISTING_WORKER_AUTH_OR_PRIVATE_KV_REQUIRED");

  // The auth adapter hard-pins the only approved user provider. The caller
  // cannot replace it with a self-asserted role/identity origin.
  const verifyBearerToken=createVerifiedBrcActor({
    fetchImpl,
    adminUserId:env.BRC_ADMIN_SUPABASE_USER_ID,
    supabasePublishableKey:env.BRC_SUPABASE_PUBLISHABLE_KEY,
    verifyMembershipInWorker,
    supabaseOrigin:APPROVED_BRC_AUTH_ORIGINS.supabase,
    memberApiOrigin:APPROVED_BRC_AUTH_ORIGINS.memberApi
  });
  const loadPrivateMatrix=createPrivateScenarioMatrixLoader({
    binding:env.BRC_SCENARIO_PRIVATE_KV,
    expectedSha256:env.BRC_SCENARIO_PRIVATE_SHA256,
    fixedKey:FIXED_KV_KEY
  });
  const handleScenario23Admin=createScenario23AdminHandler({
    verifyBearerToken,loadPrivateMatrix,allowedOrigin:PUBLIC_ORIGIN
  });
  return Object.freeze({
    path:SCENARIO_23_PATH,
    // Always delegate to the strictly bounded handler. In particular,
    // DO NOT intercept unknown BRC routes with a permissive catch-all.
    handle:handleScenario23Admin,
    productionApproved:false,
    currentlyDeployed:false,
    realWorkerLiveReadbackVerified:false
  });
}

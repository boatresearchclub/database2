/**
 * BRC Supabase + membership Worker adapter (NOT DEPLOYED).
 *
 * Matches source-confirmed 2026-10-24 INDEX login path:
 *   GET SUPABASE_URL/auth/v1/user with bearer + publishable apikey
 *   GET BRC_API_URL/ with same bearer => authorized === true
 *   admin identity is checked against a PRIVATE server-configured user UUID.
 *
 * We deliberately DO NOT trust the user's email/claims, BRC_ADMIN_ACTIVE,
 * user_metadata or any JWT payload decoded on the client.
 */
export const APPROVED_BRC_AUTH_ORIGINS=Object.freeze({
  supabase:"https://wchvzhftwxraqgihochk.supabase.co",
  memberApi:"https://brc-api.sk48159212.workers.dev"
});
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TOKEN=/^[A-Za-z0-9._~+/-]{16,4096}$/;
function validPublicKey(value){
  return typeof value==="string"&&value.length>=20
    &&value.length<=4096&&!/[\s\r\n]/.test(value);
}
function isJson(response){
  return (response?.headers?.get("content-type")||"").toLowerCase()
    .includes("application/json");
}
function safeBody(obj){
  return obj&&typeof obj==="object"&&!Array.isArray(obj);
}
async function getVerifiedJson(fetchImpl,url,headers){
  const response=await fetchImpl(url,{
    method:"GET",headers,redirect:"error",cache:"no-store",
    credentials:"omit"
  });
  if(!response||response.status!==200||!isJson(response))return null;
  const contentLen=response.headers.get("content-length");
  if(contentLen!==null && (!/^\d+$/.test(contentLen)||Number(contentLen)>16384))return null;
  const body=await response.text();
  if(body.length>16384)return null;
  try {const json=JSON.parse(body);return safeBody(json)?json:null;}
  catch(_){return null;}
}
/**
 * Returns an injection callback for existing handler:
 * async verifyBearerToken(token,request) => { authenticated,member,admin,subject }
 *
 * This uses real BRC *protocols*, but requires a server secret admin UUID
 * configured by operator and real deployed Worker binding. No cookie/browser
 * email can influence admin authorization.
 */
export function createVerifiedBrcActor({
  fetchImpl,supabasePublishableKey,adminUserId,
  verifyMembershipInWorker=null,
  supabaseOrigin=APPROVED_BRC_AUTH_ORIGINS.supabase,
  memberApiOrigin=APPROVED_BRC_AUTH_ORIGINS.memberApi
}={}){
  if(typeof fetchImpl!=="function"||!validPublicKey(supabasePublishableKey)
     ||(verifyMembershipInWorker!==null && typeof verifyMembershipInWorker!=="function")
     ||typeof adminUserId!=="string"||!UUID.test(adminUserId)
     ||supabaseOrigin!==APPROVED_BRC_AUTH_ORIGINS.supabase
     ||memberApiOrigin!==APPROVED_BRC_AUTH_ORIGINS.memberApi)
     throw Error("BRC_AUTH_BINDINGS_MISSING_OR_UNAPPROVED");
  const approvedId=adminUserId.toLowerCase();
  return async function verifyBearerToken(token){
    if(typeof token!=="string"||!TOKEN.test(token))return null;
    const supaHeaders={
      "Accept":"application/json",
      "apikey":supabasePublishableKey,
      "Authorization":"Bearer "+token
    };
    let verifiedUser;
    try{
      verifiedUser=await getVerifiedJson(
        fetchImpl,supabaseOrigin+"/auth/v1/user",supaHeaders);
    }catch(_){return null;}
    const userId=verifiedUser?.id;
    if(typeof userId!=="string"||!UUID.test(userId))return null;
    // Reject every user except the server-secret pinned UUID; no email check.
    // Also do not send a non-admin's token to the membership service.
    if(userId.toLowerCase()!==approvedId)return null;
    // When mounted INSIDE the existing brc-api Worker, use its trusted
    // already-present membership checker rather than fetching itself.
    // A second Worker may use the independent BRC_API GET / protocol.
    let verifiedMember=false;
    if(verifyMembershipInWorker!==null){
      try{
        verifiedMember=(await verifyMembershipInWorker({
          verifiedSupabaseUserId:userId.toLowerCase(),token
        }))===true;
      }catch(_){return null;}
    }else{
      let membership;
      try{
        membership=await getVerifiedJson(fetchImpl,memberApiOrigin+"/",{
          "Accept":"application/json",
          "Authorization":"Bearer "+token
        });
      }catch(_){return null;}
      verifiedMember=membership?.authorized===true;
    }
    if(!verifiedMember)return null;
    return {authenticated:true,member:true,admin:true,subject:userId.toLowerCase()};
  };
}

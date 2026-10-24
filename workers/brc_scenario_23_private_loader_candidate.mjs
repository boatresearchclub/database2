/**
 * Protected read adapter for the existing BRC Worker (NOT DEPLOYED).
 * Only server-side private KV binding is accepted. Never accept a public URL,
 * arbitrary key, user-controlled namespace, or client-provided data.
 */
export function createPrivateScenarioMatrixLoader({binding, expectedSha256, fixedKey="BRC_SCENARIO_23_RESEARCH_PRIVATE_V1"}={}) {
  if(!binding||typeof binding.get!=="function"
      ||typeof expectedSha256!=="string"||!/^[a-f0-9]{64}$/.test(expectedSha256)
      ||fixedKey!=="BRC_SCENARIO_23_RESEARCH_PRIVATE_V1")
    throw Error("PRIVATE_STORAGE_CONFIGURATION_REQUIRED");
  return async function loadPrivateMatrix(subject) {
    if(typeof subject!=="string"||!subject||subject.length>256)
      throw Error("VERIFIED_SUBJECT_REQUIRED");
    const text=await binding.get(fixedKey,{type:"text"});
    if(typeof text!=="string")
      throw Error("PRIVATE_SOURCE_MISSING");
    // The K cohort grows as verified dates are added; check UTF-8 bytes
    // rather than JS character count, and keep a bounded 12 MB limit.
    const encoded=new TextEncoder().encode(text);
    if(encoded.byteLength<20||encoded.byteLength>12_000_000)
      throw Error("PRIVATE_SOURCE_MISSING");
    const digest=await crypto.subtle.digest("SHA-256",encoded);
    const actual=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,"0")).join("");
    if(actual!==expectedSha256)throw Error("PRIVATE_SOURCE_DIGEST_MISMATCH");
    let obj;
    try{obj=JSON.parse(text);}catch(_){throw Error("PRIVATE_SOURCE_INVALID_JSON");}
    if(!obj||obj.productionApproved!==false||obj.publicVisible!==false
        ||obj.complete_history_from_2023_approved!==false
        ||obj.source_coverage_kind!=="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"
        ||!Array.isArray(obj.research_rows)||!obj.research_rows.length)
      throw Error("PRIVATE_SOURCE_UNVERIFIED");
    return obj;
  };
}

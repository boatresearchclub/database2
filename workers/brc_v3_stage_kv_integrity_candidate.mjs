/**
 * TimeX v3 stored official roster integrity check.
 *
 * Matches the schema/key contract in the operator-provided historical
 * staging Worker source (BRC_TimeX_v3_Worker_422_Diagnostic_Patch.js).
 * NOT proof this code/version is currently deployed. NO RATES / COEFFICIENTS.
 * Must only be used AFTER existing Worker server-side administrator checks.
 */
export const V3_KV_KEY_PREFIX="brc:race_context:";
const VENUE_NAMES=Object.freeze({
 "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖",
 "07":"蒲郡","08":"常滑","09":"津","10":"三国","11":"びわこ","12":"住之江",
 "13":"尼崎","14":"鳴門","15":"丸亀","16":"児島","17":"宮島","18":"徳山",
 "19":"下関","20":"若松","21":"芦屋","22":"福岡","23":"唐津","24":"大村"
});
const VALID_GRADES=new Set(["一般","G1G2","G3","SG","女子","ヴィーナス","ルーキー","マスターズ"]);
const DATE=/^20\d{2}-\d{2}-\d{2}$/;
function dateValid(v) {
 if(typeof v!=="string"||!DATE.test(v))return false;
 const x=new Date(v+"T00:00:00Z");
 return Number.isFinite(x.getTime())&&x.toISOString().slice(0,10)===v;
}
export function v3ExactKvKey({date,venue_code,race_no}={}){
 if(!dateValid(date)||typeof venue_code!=="string"||
    !/^(0[1-9]|1[0-9]|2[0-4])$/.test(venue_code)||
    venue_code==="03"||!Number.isInteger(race_no)||race_no<1||race_no>12)
   throw Error("INVALID_V3_RACE_KEY");
 return V3_KV_KEY_PREFIX+date+":"+venue_code+":"+String(race_no);
}
/** Only returns a reason code; never exposes racer identity or the JSON. */
export function checkStoredV3RaceContext(source,selection){
 if(source===null||source===undefined)return "context_missing";
 if(!source||typeof source!=="object"||Array.isArray(source))return "context_invalid";
 const {date,venue_code,race_no}=selection;
 if(source.date!==date ||
   String(source.venue_code).padStart(2,"0")!==venue_code||
   Number(source.race_no)!==race_no||
   source.venue!==VENUE_NAMES[venue_code] ||
   typeof source.grade!=="string"||!VALID_GRADES.has(source.grade)||
   !Array.isArray(source.boats)||source.boats.length!==6)return "context_invalid";
 const lanes=new Set(),regs=new Set();
 for(const b of source.boats){
  const c=Number(b?.course),reg=String(b?.reg??"");
  if(!Number.isInteger(c)||c<1||c>6||lanes.has(c)||
     !/^\d{4}$/.test(reg)||regs.has(reg))return "context_invalid";
  lanes.add(c);regs.add(reg);
 }
 if(lanes.size!==6||regs.size!==6)return "context_invalid";
 return "context_valid_candidate";
}
export function createV3TrustedKvContextReader({binding}={}){
 if(!binding||typeof binding.get!=="function")
   throw Error("PRIVATE_V3_KV_BINDING_REQUIRED");
 return async function read(selection){
  const key=v3ExactKvKey(selection);
  const raw=await binding.get(key,"json");
  // Deliberately return only the shape check. More checks still required
  // inside the real predictor (live entry, exhibition and four metrics).
  return Object.freeze({
    present:raw!==null&&raw!==undefined,
    integrity:checkStoredV3RaceContext(raw,selection)
  });
 };
}

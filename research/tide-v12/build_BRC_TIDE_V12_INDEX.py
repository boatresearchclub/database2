#!/usr/bin/env python3
"""Build an isolated BRC INDEX for tide *pre-exhibition prior* research, no prod writes.

Accept the latest complete local index file. Never overwrite input, block ambiguous markers,
fail closed if required BRC prior identity markers are missing.
"""
from pathlib import Path
import hashlib,os,re,sys,tempfile
BASE=Path(__file__).resolve().parent
START=b'<!-- BRC_TIDE_PRE_V12_START_20261023 -->'
END=b'<!-- BRC_TIDE_PRE_V12_END_20261023 -->'
OLD_STARTS=[b'<!-- BRC_TIDE_SHADOW_V11_START_20261023 -->'] + [f'<!-- BRC_TIDE_SHADOW_V{n}_START_20261023 -->'.encode() for n in list(range(3,8))+[10]]+[b'<!-- BRC_TIDE_SHADOW_V3_BEGIN_20261023 -->']
OLD_ENDS=[b'<!-- BRC_TIDE_SHADOW_V11_END_20261023 -->'] + [f'<!-- BRC_TIDE_SHADOW_V{n}_END_20261023 -->'.encode() for n in list(range(3,8))+[10]]+[b'<!-- BRC_TIDE_SHADOW_V3_END_20261023 -->']
MARKERS=[(START,END)]+list(zip(OLD_STARTS,OLD_ENDS))
SCRIPTS=['brc_tide_research_v2.js','brc_tide_admin_bridge_v7.js','brc_tide_autocapture_v10.js','brc_tide_baseline_capture_v11.js','brc_tide_prior_v12.js']
NEEDED=[b'basePctFloat',b'__predictBoatsCurrent',b'RACE_CARDS_TODAY',b'RACE_INFO_TODAY',b'brcV3AdminDiagnostics',b'predictRaceNo',b'brc-admin-public-view']
def patch(src,dst):
 source=Path(src).resolve();target=Path(dst).resolve()
 if not source.exists() or source.suffix.lower() not in ('.html','.htm'):raise ValueError('完全な最新版INDEX.htmlを指定してください')
 if source==target:raise ValueError('元ファイルの上書きは禁止')
 before=source.read_bytes();source_sha=hashlib.sha256(before).hexdigest()
 if len(before)<200_000 or b'\x00' in before:raise ValueError('最新版INDEXに必要な内容が不足')
 missing=[x.decode() for x in NEEDED if x not in before]
 if missing:raise ValueError('BRCソース識別子不足: '+','.join(missing))
 ending=list(re.finditer(rb'</body\s*>',before,re.I))
 if len(ending)!=1:raise ValueError('bodyの終端を一意に判定できません')
 blocks=[]
 for start,end in MARKERS:
  if before.count(start)>1 or before.count(end)>1:raise ValueError('研究ブロックマーカーが重複')
  if bool(start in before)!=bool(end in before):raise ValueError('旧研究ブロックが不完全')
  if start in before:
   a,b=before.index(start),before.index(end)+len(end)
   if a>=b:raise ValueError('研究マーカーの順序が逆')
   blocks.append((a,b))
 if len(blocks)>1:raise ValueError('潮汐研究ブロックが複数：安全停止')
 body=[]
 for name in SCRIPTS:
  code=(BASE/name).read_bytes()
  if b'</script' in code.lower():raise ValueError(name+'にscript終端を検出')
  body.append(b'<script data-brc-tide-pre-v12="'+name.encode()+b'">\n'+code+b'\n</script>')
 insert=START+b'\n'+b'\n'.join(body)+b'\n'+END
 if blocks:
  a,b=blocks[0];after=before[:a]+insert+before[b:]
 else:
  at=ending[0].start();after=before[:at]+b'\n'+insert+b'\n'+before[at:]
 if after.count(START)!=1 or after.count(END)!=1:raise ValueError('研究V12の重複')
 if target.exists() and target.read_bytes()!=after:raise ValueError('出力先が存在し異なる内容です。安全停止')
 target.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.brc_tide_v12_',dir=target.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(after);f.flush();os.fsync(f.fileno())
  os.replace(tmp,target)
 finally:
  if os.path.exists(tmp):os.remove(tmp)
 if source.read_bytes()!=before or target.read_bytes()!=after:raise ValueError('書込検証失敗')
 print('研究版INDEX生成:',target,'\n元INDEX SHA-256:',source_sha,'\n出力SHA-256:',hashlib.sha256(after).hexdigest())
 print('本番反映なし。原本・既存1着率・買い目への変更なし。')
 return target
if __name__=='__main__':
 if len(sys.argv) not in (2,3):print('usage: python build_BRC_TIDE_V12_INDEX.py 最新版index.html [保存先.html]');sys.exit(2)
 try:
  source=Path(sys.argv[1]);target=Path(sys.argv[2]) if len(sys.argv)==3 else source.with_name('index_BRC_TIDE_V12_事前着率研究.html')
  patch(source,target)
 except Exception as e:print('安全停止:',e,file=sys.stderr);sys.exit(1)
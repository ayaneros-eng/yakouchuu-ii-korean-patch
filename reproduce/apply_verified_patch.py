"""Offline, verified v1.3 BPS application; normalizes N64 byte order."""
import argparse,hashlib,json,os,sys,uuid
from pathlib import Path
from bps_codec import apply_patch
def normalize(data):
 if len(data)!=33554432:raise ValueError('32 MiB original Japanese ROM required.')
 header=data[:4]
 if header==bytes.fromhex('80371240'):return data
 if header==bytes.fromhex('37804012'):
  b=bytearray(len(data));b[0::2]=data[1::2];b[1::2]=data[0::2];return bytes(b)
 if header==bytes.fromhex('40123780'):
  b=bytearray(len(data))
  for i in range(4):b[i::4]=data[3-i::4]
  return bytes(b)
 raise ValueError('Invalid N64 ROM header.')
def main():
 p=argparse.ArgumentParser(description='Apply Yakouchuu II Korean patch v1.3 without changing the original.');p.add_argument('original',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 root=Path(__file__).resolve().parent.parent;m=json.loads((root/'release_manifest.json').read_text(encoding='utf-8'));sha=lambda b:hashlib.sha256(b).hexdigest()
 raw=a.original.read_bytes();source=normalize(raw)
 if sha(source)!=m['source_sha256']:raise ValueError('Wrong original ROM SHA-256.')
 patch=(root/m['patch_file']).read_bytes()
 if sha(patch)!=m['patch_sha256']:raise ValueError('Patch integrity error.')
 target=apply_patch(source,patch)
 if sha(target)!=m['target_sha256']:raise ValueError('Rebuilt ROM hash mismatch.')
 output=a.output or a.original.with_name(a.original.stem+' [KO v1.3].z64')
 if output.resolve()==a.original.resolve():raise ValueError('Refusing to overwrite the original.')
 if output.exists():
  if sha(output.read_bytes())==m['target_sha256']:print(output);return
  raise ValueError('Refusing to overwrite an unrelated file.')
 if a.original.read_bytes()!=raw:raise ValueError('Source changed during application.')
 temp=output.with_name(output.name+'.partial-'+uuid.uuid4().hex)
 try:
  with temp.open('xb') as f:f.write(target);f.flush();os.fsync(f.fileno())
  # Windows rename is exclusive; POSIX hard-link creation is also exclusive.
  if os.name=='nt':os.rename(temp,output)
  else:os.link(temp,output)
 finally:temp.unlink(missing_ok=True)
 print(output);print('SHA-256:',m['target_sha256'])
if __name__=='__main__':
 try:main()
 except (ValueError,OSError) as error:sys.exit(str(error))

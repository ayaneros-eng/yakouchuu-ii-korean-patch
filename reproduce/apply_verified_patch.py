import argparse,hashlib,json,sys
from pathlib import Path
from bps_codec import apply_patch
p=argparse.ArgumentParser(description="Apply verified Yakouchuu II KO v1.2 BPS to the original Japanese z64.")
p.add_argument("original",type=Path);p.add_argument("--output",type=Path);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;m=json.loads((r/"release_manifest.json").read_text(encoding="utf-8"))
s=a.original.read_bytes()
if hashlib.sha256(s).hexdigest()!=m["source_sha256"]:sys.exit("Wrong source ROM SHA-256. Use the original Japanese .z64.")
b=(r/m["patch_file"]).read_bytes()
if hashlib.sha256(b).hexdigest()!=m["patch_sha256"]:sys.exit("Patch integrity error.")
t=apply_patch(s,b)
if hashlib.sha256(t).hexdigest()!=m["target_sha256"]:sys.exit("Rebuilt ROM hash mismatch.")
o=a.output or r/m["target_file"]
if o.resolve()==a.original.resolve():sys.exit("Refusing to overwrite the original ROM.")
if o.exists() and hashlib.sha256(o.read_bytes()).hexdigest()!=m["target_sha256"]:sys.exit("Refusing to overwrite an unrelated file.")
o.write_bytes(t);print(o);print("SHA-256:",m["target_sha256"])

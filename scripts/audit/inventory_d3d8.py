#!/usr/bin/env python3
"""Repository-wide D3D8 call-site inventory. Standard library only."""
import argparse
import collections
import csv
import json
import pathlib
import re

EXTS={".c",".cc",".cpp",".cxx",".h",".hpp",".hxx",".mm",".m",".inl",".inc"}
# Direct COM dispatch, wrapper macros, and Direct3D factory / exported APIs.
PATTERNS=[
 ("direct-method", re.compile(r"(?:->|\.)\s*(?P<method>(?:Create|Get|Set|Draw|Begin|End|Present|Reset|Test|Clear|Update|Copy|Stretch|Lock|Unlock|Release|AddRef|QueryInterface|Validate|Apply|Capture|Delete|LightEnable|Multiply|Process|Evict|ResourceManager|Check|Enum|Register|GetAvailable|GetAdapter|GetDevice)[A-Za-z0-9_]*)\s*\(")),
 ("d3d-factory", re.compile(r"\b(?P<method>Direct3DCreate8|D3DX[A-Za-z0-9_]+)\s*\(")),
 ("dx8-macro", re.compile(r"\b(?P<method>DX8CALL|DX8CALL_HR|DX8_RECORD_DX8_CALLS)\s*\(")),
]
# Explicit D3D references identify relevant source units; we also inventory
# indirect calls in every file, marked as candidates for manual classification.
D3D_MARKER=re.compile(r"\b(?:IDirect3D\w*|D3D[A-Z0-9_]+|DX8Wrapper|DX8CALL|Direct3DCreate8|D3DX\w+)\b")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",default=".")
 p.add_argument("--out",default="build/d3d8-inventory")
 p.add_argument("--include-vendored",action="store_true")
 args=p.parse_args()
 root=pathlib.Path(args.root).resolve()
 out=pathlib.Path(args.out).resolve()
 out.mkdir(parents=True,exist_ok=True)
 excluded={".git","build",".venv","node_modules"}
 if not args.include_vendored: excluded|={"references","third_party","external","vendor","vcpkg"}
 rows=[]; relevant_files=0; scanned=0; errors=[]
 for f in root.rglob("*"):
  if not f.is_file() or f.suffix.lower() not in EXTS or any(x in excluded for x in f.relative_to(root).parts): continue
  scanned+=1
  try: data=f.read_text(encoding="utf-8",errors="replace")
  except OSError as e: errors.append(f"{f}: {e}");continue
  relevant=bool(D3D_MARKER.search(data))
  if relevant: relevant_files+=1
  for n,line in enumerate(data.splitlines(),1):
   for kind,pat in PATTERNS:
    for m in pat.finditer(line):
     # Direct-method matches are intentionally candidate matches: other APIs
     # also have Set*/Get* methods. Preserve them to avoid silent omissions.
     rows.append(dict(file=str(f.relative_to(root)),line=n,kind=kind,
                      method=m.group("method"),d3d_context=relevant,
                      snippet=line.strip()[:300]))
 rows.sort(key=lambda x:(x["file"],x["line"],x["method"]))
 with (out/"calls.csv").open("w",newline="",encoding="utf-8") as fh:
  w=csv.DictWriter(fh,fieldnames=["file","line","kind","method","d3d_context","snippet"]);w.writeheader();w.writerows(rows)
 counts=collections.Counter(x["method"] for x in rows if x["d3d_context"])
 report={"scanned_source_files":scanned,"d3d_context_files":relevant_files,
         "candidate_call_sites":len(rows),"d3d_context_candidates":sum(x["d3d_context"] for x in rows),
         "method_counts":dict(counts.most_common()),"read_errors":errors,
         "limitations":["Method name matching produces false positives.",
          "Macro expansion, indirect function pointers and generated code are not resolved.",
          "Excluded vendored/submodule directories unless --include-vendored.",
          "This is a candidate inventory, not proof of complete D3D8 ABI coverage."]}
 (out/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
 with (out/"README.md").open("w") as fh:
  fh.write("# Direct3D 8 call-site inventory\n\n")
  for key in ["scanned_source_files","d3d_context_files","candidate_call_sites","d3d_context_candidates"]:
   fh.write(f"- {key}: {report[key]}\n")
  fh.write("\n## Method candidates in D3D-context files\n\n| Method | Occurrences |\n|---|---:|\n")
  for method,count in counts.most_common(): fh.write(f"| `{method}` | {count} |\n")
  fh.write("\n## Limitations\n\n")
  for item in report["limitations"]: fh.write(f"- {item}\n")
 print(json.dumps({k:report[k] for k in ["scanned_source_files","d3d_context_files","candidate_call_sites"]}))
if __name__=="__main__":main()

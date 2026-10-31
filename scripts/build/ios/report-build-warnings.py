#!/usr/bin/env python3
"""Report compiler/configuration/linker warnings without filtering the original logs."""
# GeneralsX @build Codex 31/10/2026 Publish an explicit warning count and completion state for native-build verification.
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re

ANSI=re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
COMPILER=re.compile(r'^(?:.+?:\d+(?::\d+)?: |(?:clang\+\+|clang|gcc|g\+\+|cc|c\+\+): )warning: (.*)')
# GeneralsX @build Codex 31/10/2026 Keep real errors ahead of successful-build tails and below GitHub's per-annotation truncation.
BUILD_ERROR=re.compile(r'^(?:.+?:\d+(?::\d+)?: (?:fatal )?error:|CMake Error|(?:clang\+\+|clang|ld|ninja): (?:fatal )?error:|error:)',re.I)


def summarize(paths,outcome):
    groups=Counter();samples={};missing=[];tails=[];failures=[];seen_errors=set()
    for name in paths:
        path=Path(name)
        if not path.is_file():missing.append(str(path));continue
        content=path.read_text(errors='replace')
        if content.strip():tails.append(str(path)+':\n'+ANSI.sub('',content[-6000:]))
        lines=[re.sub(r'^\d{4}-\d\d-\d\dT\S+\s+','',ANSI.sub('',raw)).removeprefix('##[warning]') for raw in content.splitlines()]
        for index,line in enumerate(lines):
            if BUILD_ERROR.match(line) and line not in seen_errors and len(failures)<6:
                seen_errors.add(line)
                failures.append((str(path)+':\n'+'\n'.join(lines[index:index+8]))[:1800])
            matched=COMPILER.match(line)
            if matched:
                flag=re.search(r'\[(-W[^\]]+)\]',matched[1]);group=flag[1] if flag else 'compiler'
            elif re.match(r'^CMake (?:Deprecation )?Warning',line):group='cmake'
            elif line.startswith('ld: warning:'):group='linker'
            elif re.match(r'^(?:[^\s:]+: warning:|[Ww][Aa][Rr][Nn][Ii][Nn][Gg]:)',line):group='tool'
            else:continue
            groups[group]+=1
            examples=samples.setdefault(group,[])
            if line not in examples and len(examples)<4:examples.append(line)
    complete=outcome=='success' and not missing
    return dict(complete=complete,outcome=outcome or 'unknown',
                observed_warnings=sum(groups.values()),groups=dict(sorted(groups.items())),samples=samples,missing_logs=missing,
                incomplete_build_output='\n'.join(tails)[-10000:] if not complete else '',failure_samples=failures if not complete else [])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--outcome',default='unknown');parser.add_argument('--output',required=True)
    parser.add_argument('logs',nargs='+');args=parser.parse_args();result=summarize(args.logs,args.outcome)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    label='complete' if result['complete'] else 'incomplete'
    message=f"native_build={label} observed_warnings={result['observed_warnings']} groups={json.dumps(result['groups'],sort_keys=True)}"
    print('::notice title=iOS build warning summary::'+message.replace('%','%25').replace('\r','%0D').replace('\n','%0A'))
    # GeneralsX @build Codex 31/10/2026 Make real native failures and residual warnings reviewable without authenticated log downloads.
    for group,examples in result['samples'].items():
        detail='\n'.join(examples)[:3000]
        print('::notice title=iOS warning samples ('+group+')::'+detail.replace('%','%25').replace('\r','%0D').replace('\n','%0A'))
    for detail in result['failure_samples']:
        print('::notice title=iOS build error detail::'+detail.replace('%','%25').replace('\r','%0D').replace('\n','%0A'))
    if result['incomplete_build_output'] and not result['failure_samples']:
        detail=result['incomplete_build_output'][-2500:]
        print('::notice title=iOS incomplete build output::'+detail.replace('%','%25').replace('\r','%0D').replace('\n','%0A'))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as output:
            output.write(f"### Native build diagnostics\n\nBuild: **{label}**. Observed warnings: **{result['observed_warnings']}**.\n\n")
            if not result['complete']:output.write('This is not a verified warning-free build. Check the build outcome and missing logs.\n\n')
            for group,count in result['groups'].items():output.write(f'- `{group}`: {count}\n')


if __name__=='__main__':main()

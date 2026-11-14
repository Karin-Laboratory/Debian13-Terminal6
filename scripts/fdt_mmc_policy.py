#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored FDT metadata validation/policy tool, 2026-11-14.
"""Create an OWNER-PRIVATE DTB candidate; never deploys or accesses hardware.

Only four explicit MMC policy changes are supported. Require an exact input
SHA256. Verify all other FDT properties and the reservation map unchanged.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess

NODE='/mmc@11230000'


def properties(blob):
    if len(blob)<40:raise ValueError('short FDT')
    magic,total,off,strings,reserve,version,last,boot,szstr,szstruct=struct.unpack('>10I',blob[:40])
    if magic!=0xd00dfeed or total>len(blob) or version<17:raise ValueError('invalid/unsupported FDT')
    if off+szstruct>total or strings+szstr>total:raise ValueError('FDT bounds')
    result={};stack=[];pos=off;end=off+szstruct
    while pos<end:
        token=struct.unpack_from('>I',blob,pos)[0];pos+=4
        if token==1:
            stop=blob.index(b'\0',pos,end);stack.append(blob[pos:stop].decode('ascii'));pos=(stop+4)&~3
        elif token==2:
            if not stack:raise ValueError('unbalanced node')
            stack.pop()
        elif token==3:
            length,nameoff=struct.unpack_from('>II',blob,pos);pos+=8
            if pos+length>end or nameoff>=szstr:raise ValueError('property bounds')
            nameend=blob.index(b'\0',strings+nameoff,strings+szstr)
            name=blob[strings+nameoff:nameend].decode('ascii')
            key=('/'+'/'.join(stack[1:]),name)
            if key in result:raise ValueError('duplicate property')
            result[key]=blob[pos:pos+length];pos=(pos+length+3)&~3
        elif token==4:pass
        elif token==9:break
        else:raise ValueError('invalid structure token')
    # Reservation entries are binary addresses/lengths and never printed.
    p=reserve
    while p+16<=total:
        entry=blob[p:p+16];p+=16
        if entry==bytes(16):return result,blob[reserve:p]
    raise ValueError('unterminated reservation map')


def make_candidate(source,destination,expected_sha,policy):
    original=Path(source).read_bytes()
    if hashlib.sha256(original).hexdigest()!=expected_sha:raise ValueError('input SHA mismatch')
    before,reserve=properties(original)
    if before.get((NODE,'compatible'),b'').split(b'\0')[0]!=b'mediatek,mt6990-mmc':
        raise ValueError('unexpected controller compatible')
    if before.get((NODE,'bus-width'))!=struct.pack('>I',8):raise ValueError('expected 8-bit eMMC')
    if Path(source).resolve()==Path(destination).resolve() or Path(destination).exists():
        raise ValueError('output must be a new private file')
    expected=dict(before);operations=[]
    if policy=='no-cqe':
        if (NODE,'supports-cqe') not in expected:raise ValueError('CQE already absent')
        del expected[(NODE,'supports-cqe')];operations=[['-d',str(destination),NODE,'supports-cqe']]
    elif policy=='max100':
        expected[(NODE,'max-frequency')]=struct.pack('>I',100000000)
        operations=[['-t','i',str(destination),NODE,'max-frequency','100000000']]
    elif policy in ['no-hs400','no-hs200-hs400']:
        names=['mmc-hs400-1_8v','mmc-hs400-1_2v','mmc-hs400-enhanced-strobe']
        if policy=='no-hs200-hs400':names+=['mmc-hs200-1_8v','mmc-hs200-1_2v']
        for name in names:
            if (NODE,name) in expected:
                del expected[(NODE,name)];operations.append(['-d',str(destination),NODE,name])
        if not operations:raise ValueError('no matching timing capabilities')
    else:raise ValueError('unknown policy')
    shutil.copyfile(source,destination)
    try:
        for args in operations:subprocess.run(['fdtput']+args,check=True,capture_output=True)
        after,newreserve=properties(Path(destination).read_bytes())
        if after!=expected or newreserve!=reserve:raise ValueError('unexpected semantic change')
    except Exception:
        Path(destination).unlink(missing_ok=True);raise
    return {'policy':policy,'only_expected_properties_changed':True,
            'input_sha256':expected_sha,'output_sha256':hashlib.sha256(Path(destination).read_bytes()).hexdigest(),
            'hardware_test':'NOT_RUN','distribution':'OWNER_PRIVATE_ONLY'}


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input');p.add_argument('output');p.add_argument('--sha256',required=True)
    p.add_argument('--policy',required=True,choices=['no-cqe','max100','no-hs400','no-hs200-hs400'])
    a=p.parse_args();print(json.dumps(make_candidate(a.input,a.output,a.sha256,a.policy)))

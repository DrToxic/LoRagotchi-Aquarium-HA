#!/usr/bin/env python3
"""Apply the version-locked RX overlay to a clean MeshCoMod checkout; never flash."""
import argparse
from pathlib import Path
import subprocess

BASE='8aba438f452dfca5680d1c96b3e643e54f98cef3'
RX='49d3900595b85210fc19d8fbe51a829cf68cd726'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('checkout',type=Path,help='Existing clean checkout at the pinned MeshCoMod commit')
args=parser.parse_args();root=args.checkout.resolve()
def git(*arguments,**kw):return subprocess.run(['git','-C',str(root),*arguments],check=True,**kw)
head=git('rev-parse','HEAD',capture_output=True,text=True).stdout.strip()
if head!=BASE:raise SystemExit(f'Wrong baseline: require {BASE}, got {head}')
if git('status','--porcelain',capture_output=True,text=True).stdout.strip():raise SystemExit('Checkout is not clean; use an isolated checkout.')
patch=Path(__file__).with_name('overlay.patch').resolve()
git('apply','--check',str(patch));git('apply',str(patch))
print(f'Applied RX {RX} to MeshCoMod {BASE}; target heltec_v4_companion_radio_usb_tcp_lrx. No build or flash performed.')

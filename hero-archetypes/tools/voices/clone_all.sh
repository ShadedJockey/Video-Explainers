#!/usr/bin/env bash
# usage: clone_all.sh RECORDING NAME   → out/clone_<engine>_<NAME>.wav + similarity report
set -u
S=$(cd "$(dirname "$0")" && pwd); cd "$S"
REC=$1; NAME=${2:-me}; D=$S/ref_$NAME; mkdir -p "$D"
export HF_HUB_DISABLE_XET=1
asr/bin/python prep_ref.py "$REC" "$D" 2>&1 | grep -vi warn | tail -2
qwen/bin/python clone_qwen.py sample.txt "$D" out/clone_qwen_$NAME.wav 2>&1 | grep -E "clone|Error" | tail -1
cbox/bin/python clone_cbox.py sample.txt "$D" out/clone_chatterbox_$NAME.wav 2>&1 | grep -E "clone|Error" | tail -1
pocket/bin/python clone_pocket.py sample.txt "$D" out/clone_pocket_$NAME.wav 2>&1 | grep -E "clone|Error|403|401|Gated" | tail -1
asr/bin/python spksim.py "$D/ref.wav" out/clone_*_$NAME.wav 2>&1 | grep -E "^[0-9.-]+ "

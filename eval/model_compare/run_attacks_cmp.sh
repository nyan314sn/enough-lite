#!/bin/bash
# usage: run_attacks_cmp.sh anthropic 8041
cd "."
/python safety_tests/run_attacks.py http://127.0.0.1:$2 --header X-Enough-Test:1 --max-repeat 10 --out mc_$1_ > eval/model_compare/attacks_$1.log 2>&1
mv safety_tests/mc_$1_results.jsonl safety_tests/mc_$1_summary.md eval/model_compare/raw/ 

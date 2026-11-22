# Loop round 3, audit C (simulated users)
Own instance :8074 (stopped). 48 personas, Haiku. Data in simusers/round3/ (analysis.txt, skips.txt, runs/, judged/). Wrapper: simusers/run_round3.py.
Reached 48/48; accuracy 95.1% (40: 95.8%, hard 8: 91.5%); P0 dead ends 3 (2 are app connection timeouts under load, p14 source quote); dead ends 18; ignored corrections 1 (p08).
What If hit 67/92; source quotes 12; changes applied 0 (no change proposals occurred, so confirmation untested).
Attacks: 74/74 (OS-05 timed out once under load, passed on an idle rerun); round 2 kit 101/107, same 6 known non-defects.
Skip check ("not sure/skip/I don't know"): about 12 true skips; 5 proposed and named a number, 2 weak (split kept, not restated), 5 missed (rate or balance left empty): h07 t7 mortgage balance; p11 t4, h02 t5, p14 t4, p16 t5 interest rate.

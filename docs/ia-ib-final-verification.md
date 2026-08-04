# IA/IB Final Verification

| Check | Status | Exit Code | Seconds |
|---|---:|---:|---:|
| data_integrity | pass | N/A | 0.02 |
| original_100 | pass | 0 | 5.58 |
| enhanced_100 | pass | 0 | 5.42 |
| enhanced_3600 | not_run | N/A | 0.00 |
| variant_contracts | pass | 0 | 2.89 |
| runtime_contracts | pass | 0 | 2.27 |
| api_contracts | pass | 0 | 4.02 |
| ca_mp_smoke | pass | N/A | 1.85 |
| exact_metrics | pass | N/A | 1.74 |
| figure_contracts | pass | N/A | 7.28 |
| matrix | pass | N/A | 0.45 |
| stress_runs | pass | N/A | 8.84 |
| automated_regression | pass | 0 | 11.77 |
| docker | pass | 0 | 65.12 |

## Docker

live validation: pass

## Repository provenance

- commit: `572a017f2398655edf6a4c28aebd84a2f9a9dbda`
- dirty: `true`
- diff SHA-256: `635afed1124ec5d97e81d7072eebe284fda772e800eb1d77a42a2a7fc1922573`

## Evidence axes

- repository implementation: pass
- automated verification: pass
- local SUMO verification: not_run
- Docker live verification: pass
- second-machine reproduction: not_run

## data_integrity

Command: `static data inventory`
Exit code: `N/A`
Mode: `in_process`

## original_100

Command: `sumo -c <D:\Desktop\挑战杯项目\新建文件夹\challenge-cup\data\intersection_data/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\evidence\docker\ia-ib-quick/original_100/N/tripinfo.xml> --summary-output <output\evidence\docker\ia-ib-quick/original_100/N/stats.xml> --fcd-output <output\evidence\docker\ia-ib-quick/original_100/N/traj.xml>`
Exit code: `0`
Mode: `executed`
- evidence: `output\evidence\docker\ia-ib-quick\original_100`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_100

Command: `sumo -c <D:\Desktop\挑战杯项目\新建文件夹\challenge-cup\engine\configs/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\evidence\docker\ia-ib-quick/enhanced_100/N/tripinfo.xml> --summary-output <output\evidence\docker\ia-ib-quick/enhanced_100/N/stats.xml> --fcd-output <output\evidence\docker\ia-ib-quick/enhanced_100/N/traj.xml>`
Exit code: `0`
Mode: `executed`
- evidence: `output\evidence\docker\ia-ib-quick\enhanced_100`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_3600

Command: `not run`
Exit code: `N/A`
Mode: `not_run`
- warning: quick mode

## variant_contracts

Command: `D:\anaconda3\python.exe -m pytest tests/test_variants.py tests/test_scenes.py -q -p no:cacheprovider`
Exit code: `0`
Mode: `executed`

## runtime_contracts

Command: `D:\anaconda3\python.exe -m pytest tests/test_run_service.py tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py -q -p no:cacheprovider`
Exit code: `0`
Mode: `executed`

## api_contracts

Command: `D:\anaconda3\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider`
Exit code: `0`
Mode: `executed`

## ca_mp_smoke

Command: `RunService(RunRequest('1','ca_maxpressure',steps=100,flow=1.5))`
Exit code: `N/A`
Mode: `in_process`

## exact_metrics

Command: `fixed_time 100-step run; parse tripinfo.xml -> summary.json`
Exit code: `N/A`
Mode: `in_process`

## figure_contracts

Command: `pytest tests/test_visualization.py; python -m visualization.report`
Exit code: `N/A`
Mode: `in_process`

## matrix

Command: `python scripts/run_pdf_matrix.py --quick --output-root output\evidence\docker\ia-ib-quick\matrix`
Exit code: `N/A`
Mode: `audited`
- evidence: `output\evidence\docker\ia-ib-quick\matrix\matrix.csv`
- evidence: `output\evidence\docker\ia-ib-quick\matrix\matrix_state.json`

## stress_runs

Command: `python scripts/stress_memory.py --intersections 1 11 16`
Exit code: `N/A`
Mode: `in_process`

## automated_regression

Command: `D:\anaconda3\python.exe -m pytest tests -q -p no:cacheprovider [exit=0]; D:\anaconda3\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization [exit=0]; D:\anaconda3\python.exe -c import algorithms, api, cloud, core, engine, experiments, ml, scenes, scripts, visualization [exit=0]; D:\anaconda3\python.exe -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100 [exit=0]; git diff --check [exit=0]`
Exit code: `0`
Mode: `executed`
- evidence: `output\evidence\docker\ia-ib-quick\pycache`

## docker

Command: `D:\Docker\resources\bin\docker.EXE build -t ca-mp:ia-ib -f docker/Dockerfile .; D:\Docker\resources\bin\docker.EXE run --rm -v D:\Desktop\挑战杯项目\新建文件夹\challenge-cup\output:/app/output ca-mp:ia-ib; D:\Docker\resources\bin\docker.EXE save ca-mp:ia-ib -o output\evidence\docker\ia-ib-quick\ca-mp-ia-ib.tar; D:\Docker\resources\bin\docker.EXE load -i output\evidence\docker\ia-ib-quick\ca-mp-ia-ib.tar; D:\Docker\resources\bin\docker.EXE run --rm ca-mp:ia-ib`
Exit code: `0`
Mode: `executed`
- evidence: `output\evidence\docker\ia-ib-quick\ca-mp-ia-ib.tar`

# IA/IB Final Verification

| Check | Status | Exit Code | Seconds |
|---|---:|---:|---:|
| data_integrity | pass | 0 | 0.01 |
| original_100 | pass | 0 | 4.30 |
| enhanced_100 | pass | 0 | 4.33 |
| enhanced_3600 | pass | 0 | 59.91 |
| variant_contracts | pass | 0 | 0.52 |
| runtime_contracts | pass | 0 | 0.67 |
| api_contracts | pass | 0 | 1.58 |
| ca_mp_smoke | pass | 0 | 1.48 |
| exact_metrics | pass | 0 | 1.64 |
| figure_contracts | pass | 0 | 3.72 |
| matrix | pass | 0 | 0.08 |
| stress_runs | pass | 0 | 273.37 |
| docker | not_run | N/A | 0.28 |
| automated_regression | pass | 0 | 5.60 |

## Docker

live validation: not run: Docker unavailable

## data_integrity

Command: `static data inventory`
Exit code: `0`

## original_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\data\intersection_data/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/original_100/N/tripinfo.xml> --summary-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/original_100/N/stats.xml> --fcd-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/original_100/N/traj.xml>`
Exit code: `0`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\engine\configs/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_100/N/tripinfo.xml> --summary-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_100/N/stats.xml> --fcd-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_100/N/traj.xml>`
Exit code: `0`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_3600

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\engine\configs/demo_N.sumocfg> --no-step-log true -e 3600 --tripinfo-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_3600/N/tripinfo.xml> --summary-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_3600/N/stats.xml> --fcd-output <C:\Users\peng\Desktop\project\ChallengeCup\output\verification\final-sharded/enhanced_3600/N/traj.xml>`
Exit code: `0`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 11: Warning: Vehicle 'S_car.19' performs emergency braking on lane '-E2_0' with decel=9.00, wished=4.50, severity=1.00, time=130.90.
- warning: intersection 11: Warning: Vehicle 'E_car.120' performs emergency braking on lane '-E1_0' with decel=9.00, wished=4.50, severity=1.00, time=606.60.
- warning: intersection 11: Warning: Teleporting vehicle 'E_car.120'; collision with vehicle 'S_car.85', lane='E3_0', gap=-6.57, time=606.60, stage=move.
- warning: intersection 11: Warning: Vehicle 'E_car.120' teleports beyond arrival edge 'E3', time=606.60.
- warning: intersection 11: Warning: Vehicle 'N_car.238' performs emergency braking on lane '-E3_0' with decel=9.00, wished=4.50, severity=1.00, time=1630.50.
- warning: intersection 11: Warning: Vehicle 'E_car.701' performs emergency braking on lane '-E1_0' with decel=9.00, wished=4.50, severity=1.00, time=3458.30.
- warning: intersection 11: Warning: Vehicle 'S_car.534' performs emergency braking on lane '-E2_0' with decel=9.00, wished=4.50, severity=1.00, time=3459.10.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Vehicle 'SN_car.55' performs emergency braking on lane '-E2.41_0' with decel=9.00, wished=4.50, severity=1.00, time=320.90.
- warning: intersection 18: Warning: Vehicle 'NS_car.171' performs emergency braking on lane '-E3_0' with decel=9.00, wished=4.50, severity=1.00, time=1056.50.
- warning: intersection 18: Warning: Vehicle 'EW_car.285' performs emergency braking on lane '-E1.42_0' with decel=9.00, wished=4.50, severity=1.00, time=1240.90.
- warning: intersection 18: Warning: Vehicle 'SN_car.433' performs emergency braking on lane '-E2.41_0' with decel=9.00, wished=4.50, severity=1.00, time=2491.20.
- warning: intersection 18: Warning: Vehicle 'WE_car.498' performs emergency braking on lane 'E0.40_0' with decel=9.00, wished=4.50, severity=1.00, time=2600.90.
- warning: intersection 18: Warning: Vehicle 'NS_car.471' performs emergency braking on lane '-E3_0' with decel=9.00, wished=4.50, severity=1.00, time=2902.40.
- warning: intersection 18: Warning: Vehicle 'EW_car.730' performs emergency braking on lane '-E1.42_0' with decel=9.00, wished=4.50, severity=1.00, time=3160.90.
- warning: intersection 18: Warning: Vehicle 'EW_car.823' performs emergency braking on lane ':J1_0_0' with decel=9.00, wished=4.50, severity=1.00, time=3566.10.

## variant_contracts

Command: `C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m pytest tests/test_variants.py tests/test_scenes.py -q -p no:cacheprovider`
Exit code: `0`

## runtime_contracts

Command: `C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m pytest tests/test_run_service.py tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py -q -p no:cacheprovider`
Exit code: `0`

## api_contracts

Command: `C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider`
Exit code: `0`

## ca_mp_smoke

Command: `RunService(RunRequest('1','ca_maxpressure',steps=100,flow=1.5))`
Exit code: `0`

## exact_metrics

Command: `fixed_time 100-step run; parse tripinfo.xml -> summary.json`
Exit code: `0`

## figure_contracts

Command: `pytest tests/test_visualization.py; python -m visualization.report`
Exit code: `0`

## matrix

Command: `20 isolated local processes; each process uses RunService(max_workers=1); 360 x 36000-step audit`
Exit code: `0`

## stress_runs

Command: `python scripts/stress_memory.py --intersections 1 11 16`
Exit code: `0`

## docker

Command: `C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m pytest tests/test_docker_static.py -q -p no:cacheprovider`
Exit code: `N/A`
- warning: Docker unavailable; live build/run/save/load not run

## automated_regression

Command: `C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider [exit=0]; C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization [exit=0]; C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -c import algorithms, api, cloud, core, engine, experiments, ml, scenes, scripts, visualization [exit=0]; C:\Users\peng\Desktop\project\ChallengeCup\.venv\Scripts\python.exe -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100 [exit=0]; git diff --check [exit=0]`
Exit code: `0`

## Evidence axes

- repository implementation: pass (`main` commit `745dc4b`)
- automated verification: see `automated_regression`
- local SUMO verification: see original/enhanced/matrix/stress checks
- Docker live verification: not run: Docker unavailable
- second-machine reproduction: not_run (no independent evidence supplied)
- report/PPT/video: independent deliverables; not claimed by IA/IB verification

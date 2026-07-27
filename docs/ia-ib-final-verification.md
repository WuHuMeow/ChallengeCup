# IA/IB Final Verification

| Check | Status | Exit Code | Seconds |
|---|---:|---:|---:|
| data_integrity | pass | N/A | 0.02 |
| original_100 | pass | 0 | 4.46 |
| enhanced_100 | pass | 0 | 4.41 |
| enhanced_3600 | pass | 0 | 65.97 |
| variant_contracts | pass | 0 | 1.26 |
| runtime_contracts | pass | 0 | 1.33 |
| api_contracts | pass | 0 | 2.44 |
| ca_mp_smoke | pass | N/A | 1.67 |
| exact_metrics | pass | N/A | 1.66 |
| figure_contracts | pass | N/A | 5.03 |
| matrix | pass | N/A | 30.41 |
| stress_runs | pass | N/A | 299.72 |
| automated_regression | pass | 0 | 7.60 |
| docker | not_run | N/A | 0.38 |

## Docker

live validation: not run: Docker unavailable

## Repository provenance

- commit: `f31f04e5fadd26196ef8ced6bc4bd1bff78c3253`
- dirty: `false`
- diff SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

## Evidence axes

- repository implementation: pass
- automated verification: pass
- local SUMO verification: pass
- Docker live verification: not_run
- second-machine reproduction: not_run

## data_integrity

Command: `static data inventory`
Exit code: `N/A`
Mode: `in_process`

## original_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\data\intersection_data/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\verification\final-sharded/original_100/N/tripinfo.xml> --summary-output <output\verification\final-sharded/original_100/N/stats.xml> --fcd-output <output\verification\final-sharded/original_100/N/traj.xml>`
Exit code: `0`
Mode: `executed`
- evidence: `output\verification\final-sharded\original_100`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\engine\configs/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\verification\final-sharded/enhanced_100/N/tripinfo.xml> --summary-output <output\verification\final-sharded/enhanced_100/N/stats.xml> --fcd-output <output\verification\final-sharded/enhanced_100/N/traj.xml>`
Exit code: `0`
Mode: `executed`
- evidence: `output\verification\final-sharded\enhanced_100`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_3600

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\engine\configs/demo_N.sumocfg> --no-step-log true -e 3600 --tripinfo-output <output\verification\final-sharded/enhanced_3600/N/tripinfo.xml> --summary-output <output\verification\final-sharded/enhanced_3600/N/stats.xml> --fcd-output <output\verification\final-sharded/enhanced_3600/N/traj.xml>`
Exit code: `0`
Mode: `executed`
- evidence: `output\verification\final-sharded\enhanced_3600`
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

Command: `C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_variants.py tests/test_scenes.py -q -p no:cacheprovider`
Exit code: `0`
Mode: `executed`

## runtime_contracts

Command: `C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_run_service.py tests/test_events.py tests/test_resilience.py tests/test_runner_channel.py -q -p no:cacheprovider`
Exit code: `0`
Mode: `executed`

## api_contracts

Command: `C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_api.py tests/test_api_contract.py -q -p no:cacheprovider`
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

Command: `in-process audit of output\verification\final-sharded\matrix.csv`
Exit code: `N/A`
Mode: `audited`
- evidence: `output\verification\final-sharded\matrix.csv`

## stress_runs

Command: `python scripts/stress_memory.py --intersections 1 11 16`
Exit code: `N/A`
Mode: `in_process`

## automated_regression

Command: `C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests -q -p no:cacheprovider [exit=0]; C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization [exit=0]; C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c import algorithms, api, cloud, core, engine, experiments, ml, scenes, scripts, visualization [exit=0]; C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m flake8 algorithms api cloud core engine experiments scenes scripts visualization --max-line-length=100 [exit=0]; git diff --check [exit=0]`
Exit code: `0`
Mode: `executed`
- evidence: `output\verification\final-sharded\pycache`

## docker

Command: `C:\Users\peng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_docker_static.py -q -p no:cacheprovider`
Exit code: `N/A`
Mode: `not_run`
- warning: Docker unavailable; live build/run/save/load not run

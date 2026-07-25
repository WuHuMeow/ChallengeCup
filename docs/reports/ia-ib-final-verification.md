# IA/IB Final Verification

| Check | Status | Seconds |
|---|---:|---:|
| data_integrity | pass | 0.01 |
| original_100 | pass | 4.30 |
| enhanced_100 | pass | 4.52 |
| enhanced_3600 | pass | 70.82 |
| baseline_runs | pass | 70.77 |
| stress_runs | pass | 174.81 |
| docker_static | pass | 0.43 |

## Docker

live validation: not run: Docker unavailable

## Cross-role blockers

- AB blocker: CA-MP remains an AB blocker; no correctness claim made.

## data_integrity

Command: `static data inventory`

## original_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\.worktrees\ia-ib-completion\data\intersection_data/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\verification\final/original_100/N/tripinfo.xml> --summary-output <output\verification\final/original_100/N/stats.xml> --fcd-output <output\verification\final/original_100/N/traj.xml>`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_100

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\.worktrees\ia-ib-completion\engine\configs/demo_N.sumocfg> --no-step-log true -e 100 --tripinfo-output <output\verification\final/enhanced_100/N/tripinfo.xml> --summary-output <output\verification\final/enhanced_100/N/stats.xml> --fcd-output <output\verification\final/enhanced_100/N/traj.xml>`
- warning: intersection 9: Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
- warning: intersection 11: Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17
- warning: intersection 11: Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 12: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.
- warning: intersection 18: Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are unsafe.

## enhanced_3600

Command: `sumo -c <C:\Users\peng\Desktop\project\ChallengeCup\.worktrees\ia-ib-completion\engine\configs/demo_N.sumocfg> --no-step-log true -e 3600 --tripinfo-output <output\verification\final/enhanced_3600/N/tripinfo.xml> --summary-output <output\verification\final/enhanced_3600/N/stats.xml> --fcd-output <output\verification\final/enhanced_3600/N/traj.xml>`
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

## baseline_runs

Command: `python -m experiments.runner --intersection <1|11|16> --algorithm actuated --steps 3600 --flow-multiplier 1.0 --seed 42 --output-dir output\verification\final\baseline_runs`

## stress_runs

Command: `python scripts/stress_memory.py --algorithm actuated --intersections 1 11 16 --steps 3600 --flow-multiplier 1.5 --output-root output\verification\final\stress --max-python-mib 1024`

## docker_static

Command: `python -m pytest tests/test_docker_static.py -q; docker build -t ca-mp:ia-ib -f docker/Dockerfile .; docker run --rm ca-mp:ia-ib 1 (live commands conditional)`
- warning: live validation: Docker unavailable; not run

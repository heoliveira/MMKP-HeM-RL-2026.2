#!/bin/bash
# =============================================================================
# EN: Runs the full experiment: several instances, both penalty scenarios, ONE process at a time.
# PT: Roda o experimento completo: várias instâncias, os dois cenários de custo, UM processo por vez.
#
# Usage / Uso:   scripts/run_experiment.sh OUT_DIR
# Variables / Variáveis (all optional):
#   INSTANCES=10   START=12000 STEP=2000 END=20000   RUNS=50   SEED=1
#   ALPHA=0.999    OPTIONS=1,2,3    CPU=2    BIN=build/MMKP_IoT-EC-CC
#
# Layout:  OUT_DIR/inst_K/data/             demands shared by both scenarios (generated once)
#          OUT_DIR/inst_K/fixo/results/     unit penalty (1.0 per device)
#          OUT_DIR/inst_K/variavel/results/ task-proportional penalty
#
# Why one process at a time: parallel runs slow each other down and distort Execution_time.
# =============================================================================
set -e

OUT=${1:?"usage: scripts/run_experiment.sh OUT_DIR"}
INSTANCES=${INSTANCES:-10}
START=${START:-12000}; STEP=${STEP:-2000}; END=${END:-20000}
RUNS=${RUNS:-50}; SEED=${SEED:-1}; ALPHA=${ALPHA:-0.999}
OPTIONS=${OPTIONS:-}
CPU=${CPU:-2}
BIN=$(realpath "${BIN:-build/MMKP_IoT-EC-CC}")

[ -x "$BIN" ] || { echo "binary not found: $BIN (run ./build.sh --no-cplex --no-run)"; exit 1; }
[ -e "$OUT" ] && { echo "$OUT already exists; choose a new folder"; exit 1; }
mkdir -p "$OUT"
OUT=$(realpath "$OUT")

COMMON=(--seed "$SEED" --devices-start "$START" --devices-step "$STEP" --devices-end "$END" --alpha "$ALPHA")
[ -n "$OPTIONS" ] && COMMON+=(--options "$OPTIONS")
# taskset pins the process to one core (skipped if unavailable)
PIN=(); command -v taskset >/dev/null && PIN=(taskset -c "$CPU")

echo "[$(date +%T)] start: $INSTANCES instances, sizes $START..$END step $STEP, $RUNS runs, alpha=$ALPHA, seed=$SEED" | tee -a "$OUT/progress.log"
for k in $(seq 1 "$INSTANCES"); do
    d="$OUT/inst_$k"
    mkdir -p "$d"
    # --runs 0 only generates services, servers and devices for this instance
    (cd "$d" && "$BIN" "${COMMON[@]}" --instance "$k" --runs 0 > gen.log 2>&1)
    for scen in fixo variavel; do
        fp=0; [ "$scen" = "fixo" ] && fp=1
        mkdir -p "$d/$scen"
        ln -s ../data "$d/$scen/data"
        (cd "$d/$scen" && "${PIN[@]}" "$BIN" "${COMMON[@]}" --instance "$k" --runs "$RUNS" --fixed-penalty "$fp" > run.log 2>&1)
        echo "[$(date +%T)] inst_$k $scen done" | tee -a "$OUT/progress.log"
    done
done
echo "[$(date +%T)] ALL DONE" | tee -a "$OUT/progress.log"

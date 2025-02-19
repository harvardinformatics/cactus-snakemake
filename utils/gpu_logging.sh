#!/bin/bash

#salloc --partition=gpu_test --gres=gpu:4 --cpus-per-task=64 --mem=50000 --time=120 --job-name=cactus_tests

# Create a log file to store GPU utilization data
GPU_LOGFILE="gpu-usage.log"

# Define your desired fields to log
FIELDS=(
    timestamp
    utilization.gpu
    utilization.memory
    memory.total
    memory.free
    memory.used
)

# Join fields with commas to create the query string
QUERY=$(IFS=,; echo "${FIELDS[*]}")


# Use a loop to log GPU utilization every few seconds
echo "STARTING GPU LOGGING: $GPU_LOGFILE"
while sleep 1; do
    nvidia-smi --query-gpu=$QUERY --format=csv >> "$GPU_LOGFILE"
done &
MONITOR_PID=$!

#singularity exec --nv --cleanenv /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-preprocess /tmp/simCow_chr6-mask /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt --inputNames simCow_chr6 --logInfo --retryCount 0 --maxCores 8 --gpu 4 
singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-blast /tmp/mr-blast /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.cigar --root mr --logInfo --retryCount 0 --lastzCores 48 --gpu 1
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-align /tmp/mr-align /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.cigar /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.hal --root mr --logInfo --retryCount 0 --workDir /n/holylfs05/LABS/informatics/Users/gthomas/tmp/ --maxCores 24 --defaultDisk 450G --gpu

# After your work is complete, kill the nvidia-smi logging process
echo "----------" >> "$GPU_LOGFILE"
kill $MONITOR_PID
echo "FINISHING GPU LOGGING: $GPU_LOGFILE"

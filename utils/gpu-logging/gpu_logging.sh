#!/bin/bash
#SBATCH --job-name=cactus_gpu_logging_preprocess
#SBATCH --output=%x-%j.out
#SBATCH --mail-type=ALL
#SBATCH --mail-user=gthomas@g.harvard.edu
#SBATCH --partition=gpu
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100g
#SBATCH --time=1:00:00


# Create a log file to store GPU utilization data
GPU_LOGFILE="gpu-usage-turtle-preprocess.log"

# Detect the number of GPUs
NUM_GPUS=$(nvidia-smi --query-gpu=count --format=csv,noheader,nounits | head -n 1)

# Define desired fields to log
FIELDS=(
    utilization.gpu
    utilization.memory
    memory.total
    memory.free
    memory.used
)

# Join fields with commas to create the query string
QUERY=$(IFS=,; echo "${FIELDS[*]}")

# Construct the header dynamically based on the number of GPUs
HEADER="timestamp"
for ((i=0; i<NUM_GPUS; i++)); do
    for field in "${FIELDS[@]}"; do
        HEADER="$HEADER, gpu_${i}_${field} [% or MiB]"
    done
done

# Write the header to the log file
echo "$HEADER" > "$GPU_LOGFILE"

# Use a loop to log GPU utilization every second
echo "STARTING GPU LOGGING: $GPU_LOGFILE"
while sleep 1; do
    TIMESTAMP=$(date +"%Y/%m/%d %H:%M:%S.%3N")
    # Query GPU data
    GPU_DATA=$(nvidia-smi --query-gpu=$QUERY --format=csv,noheader,nounits)
    # Format the GPU data to fit on one line
    GPU_LINE=$(echo "$GPU_DATA" | tr '\n' ',' | sed 's/,$/\n/')
    echo "$TIMESTAMP, $GPU_LINE" >> "$GPU_LOGFILE"
done &
MONITOR_PID=$!


# Turtle preprocess
singularity exec --nv --cleanenv /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus_v2.9.3-gpu.sif cactus-preprocess /tmp/Cserpentina-mask /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/genomes.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus-out/genomes.txt --inputNames Cserpentina --logInfo --retryCount 0 --maxCores 8 --gpu 2

# Turtle blast
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus_v2.9.3-gpu.sif cactus-blast /tmp/Anc06-blast /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus-out/genomes.txt Anc06.cigar --root Anc06 --logInfo --retryCount 0 --lastzCores 64 --gpu 4

# Turtle align
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus_v2.9.3-gpu.sif cactus-align /tmp/Anc06-align /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus-out/genomes.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/turtles/cactus-out/Anc06.cigar Anc06.hal --root Anc06 --logInfo --retryCount 0 --workDir /n/holylfs05/LABS/informatics/Users/gthomas/tmp/ --maxCores 64 --defaultDisk 450G --gpu

# Mammal blast
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals/cactus_v2.9.3-gpu.sif cactus-blast /tmp/mr-blast /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals/evolverMammals-out/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals/evolverMammals-out/mr.cigar --root mr --logInfo --retryCount 0 --lastzCores 24 --gpu 1

#singularity exec --nv --cleanenv /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-preprocess /tmp/simCow_chr6-mask /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt --inputNames simCow_chr6 --logInfo --retryCount 0 --maxCores 8 --gpu 4 
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-blast /tmp/mr-blast /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.cigar --root mr --logInfo --retryCount 0 --lastzCores 48 --gpu 1
#singularity exec --nv --cleanenv --bind /n/holylfs05/LABS/informatics/Users/gthomas/tmp/:/tmp /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/cactus_v2.9.3-gpu.sif cactus-align /tmp/mr-align /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/evolverMammals.txt /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.cigar /n/holylfs05/LABS/informatics/Users/gthomas/cactus-snakemake/tests/evolverMammals-out-gpu/mr.hal --root mr --logInfo --retryCount 0 --workDir /n/holylfs05/LABS/informatics/Users/gthomas/tmp/ --maxCores 24 --defaultDisk 450G --gpu


#python gpu_load.py
# Load test - needs short sleep interval (0.1s) to capture GPU load

# After your work is complete, kill the nvidia-smi logging process
echo "----------" >> "$GPU_LOGFILE"
kill $MONITOR_PID
echo "FINISHING GPU LOGGING: $GPU_LOGFILE"
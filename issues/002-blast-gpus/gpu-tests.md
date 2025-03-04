I guess this might be helpful:

| SLURM GPUs (`gres=gpu:N`) | `cactus-blast` GPUs (`--gpu N`) | # of physical GPUs from `nvidia-smi` | # of MIG devices from `nvidia-smi` | Result | # Physical GPU >= `--gpu N`? | # MIG devices >= `--gpu N`? |
| ------------------------- | ------------------------------- | ------------------------------------ | ---------------------------------- | ------ | ---------------------------- | --------------------------- |
| 1 | 1 | 1 | 1 | Success   | T | T |
| 1 | 2 | 1 | 1 | Error     | F | F |
| 1 | 3 | 1 | 1 | Error     | F | F |
| 1 | 4 | 1 | 1 | Error     | F | F |
| 2 | 1 | 1 | 2 | Success   | T | T |
| 2 | 2 | 1 | 2 | Error     | F | T ⭐ |
| 2 | 3 | 1 | 2 | Error     | F | F | 
| 2 | 4 | 1 | 2 | Error     | F | F |
| 3 | 1 | 2 | 3 | Success   | T | T |
| 3 | 2 | 2 | 3 | Success   | T | T |
| 3 | 3 | 2 | 3 | Error     | F | T ⭐ |
| 3 | 4 | 2 | 3 | Error     | F | F |
| 3 | 1 | 3 | 3 | Success   | T | T |
| 3 | 2 | 3 | 3 | Success   | T | T |
| 3 | 3 | 3 | 3 | Success   | T | T |
| 3 | 4 | 3 | 3 | Error     | F | F |
| 4 | 1 | 2 | 4 | Success   | T | T |
| 4 | 2 | 2 | 4 | Success   | T | T |
| 4 | 3 | 2 | 4 | Error     | F | T ⭐ |
| 4 | 4 | 2 | 4 | Error     | F | T ⭐ |
| 4 | 1 | 3 | 4 | Success   | T | T |
| 4 | 2 | 3 | 4 | Success   | T | T |
| 4 | 3 | 3 | 4 | Success   | T | T |
| 4 | 4 | 3 | 4 | Error     | F | T ⭐ |

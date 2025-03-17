#!/usr/bin/env bash
#
# Usage: ./filter_gpu_log.sh gpu-usage.log
#
# Prints lines from gpu-usage.log where *any* GPU utilization > 0
# or memory used > 1 MiB.

if [ $# -ne 1 ]; then
  echo "Usage: $0 <gpu-log-file>"
  exit 1
fi

LOGFILE="$1"

awk -F, '
NR == 1 {
  # Print header as-is
  print
  next
}
{
  # The first field is timestamp, so GPU data begins at column 2.
  # Each GPU has 5 columns in the order:
  #   utilization.gpu, utilization.memory, memory.total, memory.free, memory.used
  #
  # So for GPU 0: columns 2..6,
  #    GPU 1:     columns 7..11,
  #    GPU 2:     columns 12..16,
  # etc.
  #
  # We iterate through the columns in steps of 5, checking:
  #   - utilization.gpu (column i) > 0
  #   - memory.used     (column i+4) > 1

  for (i = 2; i <= NF; i += 5) {
    # Force numeric comparison using +0
    if (($(i) + 0) > 0 || ($(i + 4) + 0) > 1) {
      print
      next
    }
  }
}
' "$LOGFILE"
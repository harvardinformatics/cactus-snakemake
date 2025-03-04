import pynvml
import time

def monitor_mig(interval=5):
    pynvml.nvmlInit()
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        while True:
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                print(f"GPU {i}: {pynvml.nvmlDeviceGetName(handle)}")
                
                # Retrieve the MIG mode as a tuple (current, pending)
                mig_current, mig_pending = pynvml.nvmlDeviceGetMigMode(handle)
                print(f"  MIG Mode: Current: {mig_current}, Pending: {mig_pending}")
                
                # If MIG is enabled (assuming '1' indicates enabled)
                if mig_current == 1:
                    # Assuming MIG instance checking process
                    gpu_instances_count = pynvml.nvmlDeviceGetMaxMigDeviceCount(handle)
                    for j in range(gpu_instances_count):
                        try:
                            gpu_instance = pynvml.nvmlDeviceGetGpuInstanceById(handle, j)
                            stats = pynvml.nvmlDeviceGetMemoryInfo(gpu_instance.handle)
                            utilization = pynvml.nvmlDeviceGetUtilizationRates(gpu_instance.handle)
                            print(f"  GPU Instance {j}:")
                            print(f"    Memory Used: {stats.used / 1024 / 1024} MiB")
                            print(f"    Utilization: {utilization.gpu}% GPU, {utilization.memory}% Memory")
                        except pynvml.NVMLError_NotFound:  # Handle non-existent instances
                            continue
            time.sleep(interval)
    except Exception as e:
        print(f"Error monitoring: {e}")
    finally:
        pynvml.nvmlShutdown()

if __name__ == "__main__":
    monitor_mig(interval=1)
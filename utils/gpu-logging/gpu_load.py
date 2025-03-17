import tensorflow as tf
import time
import os

# Ensure you're utilizing CUDA
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow logging information for clarity

# Check number of GPUs available
print("Num GPUs Available: ", len(tf.config.experimental.list_physical_devices('GPU')))

# Set mixed precision policy (if supported and applicable for your device)
# from tensorflow.keras.mixed_precision import experimental as mixed_precision
# policy = mixed_precision.Policy('mixed_float16')
# mixed_precision.set_policy(policy)

##########

# matrix_size = 20000  # Really big
# matrix1 = tf.random.uniform((matrix_size, matrix_size))
# matrix2 = tf.random.uniform((matrix_size, matrix_size))

# while True:
#     product = tf.linalg.matmul(matrix1, matrix2)
#     _ = product.numpy()

# This continuous loop ensures that the GPU is fully utilized
##########

matrix_size = 10000  # Further increase matrix size for heavier load
num_iterations = 5000  # Increase to ensure extended workload duration

# Create a large computational graph that runs multiple operations
start_time = time.time()
result = []
for i in range(5):  # Running parallel tasks
    matrix1 = tf.random.uniform((matrix_size, matrix_size))
    matrix2 = tf.random.uniform((matrix_size, matrix_size))
    product = tf.linalg.matmul(matrix1, matrix2)
    result.append(product)

# Run the operation with more iterations
for _ in range(num_iterations):
    for res in result:
        output = res.numpy()  # Ensure execution on GPU

print("Time taken for matrix multiplications on GPU:", time.time() - start_time)
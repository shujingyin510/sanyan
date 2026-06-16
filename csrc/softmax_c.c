
// simd_c_softmax: 精确 softmax 使用 C 的 expf
#include <math.h>
#include <string.h>

void softmax_c(float* input, float* output, int N) {
    // 1. find max
    float max_val = input[0];
    for (int i = 1; i < N; i++) {
        if (input[i] > max_val) max_val = input[i];
    }
    // 2. exp(x-max) + sum
    float sum = 0.0f;
    for (int i = 0; i < N; i++) {
        output[i] = expf(input[i] - max_val);
        sum += output[i];
    }
    // 3. divide
    if (sum > 0.0f) {
        for (int i = 0; i < N; i++) {
            output[i] /= sum;
        }
    }
}

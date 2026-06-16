// Transformer kernels: LayerNorm + GELU + FFN
#include <math.h>

// LayerNorm: y = (x - mean) / sqrt(var + eps) * gamma + beta
void layernorm(float* x, float* gamma, float* beta, float* y, int N, float eps) {
    float sum = 0, sum_sq = 0;
    for (int i = 0; i < N; i++) { sum += x[i]; sum_sq += x[i]*x[i]; }
    float mean = sum / N;
    float var = sum_sq / N - mean*mean;
    float inv_std = 1.0f / sqrtf(var + eps);
    for (int i = 0; i < N; i++) {
        y[i] = (x[i] - mean) * inv_std * gamma[i] + beta[i];
    }
}

// GELU activation
void gelu(float* x, float* y, int N) {
    for (int i = 0; i < N; i++) {
        float v = x[i];
        float c = 0.7978845608f; // sqrt(2/pi)
        float x3 = v * v * v;
        y[i] = 0.5f * v * (1.0f + tanhf(c * (v + 0.044715f * x3)));
    }
}

// Residual connection: y = x + residual
void residual_add(float* x, float* residual, int N) {
    for (int i = 0; i < N; i++) x[i] += residual[i];
}

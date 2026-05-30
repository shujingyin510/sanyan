/*
 * sensor_fusion.c — 二值逻辑传感器融合（对比实现）
 * 功能与 sensor_fusion.san 相同
 * 展示 C 语言处理三态需要多少额外代码
 */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stdbool.h>

/* C 语言没有三值类型，必须用枚举 + switch */
typedef enum { STATE_TRUE, STATE_FALSE, STATE_MAYBE } tristate_t;

typedef struct {
    tristate_t state;
    int value;
} sensor_reading_t;

/* 三值 AND — C 需要手写，三言内置 */
tristate_t tri_and(tristate_t a, tristate_t b) {
    if (a == STATE_FALSE || b == STATE_FALSE) return STATE_FALSE;
    if (a == STATE_TRUE && b == STATE_TRUE) return STATE_TRUE;
    return STATE_MAYBE;
}

/* 三值 OR — C 需要手写 */
tristate_t tri_or(tristate_t a, tristate_t b) {
    if (a == STATE_TRUE || b == STATE_TRUE) return STATE_TRUE;
    if (a == STATE_FALSE && b == STATE_FALSE) return STATE_FALSE;
    return STATE_MAYBE;
}

tristate_t simulate_sensor(const char *name, int fault_rate) {
    int r = rand() % 100 + 1;
    if (r <= fault_rate) return STATE_FALSE;
    if (r <= fault_rate + 10) return STATE_MAYBE;
    return STATE_TRUE;
}

sensor_reading_t read_temperature(void) {
    tristate_t state = simulate_sensor("temp", 15);
    sensor_reading_t r = {state, 0};
    if (state == STATE_TRUE) r.value = rand() % 18 + 18;
    else if (state == STATE_MAYBE) r.value = 0;
    else r.value = -999;
    return r;
}

sensor_reading_t read_humidity(void) {
    tristate_t state = simulate_sensor("humid", 10);
    sensor_reading_t r = {state, 0};
    if (state == STATE_TRUE) r.value = rand() % 51 + 30;
    else r.value = -999;
    return r;
}

sensor_reading_t read_gas(void) {
    tristate_t state = simulate_sensor("gas", 20);
    sensor_reading_t r = {state, 0};
    if (state == STATE_TRUE) r.value = rand() % 501;
    else r.value = -999;
    return r;
}

tristate_t fuse_states(tristate_t *states, int n) {
    /* C 需要循环 + 显式枚举比较 */
    bool has_fault = false, has_maybe = false, all_true = true;
    for (int i = 0; i < n; i++) {
        if (states[i] == STATE_FALSE) has_fault = true;
        if (states[i] == STATE_MAYBE) has_maybe = true;
        if (states[i] != STATE_TRUE) all_true = false;
    }
    if (has_fault) return STATE_FALSE;
    if (all_true) return STATE_TRUE;
    return STATE_MAYBE;
}

tristate_t temperature_safe(int temp) {
    if (temp == -999) return STATE_MAYBE;
    if (temp > 40 || temp < 10) return STATE_FALSE;
    return STATE_TRUE;
}

tristate_t humidity_safe(int humid) {
    if (humid == -999) return STATE_MAYBE;
    if (humid > 90 || humid < 20) return STATE_FALSE;
    return STATE_TRUE;
}

tristate_t gas_safe(int gas) {
    if (gas == -999) return STATE_MAYBE;
    if (gas > 400) return STATE_FALSE;
    if (gas > 200) return STATE_MAYBE;
    return STATE_TRUE;
}

const char* state_str(tristate_t s) {
    switch (s) {
        case STATE_TRUE: return "真";
        case STATE_FALSE: return "假";
        case STATE_MAYBE: return "可能";
    }
    return "?";
}

void environment_decision(tristate_t overall, int temp, int humid, int gas) {
    switch (overall) {
        case STATE_FALSE:
            printf("🚨 警报：传感器故障或环境危险！\n");
            printf("  温度: %d  湿度: %d  气体: %d\n", temp, humid, gas);
            printf("  决策: 紧急停机\n");
            break;
        case STATE_MAYBE:
            printf("⚠️ 警告：部分传感器离线，降级运行\n");
            if (temp > 35) printf("  决策: 降级-开启风扇\n");
            else printf("  决策: 降级-维持现状\n");
            break;
        case STATE_TRUE:
            printf("✅ 环境正常，全速运行\n");
            if (temp > 30) printf("  决策: 开启空调\n");
            else if (humid < 40) printf("  决策: 开启加湿器\n");
            else printf("  决策: 维持现状\n");
            break;
    }
}

int main(void) {
    srand((unsigned)time(NULL));

    printf("═══════════════════════════════════════\n");
    printf("  二值逻辑传感器融合系统 v1.0 (C)\n");
    printf("═══════════════════════════════════════\n\n");

    int count_normal = 0, count_uncertain = 0, count_abnormal = 0;

    for (int round = 1; round <= 10; round++) {
        printf("--- 第 %d 轮检测 ---\n", round);

        sensor_reading_t temp = read_temperature();
        sensor_reading_t humid = read_humidity();
        sensor_reading_t gas = read_gas();

        tristate_t temp_safe = temperature_safe(temp.value);
        tristate_t humid_safe = humidity_safe(humid.value);
        tristate_t gas_s = gas_safe(gas.value);

        tristate_t sensor_states[] = {temp.state, humid.state, gas.state};
        tristate_t safety_states[] = {temp_safe, humid_safe, gas_s};

        tristate_t sensor_fusion = fuse_states(sensor_states, 3);
        tristate_t safety_fusion = fuse_states(safety_states, 3);
        tristate_t final_state = tri_and(sensor_fusion, safety_fusion);

        printf("  传感器: 温度=%s 湿度=%s 气体=%s → 融合=%s\n",
               state_str(temp.state), state_str(humid.state),
               state_str(gas.state), state_str(sensor_fusion));
        printf("  安全性: 温度=%s 湿度=%s 气体=%s → 融合=%s\n",
               state_str(temp_safe), state_str(humid_safe),
               state_str(gas_s), state_str(safety_fusion));

        environment_decision(final_state, temp.value, humid.value, gas.value);
        printf("\n");

        switch (final_state) {
            case STATE_TRUE: count_normal++; break;
            case STATE_MAYBE: count_uncertain++; break;
            case STATE_FALSE: count_abnormal++; break;
        }
    }

    printf("═══════════════════════════════════════\n");
    printf("  统计汇总\n");
    printf("═══════════════════════════════════════\n");
    printf("  正常: %d 轮\n", count_normal);
    printf("  不确定: %d 轮\n", count_uncertain);
    printf("  异常: %d 轮\n", count_abnormal);
    printf("\n");
    printf("C 语言需要：enum 定义、手写 tri_and/tri_or、switch-case 处理\n");
    printf("三言只需：真/假/可能 + 且/或/非 运算符\n");
    return 0;
}

# 三态 vs 二值：对比示例诚实索引

每个「卖点」示例都配了一个三言版（`.san`）和一个**诚实、不偷工**的二值对照
（`.py`，标准 Python，开箱即跑）。这里如实标注每个对比的强弱——不是每个例子都
能证明「二值做不到」，硬吹反而扣分。

## 一句话评级

| 示例 | 对照文件 | 差距强度 | 三态真正赢在哪 |
|------|----------|----------|----------------|
| `circuit_sim`  | `circuit_sim.py`  | 🟢 **强** | Python 必须先手写整套 Kleene 代数；三言内置且保证正确，无从写错真值表 |
| `data_cleaning`| `data_cleaning.py`| 🟡 中偏弱 | Python 能写对（返回 None），但不被强制；优势是「默认安全 + 自动传播」 |
| `sensor_fusion`| `sensor_fusion.py` / `.c` | 🟡 弱 | 三态 Enum 也能干净处理；差距主要在写法，不在能力 |
| `health_check` | `health_check.py` | 🔴 **弱** | `Enum{UP,TIMEOUT,DOWN}` 完全平替，代码量相当——不该宣称「二值做不到」 |
| `npc_decision` | `npc_decision.py` | 🔴 **弱** | 原对照是稻草人；诚实 Python 用 `None` 表达犹豫，零随机、零抖动 |

## 结论：哪个例子该当门面

**`circuit_sim` 是唯一一个差距来自语言能力本身的例子**——三言把一套经数学
证明正确的 Kleene 三值代数冻进 `且/或/非`，Python 要做同样的事必须自己造地基，
且任何一格真值表写错都会让下游电路静默出错。这才是「三态不是方便，是正确」的硬证据。

其余几个例子，本质是「三态作为一等值，写起来更顺手 / 默认更安全」，
属于人体工学与默认值层面的优势，**不是二值范式做不到的事**。把它们如实降级、
集中火力打磨 `circuit_sim`（以及 `data_cleaning` 的自动传播角度），
比把每个例子都包装成「Python 无能为力」更有说服力。

## 本地验证命令

> 运行环境当时没起来，这批文件未经实跑验证，请本地确认。

```bash
# 三言版（需要解释器）
python -X utf8 main.py examples/circuit_sim.san
python -X utf8 main.py examples/data_cleaning.san
python -X utf8 main.py examples/health_check.san
python -X utf8 main.py examples/npc_decision.san

# 二值对照版（纯标准 Python，直接跑）
python examples/circuit_sim.py
python examples/data_cleaning.py
python examples/health_check.py
python examples/npc_decision.py
```

对照时重点看：

- `circuit_sim.py`：注意 `Trit` 类那 25 行地基——三言里这是 0 行。
- `data_cleaning.py`：`score_careless`（返回 0，bug）vs `score_safe`（返回 None，正确）。
  看二值是否真会静默出错——会，但只在你写草率版时；写对了就和三言一致。
- `health_check.py` / `npc_decision.py`：看二值版是否真有短板——基本没有，
  这正是该如实承认的地方。

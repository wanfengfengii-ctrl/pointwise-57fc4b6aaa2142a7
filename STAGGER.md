# 双台架错峰签发

`README.md` 记录现有的规程登记、冻结、实收、同起点签发和按号领取。错峰签发使用同样的实收件。夜班能按左右顺序选择具体实收号，站库关闭后仍可办理。

## 签发与领取

```python
from review import sign_stagger
from records import get

signed = sign_stagger(catalog, archive, left_id, right_id, before_commit=None)
retrieved = get(archive, signed.report_id)
```

`catalog` 和 `archive` 是现有 API 中已初始化的实收库和档案库。`left_id`、`right_id` 是不同台架的实收号。起拍差 `d` 为右台起拍减左台起拍，正数表示右台晚开。两台本地都从第 1 拍计数。左台本地拍 `tL` 与右台本地拍 `tR` 落在同一绝对拍，当且仅当 `tL - tR == d`。

两台相互独立。对每个整数 `d`，评分是双方最终都通过时，两台首次通过落在同一绝对拍的条件概率。差值覆盖正负两侧和零。存在无限重试的规程时也须给出有限次计算后的精确结果。共同最终通过概率为零时，签发合法空计划。

签发结果和按号领取结果都有 `report_id`、`draft`、`receipt`。错峰正文含以下字段。

- `draft.joint_pass` 为 `Fraction` 类型的共同最终通过概率。
- `draft.offsets` 是以升序排列的全部最优整数差值组成的元组。空计划用 `()`。
- `draft.conditional_sync` 为 `Fraction` 类型的最优评分。空计划为 `None`。
- `draft.parents` 为左右有序的两份 V1 `ParentReference`，各自保留实收号、件号、台架、修订、分析号和摘要。`receipt` 沿用 V1 的首执结构。

正文、左右父件与首执须在一次档案事务中签存。`before_commit` 为可选的无参数钩子，在上述数据暂存后、提交前执行。钩子异常原样传出，整单回滚，档案没有可领取的新成果。选件错误抛 `intake.select.ParentSelectionError`，任一父件的首达证据错误抛 `review.sync.UnusableEvidence`。

关闭实收库并重开档案后，`records.get` 按号返回当时签发的正文、原父件和首执，未知号返回 `None`。已有档案可继续使用 `initialize_archive` 初始化。`review.sign` 的同起点签发及 V1 报告的原值领取继续可用。

## 样例规程

`stagger_examples.issue_pair(station, catalog, case)` 向已初始化的站库和实收库登记、冻结并接纳一对规程，返回左、右实收号。`python3 -B stagger_examples.py` 使用这些规程执行 V1 签发和重开领取，展示现有同起点口径。以下是新增错峰签发应给出的结果。

| 样例 | 冻结规程 | 共同通过概率 | 全部最优差 | 最优条件概率 |
| --- | --- | --- | --- | --- |
| `tie` | 左台仅在第 1、3 拍各有 1/2 首达质量，右台首拍必过 | 1 | `(0, 2)` | 1/2 |
| `closed` | 左台在第 1、3 拍各有 1/4 首达质量，另有 1/2 永久继续，右台首拍必过 | 1/2 | `(0, 2)` | 1/2 |
| `dead` | 左台永久继续，右台首拍必过 | 0 | `()` | `None` |
| `retry` | 左台比右台晚两拍开始尝试。两台随后各以每拍 1/2 的概率通过，未通过则下一拍再试 | 1 | `(2,)` | 1/3 |
| `long` | 左台第 129 拍必过，右台首拍必过 | 1 | `(128,)` | 1 |

交换 `tie` 的左右实收号时，期望差集为 `(-2, 0)`，条件概率仍为 1/2，父件及首执的实收顺序也须相应交换。

## 运行交付

现有 `.pointwise-runtime.json` 以 `version` 为 1、`kind` 为 `cli` 登记入口。`setup` 是准备命令的参数数组列表，本项目可用空列表。`verify` 和 `demo` 各是一条命令的参数数组。交付时 `verify` 须执行完整原回归及错峰业务核验，失败退出非零。`demo` 须实际签发错峰计划，并展示关闭实收库、重开档案后领取的差集、概率和有序父件。

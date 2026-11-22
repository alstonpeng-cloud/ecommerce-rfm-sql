# 电商用户价值分层与精准营销（SQL 实战）

从三张**原始交易流水表**出发，用纯 SQL 完成 RFM 用户分层与营销策略评估。固定种子、一条命令复现、零第三方依赖。

> **数据边界**：全部为固定种子生成的合成数据，仅用于方法演示，不代表任何真实业务收益或真实用户行为。

## 这个项目解决了什么

参考教程里的 RFM 项目读取的是**已经算好 RFM 字段的用户宽表**，再用 pandas 逐行 `if/else` 做分层。本项目把取数、清洗、指标计算、分层、策略评估**全部放进 SQL**，并补上原版没有的重复日志处理、异常订单过滤、互斥分层和 ROI 敏感性分析。

## 相比参考实现的改进

| 环节 | 参考实现 | 本项目 |
| --- | --- | --- |
| 数据入口 | 现成用户宽表（RFM 字段已给） | 三张原始表：users / orders / order_items |
| 指标计算 | pandas 逐行 apply | 纯 SQL：CTE + JOIN + GROUP BY |
| 分层打分 | 硬编码阈值（>60 / <40） | `NTILE(5)` 五分位打分，自适应数据分布 |
| 分层规则 | 链式 if/else，后面的分支会覆盖前面的 | 互斥 `CASE WHEN`，8 类正交不重叠 |
| 数据清洗 | 未处理 | `DISTINCT` 去重日志重传 + 过滤取消/退款单 |
| 金额口径 | 现成字段 | 从明细 `quantity × unit_price` 逐单汇总 |
| ROI 评估 | 单一假设下的一个 ROI 数字 | 4 档提升率敏感性网格，检验结论是否稳健 |
| 可复现性 | 本地绝对路径 | 固定种子生成 + 一条命令重建 |
| 结果校验 | 无 | 独立 Python 计算交叉核对 SQL 口径 |

## 技术要点

- **多表 JOIN + 聚合**：订单金额由 `order_items` 明细汇总，不是读现成字段；
- **窗口函数**：`NTILE(5)` 对 R/F/M 分别打五分位分，`ROW_NUMBER()` 做预算截断；
- **数据清洗**：`SELECT DISTINCT` 去掉模拟的日志重传，`WHERE status='completed'` 排除无效单；
- **互斥分层**：8 类 `CASE WHEN` 按 R/F/M 高低组合，规则可读、可直接翻译成业务动作；
- **口径校验**：`tests/test_pipeline.py` 用独立 Python 计算复算 RFM，与 SQL 结果逐用户比对。

## 数据说明

| 表 | 行数 | 说明 |
| --- | --- | --- |
| users | 2,000 | 用户属性：注册时间、年龄、收入、订阅、兴趣、城市 |
| orders | 1,336 | 订单流水：含约 2% 重复日志行、取消/退款状态 |
| order_items | 3,259 | 订单明细：商品品类、数量、单价 |

快照日期 `2025-06-30`。全部字段由 `data/generate_data.py` 按固定种子生成。

## 运行方式

```bash
python run.py                  # 生成库 + 执行 SQL + 导出结果
python tests/test_pipeline.py  # 交叉校验（可选）
```

无需 `pip install`：只使用 Python 标准库（3.9+）。产物在 `rfm.sqlite` 与 `output/`。

## 结果摘要（来自实际运行）

- 去重后 1,063 笔有效订单，679 名有购买记录的用户进入分层；
- **重要价值客户**占 34.0%，贡献 **57.4%** 的消费额；
- **重要保持客户**（高消费但已沉睡）占 21.6%，贡献 **29.1%** —— 是唤醒活动的优先人群；
- ROI 敏感性：在 4 档转化率提升假设下，精准人群策略**在每一档**都优于传统「高消费前 20%」发券（传统 144.5%–715.1%，精准 715.1%–1937.7%）；

> ROI 中的转化率提升为可调假设参数，非真实实验测得，仅用于比较策略排序。

## 项目结构

```
ecommerce-rfm-sql/
├── data/generate_data.py          # 固定种子合成三张流水表
├── sql/01_rfm_segmentation.sql    # 清洗 → RFM → NTILE → 8 分层 → 汇总
├── sql/02_campaign_roi.sql        # 4 档 ROI 敏感性网格
├── run.py                         # 一键运行
├── tests/test_pipeline.py         # 独立复算交叉校验
└── output/                        # 运行后生成的结果 CSV
```

## 参考与致谢

本项目的方法论参考了以下公开教程，代码为独立重写与改进：

- B 站教程《带你做一个真正有含金量的数据分析实战项目》：https://www.bilibili.com/video/BV1DkPcz7Esa/
- 飞书文档《电商用户价值分层与精准营销策略项目明细》：https://my.feishu.cn/wiki/JWxWwaet1iWqoHkpfkycgod8nEh
- Kaggle 参考数据集：https://www.kaggle.com/datasets/kartikaybartwal/ecommerce-product-recommendation-collaborative

本项目以 MIT 协议开源。

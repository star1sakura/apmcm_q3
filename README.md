# Semiconductor Policy Model - Problem 3

## What this project does
A partial-equilibrium model for APMCM Problem C (question 3) to assess U.S. semiconductor policies across high/mid/low-end chips and regions (US/CN/ROW), combining tariffs, subsidies, export controls, economic efficiency, and national security metrics.

## Data used (local only)
- `wash/output/`: cleaned panels (tariff_hs2/hs4, trade_export_panel, trade_duty_panel, exports_CN_sector, etc.).
- `external_data/USITC_DataWeb/hs6_value_qty/`: HS6 854231/232/239 total value + quantity.
- `external_data/USITC_DataWeb/hs6_value_qty_by_partner/`: HS6 854231/232/239 by country value + quantity (used to split CN vs ROW and compute ASP/weights).
- `external_data/UN_Comtrade_semiconductor_trade/` (additional_csv): extra Comtrade CSVs (not core).
- `external_data/FRED_IPG3344S/`: IPG index (optional).
- `external_data/NAICS_3344_Census/`: Census industry stats (optional; folder name contains the Census extract).

## Key files
- `config.py`: paths; elasticities set to Armington H/M/L = 2.0/3.3/4.0 (USITC 334413 + 分档), demand 0.8/1.2/1.5 (Flamm/BEA/ITIF 区间); R&D 强度 SIA 19.5% (US) / 14% (CN) / 11% (ROW); tech progress coeff 0.12/0.08/0.05.
- `classification.py`: HS6-based H/M/L shares, ASP from value+qty, build flows (CN vs ROW) using partner-level DataWeb.
- `calibration.py`: Armington weights, supply/demand shifters, R&D/tech init; uses 2023 partner ASP as base price.
- `policy.py`: scenarios (baseline, tariff_only, tariff_plus_subsidy, diff_by_chip, subsidy_only) with time paths.
- `model_static.py`: single-period equilibrium solver.
- `model_dynamic.py`: R&D -> tech, NSI, welfare.
- `simulate.py`: run scenarios, save CSV/plots; also sensitivity runner.
- `analysis_plots.py`: saves NSI/Welfare/GAP/import share plots.
- `results/`: per-scenario CSVs/plots; `results/sensitivity_summary.csv` and `results/final_summary.csv` for comparison.

## Directory quick view
- `wash/output/`: cleaned panels for baseline calibration.
- `external_data/`: raw/supporting data (USITC DataWeb, Comtrade, FRED, Census, etc.).
- `results/`: outputs (scenario CSVs, summary/final_summary, sensitivity, plots/).
- Code: `config.py`, `classification.py`, `calibration.py`, `policy.py`, `model_static.py`, `model_dynamic.py`, `simulate.py`, `analysis_plots.py`.

## How to run
```bash
python simulate.py
```
Outputs: CSVs in `results/` and PNG plots in `results/plots/`.

## Scenarios (lines in plots)
- baseline: zero chip tariffs; high-end US→CN embargo proxy; baseline growth/feedback.
- tariff_only: global 10% + US↔CN tariffs escalating; demand stagnation; stronger tech feedback; US high-end R&D hit.
- tariff_plus_subsidy: CN tariffs 5/15/20 on H/M/L; subsidies ramp up; higher demand; R&D boost.
- diff_by_chip: high-end 0; CN mid/low tariffs ramp 10→40%; medium growth/feedback.
- subsidy_only: subsidies without new tariffs.

## Outputs to read
- `results/summary.csv`: discounted objectives per scenario.
- Per-scenario CSVs: NSI, Welfare, Obj_t, SAF_H/M/L, US_prod_*, US_import_from_CN_* and shares.
- Plots: NSI/Welfare/gap_H/import share (H/M/L) in `results/plots/`.
- `results/sensitivity_summary.csv`: two sensitivity cases (high/low tariff impact).
- `results/final_summary.csv`: end-year key metrics across scenarios.
- `results/elasticity_phi_sensitivity.csv`: end-year metrics for elasticity/φ sensitivity cases.

## Data & cited references
- 市场规模/R&D 强度：SIA & WSTS（2023 全球销售约 5,268–5,270 亿美元、出货近 1 万亿颗；美国 R&D/收入约 19.5%，中国约 14%）。
- Armington 弹性：USITC NAICS 334413 微观估计约 3.3；高端可替代性更低、低端更高，模型设 H/M/L = 2.0/3.3/4.0。
- 需求弹性：Flamm/BEA/ITIF 对 ICT 需求给出 0.5–1.5（绝对值）；高端最不敏感，低端较敏感。
- 供给弹性：短期 0.5–1 区间、长期可上升；代码取短期偏低值（H/M/L 约 0.8/1.0/1.2 起）。
- 关税与管制锚点：Section 301 关税维持（USTR 四年期回顾）；2022/2023 BIS 高算力与制造设备出口管制作为高端出口限制基线。
- 补贴量级：CHIPS Act 52.7B 美元（39B 制造 + 11B R&D + 25% 投资税抵免）；中国“大基金” I/II/III 总量及拟 1 万亿元扶持用于设定补贴强度阶梯。
- 价格/份额：HS6 854231/232/239 的价值与数量来自 `wash/output` 与 `external_data/USITC_DataWeb/hs6_value_qty*`；伙伴国份额用 `hs6_value_qty_by_partner` 计算，构建 CN/盟友/ROW 权重。2023 基期 ASP（由伙伴级 value/qty 得出）：H ≈ 8.35，M ≈ 0.88，L ≈ 1.68 美元/单位。

## Assumptions to disclose
- Policy paths（关税/补贴/需求/技术反馈时间序列）为情景假设，并非官方时间线。
- 弹性、R&D→TFP 系数 φ、出口管制“强度”数字用于区分情景，非观测值。
- ASP 分档基于 HS6 value/qty 计算；缺口时用平均价及倍数假设兜底。
- Import value approximation 在缺价位时以 duty/MFN 近似，存在偏差。

## 参数来源 vs 假设
- 数据驱动：HS6 854231/232/239 的基期价值/数量与 ASP、CN/ROW 份额（DataWeb/Comtrade 本地文件）；Armington 权重由伙伴流量推得；基期生产/消费尺度 γ/A 已按 2023 流量校准。市场/R&D 规模（WSTS/SIA），Armington 弹性参考 USITC 334413 微观估计。
- 情景设定：关税/补贴/出口管制路径与强度、tech_feedback、R&D 惩罚/奖励系数、φ（R&D→TFP 映射）、需求/供给弹性具体点值、embargo 以高关税近似、无价位时 duty/MFN 的近似。

## Caveats
- 结果用于相对比较，未完全拟合真实价格/成本曲线。
- gap_H 可能分辨度有限，可按需要调整或隐藏。

## Next steps (optional)
- 用伙伴国 value/qty 进一步细化 CN vs ROW ASP 与 Armington 权重。
- 校准 γ/A 使 2023 产出/进出口更贴近观测值；如有官方关税/管制最新公告可更新政策路径。
- 运行更多敏感性（关税/补贴/φ/弹性）以评估稳健性。

## 参考来源（可引用）
- WSTS/SIA 市场与 R&D：全球 2023 销售与出货、R&D/收入（SIA/WSTS 报告）。
- USITC 334413 微观 Armington 弹性（~3.3）及相关文献元分析；Flamm/BEA/ITIF 对 ICT 需求弹性区间。
- Section 301 关税维持（USTR 四年期回顾）；BIS 2022/2023 高算力与制造设备出口管制节点。
- CHIPS and Science Act 总额 52.7B（39B 制造、11B R&D、25% 投资税抵免）；中国大基金 I/II/III 规模及 1 万亿元扶持计划量级。

## 使用与写作提醒
- 数据基础：基期产出/进出口、ASP、CN/ROW 份额来自本地 DataWeb/Comtrade HS6 value+qty；市场规模、R&D 强度来自 WSTS/SIA；Armington/需求弹性取文献区间中值。
- 情景假设：关税/补贴/出口管制路径、tech_feedback、R&D 惩罚/奖励、φ 的具体值、需求/供给弹性点值、embargo 高关税近似、缺价位 duty/MFN 近似均为模型设定，非官方数值。
- 解释局限：gap_H 分叉有限，说明高端技术差对当前设定不敏感；应在论文中注明“模型用于情景对比，不用于精确预测”，并附“数据来源 vs 假设”表。
- 如需更贴近现实，可用官方公告的税率/拨付时间线替换 `policy.py` 中路径，或按需加强/减弱 tech_feedback 与 R&D 惩罚/奖励以测试分叉。

## Environment
- Python 3.x；主要依赖：pandas、matplotlib、openpyxl、numpy。安装示例：`pip install pandas matplotlib openpyxl numpy`（或使用 `requirements.txt` 如有）。

## Scenario legend
- 情景：baseline / tariff_only / tariff_plus_subsidy / diff_by_chip / subsidy_only。
- 图例颜色/线型固定分配；如需突出差异，可仅绘制关键情景或分图展示。

## Adding/modifying scenarios
- 在 `policy.py` 调整关税/补贴路径；在 `simulate.py` 可调 `default_dg`（需求增速）、`default_tf`（tech_feedback）、R&D 奖惩系数以放大或减弱分叉。
- 运行 `python simulate.py` 生成新的 CSV 与图。

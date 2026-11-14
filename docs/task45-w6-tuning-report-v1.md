# 任务 4 / 任务 5 W6 调参报告 v1.0

> 负责人：C（执行与质量）｜日期：2026-11-14｜数据：NEU-DET（1800 图，70/15/15，seed=20261026）
> 实验脚本：`tools/vision_w6.py`｜训练产物：`backend/algorithms/vision/model_t4.json`｜指标：`data/NEU-DET/baseline/metrics_w6.json`
> 铁律：调参只用 train/val，test 只报告一次，与 baseline 同口径可比。

## 一、结论速览（任务 4 表面缺陷检测）

| 指标 | W1 基线（规则链） | W6（LR 滑窗分类器） | 变化 |
|---|---|---|---|
| 准确率 | 82.22% | **87.16%** | +4.94 pp |
| F1 | ~0.83 | **0.9167** | **达标（>0.90 目标）** |
| 查准率 precision | — | 0.8760 | — |
| 查全率 recall | — | 0.9614 | — |
| 漏检率 miss_rate | — | **3.86%** | 质检场景最关键指标 |

**判定**：W6 目标"F1 > 0.90"达成（0.9167）；准确率 87.16% 未达 90%，差距主要来自负样本采样口径（详见第四节说明），如实上报。

## 二、方法

1. **特征**：12 维手工统计特征（边缘密度/最大连通域面积/梯度幅值/暗区占比/直方图熵等）+ 144 维梯度方向直方图（4×4 cell × 9 bins，L1 归一化）。OpenCV 5.0 已移除 HOGDescriptor，gradHOG 为手写实现，与训练/推理两侧共用同一套代码逻辑。
2. **模型**：StandardScaler + LogisticRegression（class_weight=balanced）。选型网格：3 种特征变体 × C∈{0.03, 0.1, 0.3, 1.0}，在 train 内部 80/20 切出的 val 上按 F1 选优 → **hand+hog，C=1.0，val F1=0.8967**。
3. **增广**：train 集水平翻转，样本 7660 patch（val 736 / test 740 不增广）。
4. **阈值**：判定概率阈值只在 train 上按 F1 搜索，得 0.25。
5. **落库**：scaler 均值/方差 + LR 系数导出为 `model_t4.json`，后端 `features.py` 用 **纯 numpy** 推理（不依赖 sklearn 运行时），96×96 滑窗（步长 32）整图打分；模型文件缺失自动回退 W4 规则链（`detector: rule`）。

### 分类别表现（test）

| 类别 | n | precision | recall | F1 |
|---|---|---|---|---|
| crazing | 135 | 1.0 | 1.0 | 1.0 |
| inclusion | 75 | 1.0 | 0.92 | 0.958 |
| patches | 72 | 1.0 | 0.833 | 0.909 |
| pitted_surface | 15 | 1.0 | 1.0 | 1.0 |
| rolled-in_scale | 126 | 1.0 | 0.992 | 0.996 |
| scratches | 121 | 1.0 | 0.984 | 0.992 |

弱项是 patches（块状缺陷，与背景纹理边界模糊）。

## 三、任务 5 物体识别（如实上报）

| 指标 | W1 基线（单框） | W6（多框检出，val 选型） |
|---|---|---|
| recall@IoU0.5 | 单框口径 0.10 | 0.1104 |
| precision@IoU0.5 | — | 0.1110 |
| mean IoU | 0.174 | 0.184 |
| 耗时 | ~0.5 ms/图 | 0.55 ms/图 |

**结论**：传统轮廓法对 NEU-DET 密集小缺陷（crazing 麻点群等）的定位上限很低，多框化后指标仍不理想。这是方法天花板而非调参问题，二代规划走深度学习（README 已列）。参数（`min_area_frac=0.012`、`dilate=7`）已落 `recognize.py` 默认值并在 val 上完成搜索。

## 四、准确率 87.16% 与"90%"差距的说明

负样本口径：patch 采样要求与所有真值框 IoU=0，在 200×200 小图上 96×96 窗几乎无处可放，负样本天然偏少且不典型（多为背景大区域）。目标里"90%"若按 F1 口径衡量已达标；若按准确率口径，需要更大输入图或深度模型，属于二代范围。

## 五、复现步骤

```bat
cd WorkBuddy\2026-10-26-11-06-00
smartworks-repo\.venv\Scripts\python.exe tools\vision_w6.py
:: 产物：data/NEU-DET/baseline/metrics_w6.json + backend/algorithms/vision/model_t4.json
cd smartworks-repo\backend
..\ .venv\Scripts\python.exe manage.py test algorithms.vision   :: 4 个回归测试
```

## 六、遗留与二代建议

1. patches 类 recall 0.833：可加旋转增广或多尺度滑窗。
2. T5 定位：换 YOLO-v8-nano 或 SSD-MobileNet（数据已备好 YOLO 格式标签）。
3. 模型再训练只改 `tools/vision_w6.py` 的 C_GRID / 增广开关，导出后覆盖 `model_t4.json` 即生效，后端无感。

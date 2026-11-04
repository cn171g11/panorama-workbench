# 缺口审计批次入图（2026-11-05）

## 输入与审计

本批处理四组输入：

- `D:\Downloads\阜阳补.json`
- `D:\Downloads\六安补.json`
- `D:\Downloads\平凉.json`
- `D:\Downloads\11.4合集.zip`（解包目录 `D:\Downloads\scan_114_extract\`，31 个 JSON）

三份单文件与合集共 34 个 JSON，原始记录 55,053 条；按 sid 去重后为 55,033 条，输入内部重复额外 20 条，坏记录 0。输入中的 `isHidden` 字段没有作为结论依据。

使用 `tools/audit_gap_scan_mobility.mjs` 逐点请求腾讯 navigation-v1 `/sv` 接口，命令为并发 10、重试 3，按 13.4 点/秒安全速率运行。最终 55,033 条全部 settled：

| 审计分类 | 数量 |
|---|---:|
| 隐藏（不可移动、movementCount=0） | 54,426 |
| 常规（可移动） | 607 |
| 无效 | 0 |
| 错误 | 0 |

## 导入

使用 DataV GeoAtlas 官方 GCJ-02 地级边界分配归属，并对常规与隐藏集合分别处理。全局 sid 查重拦截 26 条已有记录（现有常规 24、现有隐藏 2），因此实际写入：

- 隐藏新增 54,424 条，写入 `hidden_<地级码>` 集合；
- 常规新增 583 条，写入 `qq_21`（377）、`qq_22`（5）、`qq_41`（201）；
- 无法归属 0 条。

导入器先 dry-run，再以完全相同参数正式执行；不采信输入包内 `data_meta.js`。

## 校验结果

- 索引重建：`entries=34,775,322`，耗时约 149 秒；
- 隐藏网格：195 个隐藏集合、220,837 点，检查通过；
- 显示模式：PASS；
- 全库 sid：34,775,322 条、34,775,322 个唯一 sid、重复 0；
- 保护范围：既有 `g*/index.html`、根 `index.html`、`tools/build_hidden_viewer_data.py` 与 `.workbuddy/` 未纳入本批提交。

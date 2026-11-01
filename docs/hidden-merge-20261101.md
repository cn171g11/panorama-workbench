# 隐藏街景图层并入常规（v3.0.0）

2026-11-01。用户决定：隐藏街景图层直接并入常规，不再单独区分；数据报告页保持不变。

## 1. 迁移

| 项 | 值 |
|---|---|
| 原 145 个 `hidden_*` 集合 | 109,429 点 |
| 按所属地级并入 `data_<adcode>` 分片 | **109,408** 点（139 个目标城市） |
| 城市图层已有、按 sid 去重 | 6 点 |
| 剑灵游戏街景（虚构坐标，无法落地理图层） | 15 点随层移除 |
| `hidden_pano.js` | 删除 |
| `PANO_COUNT` / `PANO_META` 的 `hidden_*` 键 | 全部清除 |

归属规则：集合键 `hidden_<adcode>` → `adcode[:4]+"00"`（与全库一致的区县→地级聚合；
`429004/429005/429006 → 429000`、`469006/469030 → 469000`、`659005/659008/659010 → 659000`）。
分片写入复用 `import_scan_result.write_city_parts`（180k 拆片 + 旧片清理），元数据复用
`load_meta / update_meta_file`。合并为并集：城市图层已有 sid 不重复写入。

## 2. 查看器与工具

- `city-viewer/index.html`：删除 `hidden_pano.js` 引用；`isHiddenEntry` 短路为 `false`，
  总览网格/详情不再区分隐藏与常规渲染（数据保留 `腾讯隐藏` 来源标记作溯源）。
- `tools/build_viewer_index.js`：`hidden_pano.js` 改为存在才加载/回写，缺失时跳过隐藏网格同步。
- `tools/check_viewer_hidden_grid.js`：改为守卫——断言 meta/grid/data 文件中**不得再出现**任何
  `hidden*` 集合，且 `hidden_pano.js` 保持删除。
- `report.html` 未改动（按约定）：隐藏列自此读不到 `hidden_*` 键，自然归零。

## 3. 结果

| 项 | 前 | 后 |
|---|---|---|
| 街景点总数 | 28,958,899 | **28,958,878**（−15 剑灵 −6 去重） |
| 数据分片 | 458 | **462**（139 城市中 4 个跨过 18 万点拆出新片） |
| 网格单元 | 590,435 | **524,718**（隐藏网格并入城市网格，同格合并） |
| 集合键 | 603（含 145 隐藏） | **462**（无隐藏） |

## 4. 校验

- `build_viewer_index.js`：`entries=28,958,878` 与 `PANO_COUNT` 相等；
- `check_viewer_hidden_grid.js`（新守卫）：462 个数据文件无任何 `hidden*` 集合；
- `check_viewer_display_mode.js`：PASS；
- python 6 项 + node 测试：通过。

## 5. 后续注意

导入工具链（`import_scan_result.py` / `import_map_export.py` / `import_gap_scan_batch.py`）
目前仍会把不可移动点写进 `hidden_*` 集合——在工具改为「并入城市图层」之前，
**不得直接跑这些导入器**（新守卫会拦截）。改造成后续版本任务。

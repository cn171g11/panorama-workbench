# 河北省常规街景区县包入图（2026-11-04）

## 来源

- `D:\Downloads\Hebei_data.zip`
- 100 个 `data_<区县 adcode>.js` 文件；只读取点位文件，未采信包内 `data_meta.js`。
- 原始点位 2,643,459 条，去重后 2,643,353 个 sid。

## 导入

使用 `tools/merge_county_scan.py` 按 `adcode[:4] + "00"` 合并到 11 个地级市层，采用并集策略，不覆盖已有数据。河北常规点从 56,527 增至 2,644,131，净新增 2,587,604。

包内点位与隐藏集合无 sid 重叠。包内 sid 与历史常规层有 56,259 个重叠，其中 55,750 个在河北既有市级层，按 sid 并集去重；跨省历史副本 509 个与包内点坐标一致，已从北京、天津、辽宁、河南的旧分片删除，河北记录保留。导入后另发现 1 个河北内部重复 sid（坐标 114.604, 38.558 属石家庄），从保定层删除并保留石家庄记录。

## 结果

- 总点数：32,133,221 → **34,720,315**
- 河北常规：56,527 → **2,644,131**
- 净新增：**2,587,094**（新增 2,587,604，清理跨省副本 509，清理河北内部重复 1）
- 隐藏街景：171 集合 / 166,413 点，不变
- 索引：`grid_keys=623`，`grid_cells=670,238`

## 验证

- `build_viewer_index.js`：通过，`entries=34,720,315`
- `check_viewer_hidden_grid.js`：通过，171 集合 / 166,413 点
- `check_viewer_display_mode.js`：PASS
- 全库 sid 审计：34,720,315 条、34,720,315 个唯一 sid、重复 0
- `python -m unittest discover -s tools/tests`：6 项通过

## 备注

工作区在导入前已有用户本地修改：`g101/index.html`、`g102/index.html`、`g103/index.html`、`g106/index.html`、`g312/index.html`、根 `index.html`、`tools/build_hidden_viewer_data.py` 以及 `.workbuddy/`；本批次不包含这些文件。

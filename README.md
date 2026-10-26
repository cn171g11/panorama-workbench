# 街景工作台 · Panorama Workbench

腾讯 / 百度街景**元数据**的采集、校验、整理与可视化。仓库只保存文本类元数据，不保存任何街景图片；
线上主体是一个可按需加载的全国街景查看器。

| 入口 | 地址 |
|---|---|
| 城市查看器 | <https://cn171g11.github.io/panorama-workbench/city-viewer/> |
| 数据报告 | <https://cn171g11.github.io/panorama-workbench/city-viewer/report.html>（各省市常规/隐藏街景数量） |
| 仓库根路径 | <https://cn171g11.github.io/panorama-workbench/>（自动跳转到查看器） |
| 结构说明 | [docs/repository-layout.md](docs/repository-layout.md) |
| 数据目录 | [docs/data-catalog.md](docs/data-catalog.md) |
| 运维手册 | [docs/operations.md](docs/operations.md) |

> 街景图片版权归腾讯 / 百度所有。本仓库仅收录元数据（panoid、坐标、路名、采集时间、朝向），仅供研究与个人使用。

---

## 1. 数据规模

| 指标 | 数值 |
|---|---|
| 街景点总数 | **16,301,085** |
| 数据分片 | 511 个 `data_*.js` |
| 省级行政区 | 33 个 |
| 区县边界 | 695 个（覆盖 81 个地级行政区） |
| 腾讯隐藏街景 / 时光机 | **61,760** 点（111 个地级行政区成集，另含剑灵游戏街景 15 点） |
| 腾讯常规街景（导入） | 6,482 点 |

点位最多的省级行政区：

| 省级行政区 | 街景点 |
|---|---|
| 江苏省 | 6,461,573 |
| 上海市 | 3,779,724 |
| 安徽省 | 1,752,973 |
| 福建省 | 1,721,722 |
| 广西壮族自治区 | 1,033,851 |
| 宁夏回族自治区 | 516,314 |
| 青海省 | 306,710 |
| 山东省 | 101,273 |

> 江苏、上海两地是早年网格扫描的主体，点数远高于其他省份；福建、安徽、广西、宁夏是近期按地级市全量重扫的结果。

---

## 1.1 数据报告 `report.html`

查看器顶部的「数据报告」按钮会打开 `report.html`：按**省级**和**地级**两级列出常规街景与隐藏街景数量，
支持搜索、按列排序、展开到城市，并给出隐藏占比。页面只读取 `data_meta.js`（48 KB），不加载点位数组，打开即出结果。

区县一级没有独立计数：数据按地级市存储，只有 81 个地级市带区县边界，无法拆出可靠的点数。

---

## 2. 数据组织

查看器按**地级行政区 adcode** 拆分数据，浏览器按需加载，单次只取当前城市的分片。

| 文件 | 作用 |
|---|---|
| `data_meta.js` | `PANO_META`（名称 / 省份 / 归属地级市）、`PANO_COUNT`（各分片点数） |
| `data_districts.js` | `PANO_DISTRICTS`，区县边界多边形，供区县筛选使用 |
| `data_<adcode>.js` | `PANO_CITY[key]` 点位数组，超过 18 万点拆分为 `<adcode>_2`、`_3`… |
| `grid_all.js` | 全国网格聚合（0.004°），供总览与密度模式使用 |
| `pano_search_index.js` | panoid / 路名 / 采集时间 / 坐标的按需搜索索引 |
| `hidden_pano.js` | 「腾讯隐藏街景/时光机」合集（独立集合，不按城市拆分） |

点位格式固定为 9 个字段，只允许在末尾追加新字段：

```text
[panoid, lng, lat, road, captured, dir, has_thumb, has_pano, source]
```

---

## 3. 腾讯隐藏街景 / 时光机（按地级市分集合）

合集收的是**无法在腾讯街景里连续移动**的孤立点位（多为历史影像帧、景区单帧），与常规覆盖区分开。
每个地级行政区一个集合键（`hidden_371300` 临沂、`hidden_340200` 芜湖…），
查看器顶部是**省份 → 地级市**两级下拉：先选省，城市下拉才会启用并列出该省有隐藏数据的城市，
选中即只看这个市的隐藏点位；确实无法归属的点（目前为 0）才留在 `hidden` 兜底集合。

省份/城市归属用 DataV GeoAtlas 的地级行政边界做**点在面内**判定（GCJ-02，与街景坐标同基准，无需投影转换）；
落在所有多边形外但距边界 120 km 内的点位（三沙岛礁、鸭绿江边）按最近行政区归属。

剑灵（Blade & Soul）游戏街景的坐标是虚构的，单独成集 `hidden_game`，在「腾讯游戏街景」分组下展示。

判定规则 `navigation-v1`（`tools/pano-mobility.js`）：实时请求 `sv.map.qq.com/sv?svid=&output=json`，
只有 `roads[].points` 的前后相邻帧、`vpoints[].link`、`all_scenes` 的相邻位才算「可移动」；
自引用、邻接为 `0,0`、坐标非法、元数据报错、`svid` 不匹配都不算。

- **能移动 = 常规街景，不得进入合集**；不能移动 = 隐藏街景。
- 剑灵（Blade & Soul）游戏街景在 `tools/data/tencent-game-exceptions.json` 登记为例外。
- 复核证据沉淀在 `tools/data/hidden-collection-verification.json`（51,685 条），
  `tools/purge_hidden_collection.py` 与导入工具默认读取它。

2026-10-24 曾据此清理过一批混入的常规街景（19,958 → 19,706），详见
[docs/hidden-cleanup-20261024.md](docs/hidden-cleanup-20261024.md)。

### 3.1 腾讯常规街景

导入的「隐藏街景」里往往混着可移动的常规点位。这类点位**不丢弃、也不放进隐藏合集**，
而是按省份单独成集（`qq_65` 新疆、`qq_37` 山东…，来源标记 `腾讯常规`），与隐藏合集并列展示。
行政区内缺区县边界数据时不做 adcode 拆分。

---

## 4. 采集与发布流程

1. **边界**：DataV GeoAtlas `areas_v3/bound/<adcode>.json`，缺失时回退锐多宝行政区划。
2. **种子**：边界内网格探测 `sv.map.qq.com/xf`（1–1.5 km 粗网格，密集区补 200 m 细网格）。
3. **扩散**：BFS 通过 `/sv` 的 `all_scenes` 扩展相邻场景，实时按边界过滤，支持断点续跑。
4. **缺口扫描**：对「整天没有记录、但前后一天有记录」的时间缺口逐日补扫，产出候选点位。
5. **移动性审计**：候选点逐条核验可移动性，只有不可移动的才允许进入隐藏合集。
6. **合并入图**：`tools/merge_gap_scan.py` / `tools/merge_city_scan.py` 写入分片并更新 `data_meta.js`。
7. **重建索引**：`node tools/build_viewer_index.js` 重算 `grid_all.js`、`pano_search_index.js` 与隐藏网格。
8. **校验发布**：`tools/check_viewer_hidden_grid.js`、`tools/check_viewer_display_mode.js` 通过后提交，
   GitHub Pages 自动构建。

版本号写在 `city-viewer/index.html` 标题里，每次发布递增；APK 通过 GitHub Release 分发（包名 `cn.cn171g11.panoviewer`）。

---

## 5. 工具

| 工具 | 用途 |
|---|---|
| `tools/build_viewer_index.js` | 重建 `grid_all.js` 与 `pano_search_index.js` |
| `tools/check_viewer_hidden_grid.js` | 校验隐藏合集条数、网格与实际加载顺序一致 |
| `tools/check_viewer_display_mode.js` | 校验散点 / 密度模式在缩放与大结果集下的行为 |
| `tools/merge_city_scan.py` | 市级扫描结果合并（自动分片、更新元数据） |
| `tools/merge_gap_scan.py` | 缺口扫描候选合并，内置移动性门禁 |
| `tools/hidden_collection_rules.py` | 隐藏合集保留 / 导入判定策略 |
| `tools/pano-mobility.js` | 移动性判定实现（`navigation-v1`） |
| `tools/purge_hidden_collection.py` | 按审计结果清理合集 |
| `tools/build_hidden_viewer_data.py` | 由历史合并清单重建 `hidden_pano.js` |
| `tools/city-scan/` | 早期城市扫描流水线（BFS、全景抓取、拼装） |

测试：`python -m unittest discover -s tools/tests`、`node --test tools/tests/pano-mobility.test.js`。

---

## 6. 暂存区 `staging/`

未发布、待处理的数据放这里，**不进入查看器、不参与构建**。

| 目录 | 内容 | 数量 | 状态 |
|---|---|---|---|
| `staging/baidu-xinjiang-20261025/` | 百度街景（新疆） | 12,986 | 未发布，等待后续计划 |

---

## 7. 区域扫描清单

`mohe/`、`erguna/`、`gaochun/`、`jgdaq/`、`tahe/`、`huma/`、`xinlin/` 保留各区域的清单与边界文件
（`*-panoramas.json`、`*-panoids.json|.txt`、`*-boundary.geojson`），用于复现早期扫描结果。

线路工作台 `g101/`、`g102/`、`g103/`、`g106/`、`g312/` 各自带 `index.html` 与线路 geojson / 分片 json。

---

## 8. 说明与免责

- 数据来自街景**非官方接口**，无 SLA，可能随时变更、限流或封禁。
- 仅采集元数据，未上传任何街景图片；图片版权归腾讯 / 百度所有，仅供研究用途。
- 百度（`baidu_pano`）与腾讯（`qq_pano`）数据来源、id 体系、坐标系不同，**不得混入同一集合**。
- 底图需自备 Key（天地图等）；GitHub Pages 无法隐藏浏览器端密钥，请使用限制 Origin 的 Key。
- 线路底图坐标随底图坐标系自动换算；OSM 仅作线路数据来源（ODbL）。

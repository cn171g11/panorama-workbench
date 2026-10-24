# 街景工作台 · Panorama Workbench

腾讯 / 百度街景元数据的采集、整理与可视化工作台。仓库包含可直接部署的静态查看器、路线工作台、已验证的元数据清单和采集工具。

- 在线入口: <https://cn171g11.github.io/panorama-workbench/>
- 城市查看器: <https://cn171g11.github.io/panorama-workbench/city-viewer/>
- 结构说明: [`docs/repository-layout.md`](docs/repository-layout.md)
- 运维说明: [`docs/operations.md`](docs/operations.md)

> 本仓库收录街景元数据, 不收录街景图片。图片版权归腾讯 / 百度所有, 内容仅供研究与个人使用。

---

## 1. 全国城市街景查看器 `city-viewer/`

在线：<https://cn171g11.github.io/panorama-workbench/city-viewer/>

- 覆盖多个省级行政区和地级行政区, 数据按 adcode 拆分并按需加载
- 当前规模: **15,430,655** 个街景点, 396 个数据分片（含福建、南京、徐州、溧水、广西、安徽等）
- 界面：Leaflet 全屏地图，省 → 地级市两级切换（不区分县级行政区）
- 底图：高德标准 / 高德暗色 / 高德影像 / 腾讯暗色
- 交互: 点位渲染、最近街景、panoid / 路名 / 采集时间 / 坐标搜索、城市和区县筛选、密度与散点模式
- panoid 定位: 支持 `@16-20:SCENE`、`@1-6:350830` 等按字符位置匹配的查询
- 小于 20,000 条结果强制散点, 大结果集允许密度优化或散点模式
- 全国视图底图最低 zoom 为 3, 兼容移动端瓦片服务
- 图例：**金色**＝含全景图，**青色**＝仅元数据
- 街景跳转：<https://qq-map.netlify.app/>

**数据组织**（按地级行政区 adcode 拆分，浏览器按需加载）：

- `data_meta.js` → `window.PANO_META`：每个键含 `name`、`province`、`pref`（所属地级行政区）
- `data_<adcode>.js` → `window.PANO_CITY[key]`：`[panoid, lng, lat, road, captured, dir, has_thumb, has_pano, source]`
- `index.html`：查看器本体；本地查看可运行 `start_viewer.bat`（起一个静态服务）

---

## 2. 城市 / 区域全量扫描数据

每个目录含 `*-panoramas.json`（全量清单）、`*-panoids.json|.txt`（panoid 列表）、`*-boundary.geojson`（边界）。

| 目录 | 区域 | adcode | 街景点 | 全景图 | 采集年 |
|---|---|---|---|---|---|
| `mohe/` | 黑龙江省 漠河市 | 232701 | 34,565 | 8,246 | 2013 |
| `erguna/` | 内蒙古 额尔古纳市 | 150784 | 29,213 | 8,832 | 2013 |
| `jgdaq/` | 黑龙江省 加格达奇区 | 232718 | 15,635 | 2,452 | 2013 |
| `tahe/` | 黑龙江省 塔河县 | 232722 | 9,508 | 1,464 | 2013 |
| `gaochun/` | 江苏省 南京市高淳区 | 320118 | 37,128 | 2,990 | 2014–2015 |
| `xinlin/` | 黑龙江省 新林区 | 232723 | 未完成（仅边界 + 探测种子） | — | — |
| `huma/` | 黑龙江省 呼玛县 | 232721 | 未扫描 | — | — |

> 大兴安岭四区县（漠河 / 加格达奇 / 塔河 / 呼玛）中，塔河经 18,615 点全域网格探测补扫出 5,059 个点，数据范围向外扩展约 90 公里——**首轮仅从县城种子做 BFS 会漏掉县域内互不连通的独立覆盖区**。新林区不在 DataV `232700_full` 列表中，边界改用[锐多宝行政区划](https://map.ruiduobao.com/)（adcode 232723）。

---

## 3. 线路工作台（国道 / 省道）

原有的 S341 工作台（根 `index.html`）、G212 兰龙线工作台和溧水区工作台已移除，根路径现在直接跳转到城市查看器。

| 入口 | 线路 | 说明 |
|---|---|---|
| `g101/`、`g102/`、`g103/`、`g106/`、`g312/` | G101 / G102 / G103 / G106 / G312 | 各自 `index.html` + `*-tencent-lines.geojson` + `*-tencent-panoramas-part-*.json` + `*-tencent-scan-report.json` |

---

## 4. 采集方法

1. **边界**：DataV GeoAtlas `areas_v3/bound/<adcode>.json`（缺失时回退锐多宝行政区划）
2. **种子**：边界内网格探测 `sv.map.qq.com/xf`（1–1.5 km 粗网格，密集区补 200 m 细网格）
3. **扩散**：BFS 通过 `/sv` 的 `all_scenes` 扩展相邻场景，实时按边界过滤，落盘可断点续跑
4. **缩略图 / 全景**：可选拉取 `sv1.map.qq.com/thumb|tile`（4096×2048）
5. **速率**：全局限流约 16 req/s（`MIN_INTERVAL=0.06`），失败自动退避
6. **缺口审计**：细网格全域探测复核，命中全部落在 BFS 结果内（`NEW_SVIDS=0`）即判定无漏扫

腾讯街景沿线路覆盖通常很稀疏（如 S341 约 2%，多为 2015 年影像），百度数据用于补足线路覆盖。

---

## 5. 工具

- `tools/city-scan/`：城市全量扫描流水线
  - `bfs.py`（短连边 BFS）、`panorama_batch.py`（全景/缩略图批量）、`thumbs.py`、`assemble.py`、`build_viewer_data.py`
- `tools/g212-scan.mjs`：命令行批量扫描（自读本地密钥文件，不打印密钥，仅记录 SHA256 指纹；`--route-only` 只刷新路线）

---

## 6. 说明与免责

- 数据来自腾讯街景**非官方接口**，无 SLA，可能随时变更、限流或封禁
- 仅收集**元数据**，未上传任何街景图片；图片版权归腾讯 / 百度，仅供研究用途
- 线路底图坐标会随底图坐标系自动换算；OSM 仅作线路数据来源（ODbL），导出结果应保留来源信息
- 天地图等底图需自备 API Key；GitHub Pages 无法隐藏浏览器端密钥，请使用允许当前 Origin 的 Key

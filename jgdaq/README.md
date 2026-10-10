# 加格达奇区腾讯街景全量扫描数据（2026-10-11）

- 扫描方式：从市区中心种子点出发，沿 `all_scenes` 相邻采集点 BFS 爬行，加格达奇区界多边形实时过滤
- 数据源：腾讯街景非官方接口（sv.map.qq.com /sv、sv1.map.qq.com /thumb /tile），GBK 解码
- 坐标过滤：阿里 DataV GeoAtlas `232718.json` 加格达奇区边界

| 指标 | 数值 |
|---|---|
| 街景点（panoid）总数 | 15635 |
| 道路/路段数 | 54 |
| 采集年代 | 2013（soso 时期） |
| 经度范围 | 124.00117 ~ 124.25650 |
| 纬度范围 | 50.36259 ~ 50.55675 |
| 审图号 | GS(2018)1865号（接口返回） |

## 文件

- `jgdaq-panoramas.json`：全量清单（panoid/坐标/朝向/道路/采集时间）
- `jgdaq-panoids.json|.txt`：纯 panoid 列表
- `jgdaq-boundary.geojson`：加格达奇区边界（adcode 232718）

## 说明

- 缩略图与高清全景图片体积过大（约 2.3GB），仅保留在本地数据目录，未上传本仓库
- `entrances` 字段已从清单剔除（会返回敏感地名），原始数据仅本地保留
- 可视化：根目录 `city-viewer/`，或直接跳转 <https://qq-map.netlify.app/>
- 非官方接口无 SLA，随时可能变更；影像版权归腾讯，商用需解决授权

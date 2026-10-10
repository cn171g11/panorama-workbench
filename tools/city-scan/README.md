# city-scan 城市街景全量扫描工具

对指定城市（县级市/区）做腾讯街景全量 BFS 扫描的流水线脚本。已用于漠河市（adcode 232701）与额尔古纳市（adcode 150784）。

## 流水线

1. **边界**：阿里 DataV GeoAtlas `https://geo.datav.aliyun.com/areas_v3/bound/<adcode>.json`（需带 Referer，部分非标准区划如呼中区/新林区不在该数据集中）
2. **种子发现**：`https://sv.map.qq.com/xf?x=<墨卡托x>&y=<墨卡托y>&r=<半径>&output=json` 按坐标找最近街景（墨卡托换算：x=lng*20037508.34/180, y=ln(tan((90+lat)*pi/360))*20037508.34/pi）
3. **BFS 爬行**（`bfs.py`）：从种子出发，`/sv` 的 `all_scenes` 展开相邻采集点，边界多边形实时过滤；并发 4、请求间隔 0.22s（约 18 req/s，安全区间 13-30 req/s）；失败率 >30% 自动暂停 300s（风控退避）；断点续传（state 文件）
4. **缩略图**（`thumbs.py`）：`sv1.map.qq.com/thumb` 全量下载（512x256）
5. **全景**（`panorama_batch.py`）：80m 网格采样后，4x8 瓦片（level0，每片 512px）拼接为 4096x2048；8 并发、0.05s 间隔（约 20 tiles/s）；断点续跑
6. **清单**（`assemble.py`）：生成 `<area>-panoramas.json`（panoid/坐标/朝向/道路/采集时间）与 panoids 列表、README

## 使用

各脚本头部 `BASE` 常量为本地数据目录，按目标城市修改；种子 svid 在 `bfs.py` 的 `SEEDS` 中替换。

## ⚠️ 风控与合规

- `sv.map.qq.com` 的 /sv /xf /rarp 接口在约 4300 次 50req/s 请求后会触发 IP 级 500 风控（约 29 分钟解封）；安全速率 13-30 req/s
- 图片集群（sv1-9.map.qq.com /tile /thumb）不受该风控影响
- 非官方接口：无文档/无 SLA；影像版权归腾讯，商用需解决授权
- `entrances` 字段会返回敏感地名，交付清单必须剔除

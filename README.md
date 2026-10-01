# S341 街景工作台

南京市溧水区 S341 百度/腾讯街景采集与可视化工作台。

在线地址：<https://cn171g11.github.io/s341-panorama-workbench/>

## 内容

- `index.html`：Leaflet 可视化工作台，支持百度/腾讯数据筛选、街景跳转、底图切换。
- `g212-panorama-workbench.html`：G212 国道扫描工作台，通过 FairwayMapper Overpass 获取路线，按间距查询腾讯街景并在地图展示。
- `g212-tencent-panoramas.json`：G212 沿线腾讯街景预扫描结果，40733 条记录（662 个采样命中 + 40071 个相邻场景，2026-10-01 采集），页面打开时自动载入。
- `tools/g212-scan.mjs`：命令行批量扫描脚本，自读本地密钥文件（不打印密钥，仅记录 SHA256 指纹），用法见文件头注释。
- `s341-baidu-panoramas.json`：1718 条百度街景记录。
- `s341-tencent-panoramas.json`：344 条腾讯街景记录，跳转至 <https://qq-map.netlify.app/>。

## 说明

腾讯街景沿 S341 的覆盖约为 2%，主要是 2015 年影像；百度数据用于补足线路覆盖。工作台默认使用腾讯/高德底图。天地图选项需要自行配置 API Key；OSM 仅作为线路数据来源，不作为成品底图。

## G212 扫描说明

打开 `g212-panorama-workbench.html` 后输入 FairwayMapper 的 `fm_...` API key。key 只保存在当前页面内存，仅随请求发送给 fairwaymapper.com 端点，不会写入源码、URL、localStorage 或导出文件。GitHub Pages 无法隐藏浏览器端 key，因此请使用允许当前 Origin 的 key，或把 Overpass 请求改为自有后端代理（非 fairwaymapper 端点不要求、也不会收到 key）。

页面通过 Overpass 联合查询（G212 路线关系成员 + 全国范围内 `ref=G212` 的路段）获取兰龙线（兰州—龙邦）全部几何，按配置间距采样后调用 `sv.map.qq.com/xf` 查找腾讯街景，再用 `/sv` 的 `all_scenes` 扩展相邻场景。默认采样 400 m、查询半径 250 m。

腾讯街景沿 G212 覆盖稀疏：已实测兰州、广元、南充、重庆市区存在街景簇，中途县城大多没有覆盖；未命中表示该处缺腾讯街景数据，而不是扫描失败。OSM 数据遵循 ODbL，导出结果应保留来源信息。

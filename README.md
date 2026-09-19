# S341 街景工作台

南京市溧水区 S341 百度/腾讯街景采集与可视化工作台。

在线地址：<https://cn171g11.github.io/s341-panorama-workbench/>

## 内容

- `index.html`：Leaflet 可视化工作台，支持百度/腾讯数据筛选、街景跳转、底图切换。
- `s341-baidu-panoramas.json`：1718 条百度街景记录。
- `s341-tencent-panoramas.json`：344 条腾讯街景记录，跳转至 <https://qq-map.netlify.app/>。

## 说明

腾讯街景沿 S341 的覆盖约为 2%，主要是 2015 年影像；百度数据用于补足线路覆盖。工作台默认使用腾讯/高德底图。天地图选项需要自行配置 API Key；OSM 仅作为线路数据来源，不作为成品底图。

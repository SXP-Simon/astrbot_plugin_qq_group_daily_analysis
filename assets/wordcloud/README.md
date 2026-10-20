# 词云资源来源

ATRI 词云使用群分析模板已有的图片和字体直链，本目录不附带字体或立绘副本。资源地址复用「模板渲染设置」中的 CDN 配置；已有 ATRI 镜像覆盖设置也继续生效。

## ATRI 立绘

以下图片直接引用[上游仓库](https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis)已有 ATRI 模板资源：

| 用途 | 上游原路径 |
| --- | --- |
| 左侧立绘 | `assets/ATRI/file/1775130626446_1774881312214_atri1.webp` |
| 右侧立绘 | `assets/ATRI/file/1775130623112_1774881319340_atri4.webp` |

图片相关权利归原权利人所有；本说明记录资源来源，不为图片授予额外许可。

## 字体

「霞鹜文楷」选项使用已有的 `assets/ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2` 直链。字体为 [霞鹜文楷（LXGW WenKai）](https://github.com/lxgw/LxgwWenKai)，基于 [Klee](https://github.com/fontworks-fonts/Klee)；字体许可和版权说明见其源项目。

用户也可以在词云编辑器中上传 WOFF2、WOFF、TTF、OTF 字体，上传文件保存在插件数据目录 `wordcloud_fonts/`，仅在渲染时内嵌，或选择系统无衬线/衬线字体。

## 加载与模板清单

快速预览与 T2I 会等待字体加载、立绘解码和排版完成，加载失败或超时会明确报错。浏览器和 T2I 服务都需要能访问所配置的 CDN；远端字体需要允许浏览器跨域加载。

`wordcloud_assets.json` 中以 `cdn:` 开头的值引用仓库 `assets/` 下的现有路径，例如 `cdn:ATRI/file/example.webp`。其他相对路径继续按原有本地模板资源规则解析，供自定义模板使用。

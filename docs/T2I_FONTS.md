# 自定义 T2I 的字体加载与安装

通常保持 **在线字体** 即可。只有「自定义 T2I 方案」提供「字体加载方式」，海外、内地方案继续沿用现有行为。

## 什么情况下需要调整

| 你的情况 | 建议 |
| --- | --- |
| 报告能正常生成，字体和排版也正常 | 保持在线字体，不需要调整 |
| 自建 T2I 已安装所用模板的字体，希望减少字体下载 | 可以选择使用已安装字体 |
| 已确认字体样式表下载经常超时，愿意接受备用字体的外观 | 可以临时尝试使用已安装字体 |
| 使用别人的 T2I，不清楚它安装了哪些字体 | 优先保持在线字体，或先联系服务提供者 |
| 标题、书法、手写效果必须接近模板原样 | 先安装所需字体，再切换；字体版本差异也可能影响外观 |
| 缺少的是初音装饰图、人格图片或头像 | 检查对应素材地址和网络；这个选项不处理图片下载 |

**“已安装”指实际运行截图浏览器的机器或容器。** 安装在打开 WebUI 的电脑、AstrBot 所在的其他容器或 T2I 宿主机上，不代表截图浏览器能够使用。

## 两种方式分别做什么

- **在线字体（默认）**：使用当前轮次的 Google Fonts、Gstatic 和模板自己的字体来源；现有方案缺少新字段时也保持这一行为。
- **使用已安装字体**：内置模板跳过网络字体样式表、字体预连接和远端字体文件，优先匹配已经安装的原字体，缺少时使用模板的备用字体。不会下载或安装字体，也不要求 T2I 服务提供额外接口。

选择已安装字体后，两端配置页会隐藏本轮暂不使用的 Google Fonts、Gstatic 输入框，但保留原值，切回在线字体时可以继续使用。模板资源 CDN 仍然生效，装饰图和人格图片照常加载。

这个设置只作用于该轮**图片报告**。独立导出的 HTML 报告继续使用在线字体，方便接收者在自己的浏览器里打开。第三方模板需要按[模板开发指南](REPORT_TEMPLATE_GUIDE.md#字体加载方式)适配；不支持该变量的自定义主题可能仍请求网络字体。

需要时可以配置两轮相同服务：第一轮在线字体，第二轮使用已安装字体，并给第二轮更大的优先级数值。只有第一轮渲染失败才尝试下一轮；成功出图但字体不理想，不会自动重试。

## 按模板安装，不必一开始装全套

下表列出模板主动使用的设计字体，不要求安装 `Microsoft YaHei`、`PingFang SC`、`Consolas` 等所有备用字体。

| 模板 | 对应字体 |
| --- | --- |
| simple | Noto Sans SC、Noto Sans TC |
| deepseek_maid | Noto Sans SC |
| HatsuneMiku | Noto Sans SC、Noto Sans TC、Noto Sans JP、Outfit、Share Tech Mono；英文报告另用 Inter |
| hack | Noto Sans SC、Noto Sans TC、Inter、JetBrains Mono |
| format | Noto Serif SC、Noto Serif TC、Inter |
| maria、art_nouveau | Noto Serif SC、Noto Serif TC、Cinzel、Cormorant Garamond、JetBrains Mono |
| retro_futurism | Noto Sans SC、Noto Sans TC、Oswald、JetBrains Mono |
| scrapbook | Noto Sans SC、Noto Sans TC、ZCOOL KuaiLe、Long Cang、Patrick Hand |
| spring_festival | Noto Serif SC、Noto Serif TC、Ma Shan Zheng、ZCOOL XiaoWei |
| ATRI | LXGW WenKai Regular、LXGW WenKai Medium、LXGW WenKai Mono Regular |
| BlueArchive | Blueaka 的常规与粗体；见下方的来源和名称说明 |

QQ 官方摘要卡使用自己的系统字体列表，不受这个选项控制。

## 完整字体清单与下载入口

Google Fonts 链接指向[官方字体仓库](https://github.com/google/fonts)中的对应目录。下载字体文件时，优先使用完整 TTF／OTF；如果提供可变 TTF，可以用覆盖表中所需字重的版本，斜体通常需要单独文件。不要只下载 CSS，也不要把网页按字符拆分的一个 WOFF2 文件当作完整中文字体。

| 字体家族 | 当前模板请求的字重／样式 | 下载入口 |
| --- | --- | --- |
| Noto Sans SC | 400、500、600、700 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/notosanssc) |
| Noto Sans TC | 400、500、700、800 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/notosanstc) |
| Noto Sans JP | 400、700 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/notosansjp) |
| Noto Serif SC | 400、500、600、700、900 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/notoserifsc) |
| Noto Serif TC | 400、500、600、700、900 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/notoseriftc) |
| Inter | 300、400、500、600、700、800 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/inter) |
| JetBrains Mono | 400、500、600、700 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/jetbrainsmono) |
| Cinzel | 600、700、800 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/cinzel) |
| Cormorant Garamond | 正体 500、600、700；斜体 500 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/cormorantgaramond) |
| Outfit | 400、600、800 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/outfit) |
| Share Tech Mono | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/sharetechmono) |
| Oswald | 400、600 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/oswald) |
| ZCOOL KuaiLe | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/zcoolkuaile) |
| Long Cang | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/longcang) |
| Patrick Hand | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/patrickhand) |
| Ma Shan Zheng | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/mashanzheng) |
| ZCOOL XiaoWei | 400 | [官方字体目录](https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei) |
| LXGW WenKai | Regular、Medium | [霞鹜文楷发布页](https://github.com/lxgw/LxgwWenKai/releases) |
| LXGW WenKai Mono | Regular | [霞鹜文楷发布页](https://github.com/lxgw/LxgwWenKai/releases) |
| Blueaka | 模板 CSS 映射到 400、700 | [当前网页字体来源](https://github.com/VanillaNahida/BA-Spark-Cursor/tree/main/fonts)；完整桌面字体包尚未核验，见下文 |

### 字体名称和特殊映射

安装时认字体内部名称，文件改名不会修改字体家族名。

- 部分系统包提供的是 `Noto Sans CJK SC`，模板使用的是 `Noto Sans SC`。它们可能互为备用，但不能据此认定原字体已经匹配。需要尽量保持原设计时，安装上表链接中的对应家族。
- ATRI 使用 `LXGWWenKai-Regular.ttf`、`LXGWWenKai-Medium.ttf` 和 `LXGWWenKaiMono-Regular.ttf`。模板保留本地映射：`LXGW WenKai`／`LXGWWenKai-Regular` 对应 400，`LXGW WenKai Medium`／`LXGWWenKai-Medium` 对应原模板的 600，`LXGW WenKai Mono`／`LXGWWenKaiMono-Regular` 对应 400。Medium 文件自身的字重与模板声明可能不同，保留映射可继续使用该文件。
- BlueArchive 的上游 CSS 将 `BlueakaBeta2GBK DemiBold` 映射到 `Blueaka` 400，将 `BlueakaBeta2GBK` 映射到 700。本地模式保留这些名称及 `Blueaka`／`Blueaka Bold` 候选。当前来源主要是分片网页字体，**尚未核验完整、可直接安装的桌面字体包**，请向字体提供者确认完整文件和使用许可。没有对应字体而又希望保留原设计时，继续使用在线字体；接受备用字体时才尝试本地模式。

插件不附带字体安装包，也不自动安装这些字体。

## Docker／Podman 部署

1. 确认哪个容器实际运行 T2I 浏览器。使用插件式 T2I 且浏览器运行在 AstrBot 容器内时，字体应安装到那个容器。
2. 在宿主机准备 `fonts` 目录，放入所需完整字体文件，保留下载包中的许可文件。
3. 将目录挂载到 T2I 容器的字体目录。常见 Fontconfig 环境可以使用下面的 Compose 配置片段；服务名和原有配置请按实际部署调整：

   ```yaml
   services:
     t2i:
       volumes:
         - ./fonts:/usr/local/share/fonts/daily-analysis:ro
   ```

4. 在容器内更新缓存，然后重启 T2I 服务，让新的浏览器进程读取字体：

   ```sh
   # 使用 Podman 时，将 docker 替换为 podman。
   docker exec <T2I容器名> fc-cache -f
   docker restart <T2I容器名>
   ```

如果镜像中没有 `fc-cache`，先确认镜像使用的字体系统；Debian／Ubuntu 和 Alpine 常见镜像可以安装 `fontconfig`。建议将字体和缓存更新步骤写入自己的镜像构建过程，或使用持久化挂载；只临时复制到容器可写层，重建容器后会丢失。

只安装中文基础字体时，Debian／Ubuntu 的 `fonts-noto-cjk` 可以改善缺字，但不包含上表全部设计字体。基础中文包可读，不代表标题、手写和书法效果已经恢复。

## Linux 原生部署

使用运行 T2I 的账号安装字体。以下是常见 Fontconfig 环境的用户级安装方式：

```sh
mkdir -p ~/.local/share/fonts/daily-analysis
# 将下载的完整 TTF／OTF 文件放到上述目录。
fc-cache -f
fc-list : family
fc-match 'LXGW WenKai'
```

需要给多个运行账号使用时，可以安装到 `/usr/local/share/fonts/daily-analysis`，更新缓存并确认服务账号有读取权限。之后重启 T2I 服务或其浏览器进程。目录和工具说明可参考 [Fontconfig 文档](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html)及 [Debian 字体指南](https://wiki.debian.org/Fonts/)。

**`fc-match` 成功退出不代表目标字体存在**：它也会返回最接近的替代字体。请查看输出的实际家族名，并结合 `fc-list` 确认。检查命令必须在浏览器真正运行的容器、机器和账号环境中执行。

## Windows 原生部署

从字体提供者下载完整字体包，解压后安装 TTF／OTF。T2I 作为服务或使用其他账号运行时，优先选择「为所有用户安装」，并确认服务账号可见；只给当前登录账号安装可能不生效。安装后重启 T2I 服务或浏览器进程。

Windows 主机上安装字体，不会自动安装到 Linux Docker／Podman 容器中。容器部署仍按上面的挂载方式处理。

## macOS 原生部署

使用「字体册」安装下载的完整字体，确认运行 T2I 的账号可以使用，然后重启服务或浏览器。若 T2I 实际运行在容器内，请仍按容器方式安装。

## 如何确认设置有效

1. 先确认安装环境和字体名称正确，再将自定义方案改为「使用已安装字体」并保存。
2. 「测试渲染」只验证地址、Token 和基本出图能力，使用简单系统字体，不会检查上表字体是否齐全。
3. 在报告历史中选择实际模板重绘，检查中文、标题、西文、数字、粗体和斜体；只看正文宽度不能确认匹配成功。
4. 具备浏览器调试条件时，检查实际渲染字体与网络请求，确认没有继续请求字体 CSS 或远端字体文件。仅使用 `document.fonts.check()` 也不足以证明没有回退。
5. 字体不合适时切回在线字体，原先的地址仍然保留。若仍是图片素材缺失，继续排查 CDN，不必反复切换字体模式。

字体安装齐全也不保证跨浏览器、跨字体版本逐像素一致。这个功能提供的是减少网络字体依赖的选择，不会自动修复截图服务、字体文件或图片 CDN。

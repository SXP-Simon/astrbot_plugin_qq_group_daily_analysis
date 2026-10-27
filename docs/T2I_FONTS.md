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

**“已安装”指实际运行T2I浏览器的机器或容器。** 安装在打开 WebUI 的电脑、AstrBot 所在的其他容器或 T2I 宿主机上，不代表T2I浏览器能够使用。

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

## 按模板批量下载字体

操作顺序是：**先下载字体，再安装到 T2I 的运行环境，检查成功后，最后切换插件配置。** 插件里选择「使用已安装字体」只改变加载方式，不会执行下面的下载或安装命令。

下面的示例只需要 Python 3.8 或更新版本，不需要 `pip install`。它按模板下载完整 TTF／OTF 和对应许可文件，字体放到当前目录的 `fonts` 子目录中；默认下载初音模板需要的字体，含英文报告使用的 Inter 正体和斜体文件。文件按字体家族分目录保存，可以直接用于后面的容器挂载。

将下列代码保存为 `download_t2i_fonts.py`。如果使用 Compose，建议把脚本放在 `compose.yaml` 所在目录，并在该目录执行。

<details>
<summary>展开下载脚本（复制到 download_t2i_fonts.py）</summary>

```python
import json
import os
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

TEMPLATES = {
    "simple": "notosanssc notosanstc",
    "deepseek_maid": "notosanssc",
    "HatsuneMiku": "notosanssc notosanstc notosansjp outfit sharetechmono inter",
    "hack": "notosanssc notosanstc inter jetbrainsmono",
    "format": "notoserifsc notoseriftc inter",
    "maria": "notoserifsc notoseriftc cinzel cormorantgaramond jetbrainsmono",
    "art_nouveau": "notoserifsc notoseriftc cinzel cormorantgaramond jetbrainsmono",
    "retro_futurism": "notosanssc notosanstc oswald jetbrainsmono",
    "scrapbook": "notosanssc notosanstc zcoolkuaile longcang patrickhand",
    "spring_festival": "notoserifsc notoseriftc mashanzheng zcoolxiaowei",
    "ATRI": "lxgw",
}
selected = os.environ.get("FONT_TEMPLATES", "HatsuneMiku").replace(",", " ").split()
if not selected or any(name not in TEMPLATES and name != "all" for name in selected):
    raise SystemExit("请填写表中的模板目录名或 all；BlueArchive 暂无已核验的完整安装包。")
if "all" in selected:
    selected = list(TEMPLATES)
families = sorted({family for name in selected for family in TEMPLATES[name].split()})
output = Path(os.environ.get("FONT_DIR", "fonts")).expanduser().resolve()
headers = {"User-Agent": "AstrBot-T2I-Font-Download"}


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with urlopen(Request(url, headers=headers), timeout=120) as response:
            prefix = response.read(4)
            if target.suffix.lower() in (".ttf", ".otf") and prefix not in (
                b"\x00\x01\x00\x00", b"OTTO", b"ttcf"
            ):
                raise ValueError("返回内容不是字体文件")
            with partial.open("wb") as file:
                file.write(prefix)
                shutil.copyfileobj(response, file)
        partial.replace(target)
        print("已下载：", target, flush=True)
    finally:
        partial.unlink(missing_ok=True)


for family in families:
    if family == "lxgw":
        base = "https://raw.githubusercontent.com/lxgw/LxgwWenKai/main/"
        for name in ("LXGWWenKai-Regular.ttf", "LXGWWenKai-Medium.ttf",
                     "LXGWWenKaiMono-Regular.ttf"):
            download(base + "fonts/TTF/" + name, output / family / name)
        download(base + "OFL.txt", output / family / "OFL.txt")
        continue
    api = f"https://api.github.com/repos/google/fonts/contents/ofl/{family}?ref=main"
    with urlopen(Request(api, headers=headers), timeout=30) as response:
        entries = json.load(response)
    files = [item for item in entries if item["type"] == "file" and (
        item["name"].lower().endswith((".ttf", ".otf")) or item["name"] == "OFL.txt"
    )]
    if not any(item["name"].lower().endswith((".ttf", ".otf")) for item in files):
        raise SystemExit(f"没有找到 {family} 的字体文件，请按上表手动下载。")
    for item in files:
        download(item["download_url"], output / family / item["name"])
print("下载完成。请继续安装到 T2I 环境：", output)
```

</details>

Linux／macOS 终端示例：

```sh
# 默认初音模板；改成 ATRI、scrapbook 等表中的目录名即可。
FONT_TEMPLATES=HatsuneMiku python3 download_t2i_fonts.py

# 同时使用多个模板时，用空格分隔；这是一种替代上面命令的选择。
FONT_TEMPLATES="ATRI scrapbook" python3 download_t2i_fonts.py

# 需要全部已核验字体时使用 all；包含较大的中文字体，不包含 Blueaka。
FONT_TEMPLATES=all python3 download_t2i_fonts.py
```

Windows PowerShell 中这样选择模板并运行：

```powershell
$env:FONT_TEMPLATES = "HatsuneMiku" # 也可以填 "ATRI scrapbook" 或 "all"
py -3 download_t2i_fonts.py
```

如果系统使用 `python` 而不是 `python3`／`py -3`，将命令中的解释器名称替换即可。重复执行会重新下载所选字体；下载失败会报错，不会把 `.part` 临时文件当作已完成字体。GitHub API 返回 HTTP 403 时也可能是匿名请求额度用尽，可稍后重试或手动下载。可以重新执行，也可以使用上表的链接手动下载。

**下载需要能访问 `api.github.com` 和 `raw.githubusercontent.com`。** 这里的下载地址独立于插件中的 CDN、Google Fonts 和 Gstatic 设置；脚本不会读取或修改插件配置。网络不通时，可以在另一台电脑下载后，将整个 `fonts` 目录传到部署机器，再继续安装。不要把字体 CSS 地址或 T2I 接口地址填进下载脚本。

## Docker／Podman 部署

先确认哪个容器实际运行 T2I 浏览器。使用插件式 T2I 且浏览器运行在 AstrBot 容器内时，下面的挂载和检查都应作用于 AstrBot 容器。

### 使用 Compose 的推荐步骤

1. 在 `compose.yaml` 所在目录完成上面的下载，确认该目录下已有 `fonts` 文件夹。目录可以包含按字体家族划分的子目录，Fontconfig 会继续扫描其中的字体。
2. 将下面的 `volumes` 条目合并到**已有的T2I服务**，保留服务原有的镜像、端口、数据挂载等配置。这里 `t2i` 是 Compose 服务名的示例，请替换成自己的服务名：

   ```yaml
   services:
     t2i:
       volumes:
         - ./fonts:/usr/local/share/fonts/daily-analysis:ro
   ```

3. 在 `compose.yaml` 所在目录执行以下命令。先检查合并后的配置，再让 Compose 应用挂载设置：

   ```sh
   docker compose config
   docker compose config --services
   docker compose up -d --no-deps t2i
   docker compose exec t2i fc-cache -f
   docker compose exec t2i fc-list : family
   docker compose exec t2i fc-match 'Outfit'
   docker compose restart t2i
   ```

Linux／macOS 宿主机上的字体目录若限制了其他账号读取，可先在下载目录执行 `chmod -R a+rX ./fonts`；字体文件只需读取权限。

`fc-match` 的示例与默认下载的初音模板一致；ATRI 可以改成 `fc-match 'LXGW WenKai'`，其他模板按字体清单替换。`config --services` 可查看实际服务名，后面的命令需将 `t2i` 替换为该名称。检查输出的实际字体名，不要只看命令是否成功退出。检查完成后，再按文末步骤切换插件设置。

**首次新增或更改挂载后，需要执行 `compose up` 应用配置；仅执行 `restart` 不会给旧容器增加新的挂载。** 如果以后只向已有挂载目录添加字体文件，则更新字体缓存、重启服务即可。Compose 应用配置可能重建目标服务，应先确认原有数据已有持久化挂载。[Compose 官方说明](https://docs.docker.com/reference/cli/docker/compose/up/)

使用 Podman 时，如果已安装 Compose provider，可以将上述 `docker compose` 替换为 `podman compose`。Windows 的 Docker Desktop／Podman 同样可以挂载目录；请在 Compose 文件所在目录准备 `fonts`，并确认引擎可以读取该目录。

### 没有 Fontconfig 命令时

先在容器内查看 `/etc/os-release`，按镜像类型选择一种安装方式。安装软件包通常需要容器内的 root 权限；如果镜像使用普通用户，可通过 `docker compose exec -u 0 t2i ...` 执行安装，装好后再以原服务账号检查字体。

```sh
docker compose exec t2i cat /etc/os-release

# Debian／Ubuntu 镜像
docker compose exec -u 0 t2i sh -c 'apt-get update && apt-get install -y --no-install-recommends fontconfig'

# Alpine 镜像；不要和上面的 Debian 命令一起执行
docker compose exec -u 0 t2i apk add --no-cache fontconfig
```

软件包只装进容器可写层时，重建容器后需要重新安装。长期使用建议基于原 T2I 镜像构建自己的镜像；下面仅为 Debian／Ubuntu 基础镜像的示例，将 `FROM` 替换为自己当前使用的镜像：

```dockerfile
FROM your-current-t2i-image:tag
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig \
    && rm -rf /var/lib/apt/lists/*
# 如果原镜像用普通账号运行，在这里用 USER 恢复原来的账号。
```

字体本身继续使用挂载目录，无需复制进插件或 AstrBot 源码目录。原镜像已有 Fontconfig 时，直接使用上面的挂载步骤即可。

### 没有使用 Compose 时

使用 `docker run`／`podman run` 部署的服务，需要在原来的创建命令中追加字体目录挂载，并按原配置重新创建目标容器。以 Linux／macOS 终端为例，在原命令中加入：

```sh
--mount "type=bind,src=$(pwd)/fonts,dst=/usr/local/share/fonts/daily-analysis,readonly"
```

不要只运行这一行，也不要丢掉原来的端口、环境变量和数据挂载。容器创建完成后，可用 `docker exec <实际容器名> fc-cache -f`、`docker exec <实际容器名> fc-list : family` 检查，再重启该容器。这里填写的是实际容器名，与 Compose 步骤使用的服务名有所不同。

只安装中文基础字体时，Debian／Ubuntu 的 `fonts-noto-cjk` 可以改善缺字，但不包含上表全部设计字体。基础中文包可读，不代表标题、手写和书法效果已经恢复。

## Linux 原生部署

先按上面的命令下载到当前目录的 `fonts`，再使用运行 T2I 的账号安装。Debian／Ubuntu 系统缺少工具时先执行 `sudo apt-get update && sudo apt-get install -y fontconfig`；Alpine 使用 `sudo apk add --no-cache fontconfig`。

以下是常见 Fontconfig 环境的用户级安装方式，在下载目录执行：

```sh
mkdir -p ~/.local/share/fonts/daily-analysis
cp -R ./fonts/. ~/.local/share/fonts/daily-analysis/
fc-cache -f
fc-list : family
fc-match 'Outfit'
```

需要给多个运行账号或系统服务使用时，可以改为系统级安装：

```sh
sudo mkdir -p /usr/local/share/fonts/daily-analysis
sudo cp -R ./fonts/. /usr/local/share/fonts/daily-analysis/
sudo fc-cache -f
```

确认服务账号有目录和文件的读取权限。之后重启实际的 T2I 服务或其浏览器进程；如果使用 systemd，可以执行 `sudo systemctl restart <你的T2I服务单元名>`，不要把示例占位符直接照抄。目录和工具说明可参考 [Fontconfig 文档](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html)及 [Debian 字体指南](https://wiki.debian.org/Fonts/)。

**`fc-match` 成功退出不代表目标字体存在**：它也会返回最接近的替代字体。请查看输出的实际家族名，并结合 `fc-list` 确认。检查命令必须在浏览器真正运行的容器、机器和账号环境中执行。

## Windows 原生部署

从字体提供者下载完整字体包，解压后安装 TTF／OTF。T2I 作为服务或使用其他账号运行时，优先选择「为所有用户安装」，并确认服务账号可见；只给当前登录账号安装可能不生效。安装后重启 T2I 服务或浏览器进程。

Windows 主机上安装字体，不会自动安装到 Linux Docker／Podman 容器中。容器部署仍按上面的挂载方式处理。

## macOS 原生部署

使用「字体册」安装下载的完整字体，确认运行 T2I 的账号可以使用，然后重启服务或浏览器。若 T2I 实际运行在容器内，请仍按容器方式安装。

## 如何确认设置有效

1. 先确认安装环境和字体名称正确，在插件配置中找到「图片渲染策略 → 图片渲染方案」。添加或展开「自定义 T2I 方案」，确认服务地址指向刚安装字体的服务，将「字体加载方式」改为「使用已安装字体」并保存。只保存这一项不会自动安装字体。
2. 「测试渲染」只验证地址、Token 和基本出图能力，使用简单系统字体，不会检查上表字体是否齐全。
3. 在报告历史中选择实际模板重绘，检查中文、标题、西文、数字、粗体和斜体；只看正文宽度不能确认匹配成功。
4. 具备浏览器调试条件时，检查实际渲染字体与网络请求，确认没有继续请求字体 CSS 或远端字体文件。仅使用 `document.fonts.check()` 也不足以证明没有回退。
5. 字体不合适时切回在线字体，原先的地址仍然保留。若仍是图片素材缺失，继续排查 CDN，不必反复切换字体模式。

字体安装齐全也不保证跨浏览器、跨字体版本逐像素一致。这个功能提供的是减少网络字体依赖的选择，不会自动修复T2I服务、字体文件或图片 CDN。

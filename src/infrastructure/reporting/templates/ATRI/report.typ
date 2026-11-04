// 以原版 940px 海报为基准缩放，字体与装饰从插件数据目录本地化。
#import "atri.typ": render
#let d=json("data.json")
#render(d,(u:.5pt))

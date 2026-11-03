// 与 HTML 并列的蓝白值班日志，按同一份 940px 海报缩放。
#import "maid.typ": render
#let d=json("data.json")
#render(d,(u:.5pt))

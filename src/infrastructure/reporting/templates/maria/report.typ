// 按原版莉莉安公报的独立布局排版，输出宽度仅缩放同一份海报。
#import "maria.typ": render
#let d=json("data.json")
#render(d,(u:72/d.ppi*d.width/940*1pt))

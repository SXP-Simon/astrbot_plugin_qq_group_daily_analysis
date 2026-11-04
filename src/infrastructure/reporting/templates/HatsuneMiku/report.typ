// 图片宽度缩放同一份长图版式，避免字号和固定宽度卡片相互挤压。
#import "miku.typ": render
#let d = json("data.json")
#let t = (u: .5pt)
#render(d,t)

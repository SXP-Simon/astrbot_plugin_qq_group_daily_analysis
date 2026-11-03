// simple 原生排版；复用展示组件，主题布局独立定义。
#import "simple.typ": render
#let d = json("data.json")
#let t = (accent: rgb("333333"), soft: rgb("f5f5f5"), border: rgb("dddddd"), u: .5pt)
#render(d,t)

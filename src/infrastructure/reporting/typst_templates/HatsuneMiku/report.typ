// HatsuneMiku 原生排版；复用展示组件，主题布局独立定义。
#import "miku.typ": render
#let d = json("data.json")
#let t = (bg: rgb("f0fafa"), paper: rgb("ffffff"), card: rgb("ffffff"), ink: rgb("2c3e50"), muted: rgb("7f8c8d"), accent: rgb("39c5bb"), secondary: rgb("a7e7e3"), soft: rgb("e0f2f1"), border: rgb("d2eeeb"), radius: 12, pattern: "grid", u: 72/d.ppi*1pt)
#render(d,t)

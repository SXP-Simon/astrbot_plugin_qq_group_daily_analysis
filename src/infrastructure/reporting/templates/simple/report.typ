// simple 原生排版；复用展示组件，主题布局独立定义。
#import "simple.typ": render
#let d = json("data.json")
#let t = (bg: rgb("ffffff"), paper: rgb("ffffff"), card: rgb("ffffff"), ink: rgb("222222"), muted: rgb("777777"), accent: rgb("333333"), secondary: rgb("999999"), soft: rgb("f5f5f5"), border: rgb("dddddd"), radius: 3, pattern: "none", u: 72/d.ppi*1pt)
#render(d,t)

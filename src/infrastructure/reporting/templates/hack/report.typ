// 终端主题保留黑橙配色、非等宽双栏及两侧各自的阅读顺序。
#import "hack.typ": render
#let d = json("data.json")
#render(d, (u: 72/d.ppi*d.width/940*1pt))

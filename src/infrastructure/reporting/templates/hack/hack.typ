#import "common.typ": shadow
#let orange = rgb("ff9900")
#let blue = rgb("3399ff")
#let secondary = rgb("cccccc")
#let border = rgb("2a2a2a")

#let copy(t, body, size: 18, weight: 400, fill: white, lh: 1.448, mono: false, italic: false) = {
  set par(leading: 0pt, spacing: 0pt)
  let baseline = if mono {0.86} else {0.86377}
  let edge = (lh - 1)/2
  let rendered = text(font: if mono {t.mono} else {t.fonts}, size: size*t.u, weight: weight, fill: fill,
    top-edge: (baseline+edge)*1em, bottom-edge: -(1-baseline+edge)*1em)[#body]
  if italic {
    // 按字形或西文词段合成斜体，避免长金句的首行随整段高度向右偏移。
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*|[\\p{Latin}\\p{N}]+|[\"'.,:;!?()\\[\\]{}-]"): it=>box(height:lh*size*t.u,baseline:(at:top,shift:-(baseline+edge)*size*t.u))[#skew(ax:-12deg,origin:bottom+left,it)]
    rendered
  }else{rendered}
}
#let rich(t, parts) = {
  for part in parts {
    if part.avatar != "" {
      h(2*t.u)
      box(inset: (left: 3*t.u, right: 7*t.u, y: 3*t.u), radius: 12*t.u,
        fill: black.transparentize(95%), stroke: 1*t.u+black.transparentize(90%), baseline: (at: bottom, shift: 7*t.u))[
        #set text(top-edge: 0.85em, bottom-edge: -0.15em)
        #box(width: 18*t.u, height: 18*t.u, radius: 50%, clip: true, baseline: 25%)[#image(part.avatar, width: 100%, height: 100%, fit: "cover")]
        #if part.text != "" {h(4*t.u); text(size: 0.85em, weight: 500, part.text)}
      ]
      h(2*t.u)
    } else {
      for (i, line) in part.text.split("\n").enumerate() {if i>0 {linebreak()}; line}
    }
  }
}
#let section(t, label) = {
  copy(t, [#text(fill: orange, weight: 700, "$")#h(10*t.u)#label], size: 17.6, fill: secondary, mono: true, lh: 23/17.6)
  v(25*t.u)
}
#let face(t, path, size: 50, round: false) = box(width: size*t.u, height: size*t.u,
  radius: if round {50%} else {8*t.u}, stroke: 1*t.u+rgb("333333"), clip: true, fill: rgb("222222"))[
  #if path != "" {image(path, width: 100%, height: 100%, fit: "cover")} else {
    align(center+horizon, copy(t, if round {"ID"}else{"ID_REF"}, size: 10, fill: rgb("444444"), mono: true, lh: 1.32))
  }
]
#let navigation(t) = {
  let item(body, active: false) = box(inset: (x: 13*t.u, y: 7*t.u), radius: 4*t.u,
    stroke: 1*t.u+if active {orange.transparentize(80%)} else {white.transparentize(100%)},
    fill: if active {orange.transparentize(95%)} else {none})[
    #copy(t, body, size: 13.6, fill: if active {orange} else {secondary}, mono: true, lh: 19/13.6)
  ]
  grid(columns: (auto, auto, 1fr, auto, auto, auto, auto, 50*t.u), gutter: 20*t.u, align: horizon,
    item("● ready", active: true), item("~/analysis"), [], item("$ ai --summary"), item("$ cd /groups"),
    item("$ api --status"), item([#box(width: 14*t.u, height: 14*t.u, baseline: 25%)[#image("globe.svg", width: 100%, height: 100%)] EN]),
    box(width: 50*t.u, height: 25*t.u, radius: 50%, stroke: 1*t.u+rgb("333333")))
  v(40*t.u)
}
#let hero(t, d) = {
  copy(t, "// main.ts", fill: secondary, lh: 21/18)
  copy(t, [> Group#h(1fr)#linebreak()Activity#h(1fr)#linebreak()Insights#h(5*t.u)#box(width: 15*t.u, height: 78.96*t.u, baseline: 25%, fill: white)#h(1fr)],
    size: 65.8, weight: 900, lh: 0.9, fill: gradient.linear((white, 0%), (white, 60%), (orange, 100%), angle: 45deg, relative: "parent"))
  v(25*t.u)
  copy(t, [#text("//") Report for #d.date], fill: secondary, lh: 26/18)
  v(30*t.u)
  block(width: 100%, fill: rgb("141414").transparentize(20%), stroke: 1*t.u+orange.transparentize(85%),
    outset: -0.5*t.u, radius: 12*t.u, inset: 31*t.u)[
    #copy(t, [#text(fill: rgb("ff3366"))[const] stats = {#linebreak()
      #h(1.2em)messages: #text(fill: orange)[#d.message_count],#linebreak()
      #h(1.2em)active_users: #text(fill: orange)[#d.participant_count],#linebreak()
      #h(1.2em)peak_time: #text(fill: blue)['#d.peak']#linebreak()
      };#linebreak()
      #text(fill: orange)[#text("//") Total characters: #d.characters]], mono: true, lh: 1.6)
  ]
}
#let quality(t, d) = {
  if d.review == none {return}
  v(40*t.u)
  section(t, "analyze --quality")
  v(21*t.u)
  let r = d.review
  let colors = (orange, rgb("e68a00"), rgb("cc7a00"), rgb("b36b00"), rgb("995c00"), rgb("804d00"))
  let dims = r.dimensions.filter(x => x.percentage>0)
  shadow(t, radius: 0, dy: 0, blur: 15, color: orange.transparentize(80%),
    block(width: 100%, fill: black, stroke: 2*t.u+orange, outset: -1*t.u, inset: 22*t.u)[
    #block(width: 100%, inset: (bottom: 11*t.u), stroke: (bottom: 1*t.u+orange))[
      #grid(columns: (1fr, auto), gutter: 12*t.u, align: bottom,
        copy(t, [> #r.title], size: 25.2, weight: 700, fill: orange, mono: true, lh: 33/25.2),
        copy(t, [\# #r.subtitle], size: 15.3, fill: rgb("e68a00"), mono: true, lh: 20/15.3))
    ]
    #v(20*t.u)
    #block(width:100%,height:30*t.u,inset:1*t.u,stroke:1*t.u+orange,outset:-0.5*t.u,fill:rgb("0d0800"),clip:true)[
      #if dims.len()>0 {grid(columns: dims.map(x => x.percentage*1fr),
      ..dims.enumerate().map(((i, x)) => block(width: 100%, height: 28*t.u, fill: colors.at(calc.rem(i, 6)),
        clip: true, inset: (x: 4*t.u), stroke: (right:1*t.u+orange))[
        #align(center+horizon, copy(t, x.name, size: 14.4, weight: 700, fill: if i < 2 {black} else {white}, mono: true, lh: 1))
      ]))}
    ]
    #v(20*t.u)
    #grid(columns: (1fr, 1fr), gutter: 15*t.u, ..dims.map(x => grid.cell(inset: 11*t.u,
      fill: rgb("281400").transparentize(50%), stroke: (paint: orange, thickness: 1*t.u, dash: "dotted"))[
      #copy(t, [:: #x.name], size: 13.77, weight: 700, mono: true, lh: 18/13.77)#v(5*t.u)
      #copy(t, [\>> #(str(x.percentage))%], size: 12.96, fill: orange.transparentize(20%), mono: true, lh: 16/12.96)#v(5*t.u)
      #copy(t, rich(t, x.comment), size: 16.2, fill: orange, mono: true, lh: 21/16.2)
    ]))
    #v(20*t.u)
    #block(width: 100%, inset: (top: 16*t.u), stroke: (top: 1*t.u+orange))[
      #copy(t, [#box(inset: (bottom: 4*t.u))[#box(fill: rgb("cc7a00"), inset: (x: 6*t.u, y: 2*t.u))[#text(weight: 700, fill: white)[[SYSTEM_SUMMARY]]]]#h(8*t.u)#rich(t, r.summary)], fill: orange, mono: true, lh: 1.5)
    ]
  ])
  v(25*t.u)
}
#let topics(t, d) = {
  if d.topics.len() == 0 {return}
  v(40*t.u)
  section(t, "ls ./topics")
  v(45*t.u)
  for (i, x) in d.topics.enumerate() {
    block(width: 100%, fill: white.transparentize(98%), inset: (left: 23*t.u, rest: 20*t.u),
      stroke: (left: 3*t.u+orange), outset: (left: -1.5*t.u))[
      #copy(t, x.title, size: 24, weight: 700, fill: orange)#v(12*t.u)
      #copy(t, [#text("/* Participants: ")#rich(t, x.contributors)#text(" */")], fill: secondary)#v(15*t.u)
      #copy(t, rich(t, x.detail), fill: white.transparentize(10%), lh: 1.6)
    ]
    if i < d.topics.len() - 1 {v(24*t.u)}
  }
}
#let chart(t, d) = shadow(t, dy: 30, blur: 60, color: black.transparentize(40%),
  block(width: 100%, fill: rgb("141414").transparentize(30%), radius: 12*t.u, stroke: 1*t.u+white.transparentize(95%), outset: -0.5*t.u, inset: 1*t.u, clip: true)[
  #block(width: 100%, fill: rgb("1e1e1e"), inset: (x: 20*t.u, top: 12*t.u, bottom: 13*t.u), stroke: (bottom: 1*t.u+border))[
    #grid(columns: (12*t.u, 12*t.u, 12*t.u, 1fr), column-gutter: 8*t.u, align: horizon,
      circle(radius: 6*t.u, fill: rgb("ff5f56"), stroke: none), circle(radius: 6*t.u, fill: rgb("ffbd2e"), stroke: none), circle(radius: 6*t.u, fill: orange, stroke: none),
      pad(left: 12*t.u, copy(t, "trend-analytics.tsx", size: 12.8, fill: secondary, mono: true, lh: 17/12.8)))
  ]
  #block(width: 100%, height: 300*t.u, inset: (top: 40*t.u, bottom: 50*t.u, x: 11*t.u))[
    #let highest = calc.max(1, ..d.hours)
    #grid(columns: (1fr,)*24, gutter: 2*t.u, align: bottom, ..d.hours.enumerate().map(((hour, n)) => [
      #block(width: 100%, height: 210*t.u)[
        #place(bottom, align(center)[
          #copy(t, str(n), size: 8.8, fill: white.transparentize(40%), mono: true, lh: 1.32)#v(4*t.u)
          #rect(width: 80%, height: calc.min(n/highest*210, 174)*t.u, fill: orange, stroke: none, radius: (top: 1*t.u))
          #v(10*t.u)
          #box(height: 10.56*t.u)[#rotate(-60deg, origin: top+center,
            copy(t, (if hour < 10 {"0"} else {""})+str(hour)+":00", size: 8, fill: secondary, mono: true, lh: 1.32))]
        ])
      ]
    ]))
  ]
])
#let members(t, d) = context {
  if d.portraits.len() == 0 {return}
  v(100*t.u)
  section(t, "cat ./user_titles")
  v(41*t.u)
  for (i, x) in d.portraits.enumerate() {
      let body=grid(columns: (50*t.u, 1fr), gutter: 20*t.u, face(t, x.avatar), [
        #copy(t, x.name, size: 17.6, weight: 700, lh: 25/17.6)#v(5*t.u)
        #let tag(value, color) = box(radius: 4*t.u, inset: (x: 9*t.u, y: 3*t.u), stroke: 1*t.u+color.transparentize(70%), fill: color.transparentize(95%))[
          #copy(t, value, size: 12, fill: color, mono: true, lh: 1.5)
        ]
        #par(leading: 6*t.u)[#tag(x.profile, rgb("ffcc00"))#h(8*t.u)#tag(x.title, blue)]
        #v(16*t.u)#copy(t, rich(t, x.reason), size: 13.6, fill: secondary, lh: 1.4)
      ])
    let height=measure(body,width:(820/2.38 - 42)*t.u).height+42*t.u
    block(width: 100%, fill: rgb("1c1c1c"), radius: 8*t.u, inset: 21*t.u, stroke: 1*t.u+border, outset: -0.5*t.u, clip: true)[
      #body
      #if x.image != "" {
        let width=820/2.38*0.36*t.u
        let natural=measure(image(x.image,width:width))
        place(bottom+right, dx: 13*t.u, dy: 13*t.u, image(x.image, width: width, height:calc.min(natural.height,height*0.78), fit: x.image_fit))
      }
    ]
    if i < d.portraits.len() - 1 {v(20*t.u)}
  }
}
#let quotes(t, d) = {
  if d.quotes.len() == 0 {return}
  v(if d.portraits.len()==0 {100*t.u}else{60*t.u})
  section(t, "grep -r \"golden_quotes\"")
  v(41*t.u)
  for (i,x) in d.quotes.enumerate() {
    block(width: 100%, inset: 25*t.u, radius: 12*t.u, fill: rgb("1e1e1e").transparentize(60%), stroke: 1*t.u+white.transparentize(95%), outset: -0.5*t.u)[
      #grid(columns: (45*t.u, 1fr), gutter: 20*t.u, face(t, x.avatar, size: 45, round: true), [
        #copy(t, ["#rich(t, x.content)"], size: 17.6, fill: orange, italic: true, lh: 1.5)#v(12*t.u)
        #copy(t, [#text("--") #x.sender], size: 14.4, fill: blue, mono: true, lh: 19/14.4)#v(8*t.u)
        #copy(t, [#text("//") Reason: #rich(t, x.reason)], size: 12.8, fill: secondary, lh: 19/12.8)
      ])
    ]
    v(if i < d.quotes.len() - 1 {40*t.u}else{20*t.u})
  }
}
#let render(d, t) = {
  let cjk = if d.font_language == "zh-Hant" {"Noto Sans TC"} else {"Noto Sans SC"}
  t.insert("fonts", ("Inter", cjk, "Noto Sans JP"))
  t.insert("mono", ("JetBrains Mono", cjk, "Noto Sans JP"))
  set page(width: 940*t.u, height: auto, margin: 0pt, fill: rgb("0a0a0a"))
  set text(font: t.fonts, fill: white, size: 18*t.u, cjk-latin-spacing: none, overhang: false, hyphenate: false,
    lang: "zh", region: if d.font_language=="zh-Hant" {"TW"}else{"CN"})
  set smartquote(enabled: false)
  set par(spacing: 0pt, leading: 0pt)
  let content = block(width: 940*t.u, inset: (x: 40*t.u, y: 60*t.u))[
    #v(21*t.u)
    #navigation(t)
    #grid(columns: (1.38fr, 1fr), gutter: 40*t.u,
      [#hero(t, d)#quality(t, d)#topics(t, d)],
      [#chart(t, d)#members(t, d)#quotes(t, d)])
    #v(80*t.u)
    #block(width: 100%, inset: (top: 41*t.u), stroke: (top: 1*t.u+border))[
      #grid(columns: (253.5*t.u, 190*t.u, 1fr), gutter: 18*t.u,
        copy(t, [SYSTEM_REPORT #text("//") #d.generated_at], size: 14.4, fill: secondary, mono: true, lh: 1.32),
        copy(t, [TOKENS: #text(fill: orange)[#d.tokens.at(0)] \[P: #d.tokens.at(1) | C: #d.tokens.at(2)\]], size: 14.4, fill: secondary, mono: true, lh: 1.32),
        copy(t, [SXP-#linebreak()Simon/astrbot_plugin_qq_group_daily_analysis#linebreak()群分析], size: 14.4, fill: orange, mono: true, lh: 1.32))
    ]
  ]
  context {
    let measured = measure(content)
    let paper = tiling(size: (30*t.u, 30*t.u))[
      #rect(width: 30*t.u, height: 30*t.u, stroke: (top: 1*t.u+white.transparentize(97%), left: 1*t.u+white.transparentize(97%)))
    ]
    let scan = tiling(size: (4*t.u, 4*t.u))[
      #place(top+left, dy: 2*t.u, rect(width: 4*t.u, height: 2*t.u, fill: black.transparentize(99%), stroke: none))
    ]
    [#metadata((height: measured.height/1pt))<report-size>]
    block(width: 940*t.u, fill: gradient.radial(orange.transparentize(92%), orange.transparentize(100%), center: (50%, 10%), radius: 70%))[
      #block(width: 100%, fill: paper)[#content]
      #place(top+left, rect(width: 940*t.u, height: measured.height, fill: scan, stroke: none))
    ]
  }
}

// 各主题共享的原生排版组件；报告正文始终来自 JSON 字符串，不参与代码求值。
#let labels = (
  "zh-Hans": (title: "群聊日常分析看板", log: "分析日志", messages: "今日消息数", members: "活跃成员数", emoji: "表情互动", characters: "今日字数累计", peak: "峰值活跃时间段", activity: "24小时活动", topics: "话题总结", portraits: "群友画像", quotes: "今日圣经", review: "群聊锐评", verdict: "Miku 综合点评", participants: "参与成员", reason: "AI 锐评"),
  "zh-Hant": (title: "群聊日常分析看板", log: "分析日誌", messages: "今日訊息數", members: "活躍成員數", emoji: "表情互動", characters: "今日字數累計", peak: "峰值活躍時段", activity: "24 小時活動", topics: "話題總結", portraits: "群友畫像", quotes: "今日聖經", review: "群聊銳評", verdict: "Miku 綜合點評", participants: "參與成員", reason: "AI 銳評"),
  "en": (title: "Group Chat Daily Report", log: "Analysis Log", messages: "Messages Today", members: "Active Members", emoji: "Emoji Reactions", characters: "Characters Today", peak: "Peak Activity Window", activity: "24-Hour Activity", topics: "Topics", portraits: "Member Portraits", quotes: "Quote of the Day", review: "Chat Review", verdict: "Miku's Verdict", participants: "Participants", reason: "AI Review"),
  "ja": (title: "グループチャット日報", log: "分析ログ", messages: "今日のメッセージ数", members: "アクティブメンバー数", emoji: "絵文字リアクション", characters: "今日の累計文字数", peak: "ピーク時間帯", activity: "24時間のアクティビティ", topics: "トピックまとめ", portraits: "メンバープロフィール", quotes: "今日の聖書", review: "グループ辛口レビュー", verdict: "ミクの総評", participants: "参加メンバー", reason: "AI コメント"),
)
#let words(d) = labels.at(d.language, default: labels.at("zh-Hans"))
// 卡片投影复用本地 SVG 滤镜；尺寸来自实际排版测量，不影响正文的流式高度。
#let shadow(t,body,radius:12,dy:8,blur:24,color:rgb("2a9d95").transparentize(96%)) = layout(size=>{
  let measured=measure(body,width:size.width)
  let w=measured.width/t.u
  let h=measured.height/t.u
  let pad=blur*2+calc.abs(dy)
  // 滤镜只计算 SVG 画布内可见的像素，避免为大卡片分配三倍宽高的离屏区域。
  let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"' viewBox='0 0 "+str(w+2*pad)+" "+str(h+2*pad)+"'><defs><filter id='s' filterUnits='userSpaceOnUse' x='0' y='0' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"'><feGaussianBlur stdDeviation='"+str(blur/2)+"'/></filter></defs><rect x='"+str(pad)+"' y='"+str(pad+dy)+"' width='"+str(w)+"' height='"+str(h)+"' rx='"+str(radius)+"' fill='"+color.to-hex()+"' filter='url(#s)'/></svg>"
  [#place(top+left,dx:-pad*t.u,dy:-pad*t.u,image(bytes(svg),format:"svg",width:(w+2*pad)*t.u,height:(h+2*pad)*t.u))#body]
})
#let deco(d, index, width: 80pt, height: 65pt) = {
  let path = d.decorations.at(index, default: "")
  if path != "" { image(path, width: width, height: height, fit: "contain") }
}
#let badge(t, body, fill: none) = box(inset: (x: 7*t.u, y: 3*t.u), radius: 5*t.u, fill: if fill == none {t.soft} else {fill})[#text(size: 11*t.u, weight: "bold", fill: t.accent)[#body]]
#let avatar(t, path, size: 40) = box(width: size*t.u, height: size*t.u, radius: 50%, clip: true, fill: t.soft, stroke: 2*t.u + t.border)[
  #if path != "" { image(path, width: size*t.u, height: size*t.u, fit: "cover") } else { align(center + horizon, text(fill: t.accent)[?]) }
]
#let runs(t, parts) = {
  for part in parts {
    if part.avatar != "" {
      box(inset: (x: 3*t.u, y: 1*t.u), radius: 8*t.u, fill: t.soft)[#avatar(t, part.avatar, size: 16)#if part.text != "" { h(3*t.u); text(size: 0.9em, part.text) }]
    } else {
      let lines = part.text.split("\n")
      for (i, value) in lines.enumerate() { if i > 0 { linebreak() }; value }
    }
  }
}
#let card(t, body, fill: none, inset: 20, accent: false) = block(
  width: 100%, breakable: false, radius: t.radius*t.u,
  inset: inset*t.u, fill: if fill == none { t.card } else { fill },
  stroke: if accent { (left: 5*t.u + t.accent, rest: 1*t.u + t.border) } else { 1*t.u + t.border },
)[#body]
#let section(t, title, number: "") = {
  v(25*t.u)
  grid(columns: (5*t.u, 1fr, auto), gutter: 12*t.u, align: horizon,
    rect(width: 5*t.u, height: 25*t.u, fill: t.accent, stroke: none),
    text(size: 23*t.u, weight: "bold", fill: t.accent, title),
    text(size: 11*t.u, fill: t.muted, font: "Share Tech Mono", number),
  )
  v(17*t.u)
}
#let header(t, d, title: none, subtitle: "", mode: "center") = {
  let w = words(d)
  let heading = if title == none or d.language != "zh-Hans" { w.title } else { title }
  if mode == "terminal" {
    card(t, [#text(font: "Share Tech Mono", fill: t.accent)[● ● ●  /  DAILY_ANALYSIS.EXE]#v(18*t.u)#text(size: 30*t.u, weight: "bold", heading)#v(12*t.u)#text(fill: t.accent)[> #d.date  /  SYSTEM ONLINE]])
  } else if mode == "newspaper" {
    align(center)[#text(size: 11*t.u, tracking: 2*t.u, subtitle)#v(12*t.u)#text(size: 38*t.u, weight: "bold", heading)#v(12*t.u)#line(length: 100%, stroke: 3*t.u + t.accent)#v(5*t.u)#text(size: 12*t.u)[#w.log  ·  #d.date]#v(5*t.u)#line(length: 100%, stroke: 0.8*t.u + t.border)]
  } else if mode == "banner" {
    card(t, fill: t.accent, [#text(fill: t.card, size: 34*t.u, weight: "bold", heading)#v(10*t.u)#text(fill: t.card, size: 13*t.u)[#subtitle  ·  #d.date]])
  } else {
    align(if mode == "left" {left} else {center})[
      #text(size: 11*t.u, tracking: 1.3*t.u, fill: t.accent, font: "Share Tech Mono", subtitle)
      #v(14*t.u)
      #text(size: 34*t.u, weight: "bold", fill: t.ink, heading)
      #v(12*t.u)
      #text(size: 15*t.u, fill: t.accent)[#w.log · #d.date]
    ]
  }
  v(30*t.u)
}
#let metrics(t, d, columns: 4) = {
  let w = words(d)
  let entries = ((w.messages, d.message_count), (w.members, d.participant_count), (w.emoji, d.emoji_count), (w.characters, d.characters))
  grid(columns: (1fr,) * columns, gutter: 15*t.u, ..entries.map(entry => card(t, inset: 17, [#align(center)[#text(size: 12*t.u, fill: t.muted, entry.at(0))#v(10*t.u)#text(font: "Outfit", size: 32*t.u, weight: "bold", str(entry.at(1)))]])))
}
#let peak(t, d, illustration: true) = {
  v(25*t.u)
  card(t, fill: gradient.linear(t.accent, t.secondary, angle: 0deg), inset: 22, [
    #grid(columns: (1fr, auto), align: horizon, gutter: 15*t.u,
      [#text(size: 14*t.u, weight: "bold", fill: white, words(d).peak)#v(10*t.u)#text(size: 30*t.u, weight: "bold", fill: white, d.peak)],
      if illustration {deco(d, 0, width: 180*t.u, height: 85*t.u)} else {text(size: 45*t.u, fill: white)[↗]},
    )
  ])
}
#let activity(t, d) = {
  section(t, words(d).activity, number: "ACTIVITY / 24H")
  card(t, inset: 18, [
    #let highest = calc.max(1, ..d.hours)
    #grid(columns: (1fr,) * 24, column-gutter: 4*t.u, align: bottom,
      ..d.hours.enumerate().map(((hour, count)) => [
        #align(center)[
          #box(height: 120*t.u, width: 100%)[#align(bottom)[
            #if count > 0 { text(size: 9*t.u, fill: t.accent, str(count)); v(4*t.u) }
            #rect(width: 100%, height: calc.max(3, count/highest*90)*t.u, radius: 3*t.u, stroke: none, fill: if count == highest {t.secondary} else {t.accent.lighten(30%)})
          ]]
          #v(5*t.u)#text(size: 9*t.u, fill: t.muted, (if hour < 10 {"0"} else {""}) + str(hour))
        ]
      ]),
    )
  ])
}
#let topics(t, d, mode: "cards") = {
  if d.topics.len() == 0 { return }
  section(t, words(d).topics, number: "TOPICS")
  for (i, topic) in d.topics.enumerate() {
    let body = [
      #grid(columns: (auto, 1fr), gutter: 16*t.u,
        text(size: 25*t.u, weight: "bold", fill: t.secondary)[#(if mode == "checklist" {"☑"} else {"#" + (if i < 9 {"0"} else {""}) + str(i+1)})],
        [#text(size: 20*t.u, weight: "bold", topic.title)#v(12*t.u)
          #block(fill: t.soft, inset: 12*t.u, radius: 7*t.u)[#runs(t, topic.detail)]
          #v(15*t.u)#grid(columns: (1fr, auto), align: horizon,
            text(size: 12*t.u, fill: t.accent)[#words(d).participants: #runs(t, topic.contributors)],
            deco(d, 1 + calc.rem(i, calc.max(1, d.decorations.len()-1)), width: 100*t.u, height: 55*t.u))
        ],
      )
    ]
    if mode == "editorial" { body; v(15*t.u); line(length: 100%, stroke: 0.8*t.u + t.border) }
    else if mode == "checklist" { rotate(if calc.even(i) {-0.3deg} else {0.3deg}, card(t, fill: if calc.even(i) {t.soft} else {t.card}, body)) }
    else { card(t, accent: true, body) }
    v(18*t.u)
  }
}
#let portraits(t, d, columns: 2) = {
  if d.portraits.len() == 0 { return }
  section(t, words(d).portraits, number: "MEMBERS")
  grid(columns: (1fr,) * columns, gutter: 20*t.u, ..d.portraits.map(p => card(t, [
    #grid(columns: (auto, 1fr), gutter: 12*t.u, align: horizon,
      avatar(t, p.avatar, size: 54),
      [#text(weight: "bold", size: 18*t.u, p.name)#v(7*t.u)#badge(t,p.title)#h(4*t.u)#badge(t,p.profile,fill:t.secondary.lighten(50%))])
    #v(15*t.u)
    #block(width: 100%, fill: t.soft, inset: 14*t.u, radius: 8*t.u)[
      #if p.image != "" { place(bottom + right, image(p.image, width: 90*t.u, height: 85*t.u, fit: "contain")) }
      #text(size: 14*t.u, fill: t.muted)[#runs(t,p.reason)]
    ]
  ])))
}
#let quotes(t, d, mode: "chat") = {
  if d.quotes.len() == 0 { return }
  section(t, words(d).quotes, number: "QUOTES")
  for (i, q) in d.quotes.enumerate() {
    align(if mode == "chat" and calc.odd(i) {right} else {left})[
      #block(width: if mode == "chat" {88%} else {100%})[
        #grid(columns: if calc.odd(i) and mode == "chat" {(1fr, auto)} else {(auto, 1fr)}, gutter: 15*t.u,
          ..(if calc.odd(i) and mode == "chat" {(true,false)} else {(false,true)}).map(content => if not content {avatar(t,q.avatar,size:44)} else {[
            #text(size: 13*t.u, fill: t.muted, q.sender)#v(7*t.u)
            #card(t, inset: 20, [#text(weight: "bold", size: 17*t.u)[#runs(t,q.content)]])
            #v(10*t.u)
            #block(width: 100%, fill: t.soft, inset: 14*t.u, radius: 10*t.u, stroke: (left: 4*t.u + t.secondary))[
              #text(size: 14*t.u, weight: "bold", fill: t.accent, words(d).reason)#v(6*t.u)#text(size: 14*t.u, fill: t.muted)[#runs(t,q.reason)]
            ]
          ]}),
        )
      ]
    ]
    v(20*t.u)
  }
}
#let review(t, d) = {
  if d.review == none {return}
  let r = d.review
  let colors = (t.accent, t.secondary, t.accent.lighten(45%), rgb("fff9c4"), rgb("80cbc4"))
  section(t, words(d).review, number: "REVIEW")
  card(t, [
    #grid(columns:(1fr,auto), gutter: 10*t.u, align:horizon, text(size:24*t.u,fill:t.accent,r.title),badge(t,r.subtitle))
    #v(20*t.u)
    #let total = calc.max(1, ..r.dimensions.map(x => x.percentage))
    #if r.dimensions.len() > 0 {
      grid(columns:r.dimensions.map(x => calc.max(0.1,x.percentage)*1fr), ..r.dimensions.enumerate().map(((i,x)) => rect(width:100%,height:12*t.u,fill:colors.at(calc.rem(i,colors.len())),stroke:none)))
      v(20*t.u)
      grid(columns:(1fr,1fr),gutter:12*t.u,..r.dimensions.map(x => block(fill:t.soft,inset:12*t.u,radius:8*t.u)[#text(weight:"bold",size:14*t.u)[#x.name (#x.percentage%)]#v(6*t.u)#text(size:13*t.u,fill:t.muted)[#runs(t,x.comment)]]))
    }
    #v(20*t.u)
    #card(t, fill: gradient.linear(t.accent,t.secondary,angle:135deg), [#text(fill:white,weight:"bold",words(d).verdict)#v(10*t.u)#text(fill:white)[#runs(t,r.summary)]])
  ])
}
#let footer(t, d, author: "") = {
  v(35*t.u)
  line(length:100%,stroke:0.8*t.u+t.border)
  v(15*t.u)
  text(size:11*t.u,fill:t.muted)[
    SXP-Simon/astrbot_plugin_qq_group_daily_analysis
    #h(1fr) Token usage: #d.tokens.at(0) (P: #d.tokens.at(1) | C: #d.tokens.at(2))
    #linebreak() Generated at #d.generated_at #h(1fr) #author
  ]
}
#let document(d, t, body) = {
  set page(width: d.width*t.u, height: auto, margin: 0pt, fill: t.bg)
  let fonts = if d.language == "ja" {("Noto Sans JP", "Noto Sans SC")} else if d.language == "zh-Hant" {("Noto Sans TC", "Noto Sans SC")} else {("Noto Sans SC",)}
  set text(font: fonts, size: 16*t.u, fill: t.ink, lang: if d.language == "ja" {"ja"} else if d.language == "en" {"en"} else {"zh"})
  set par(leading: 0.65em, spacing: 0pt)
  let pattern = tiling(size:(25*t.u,25*t.u))[
    #if t.pattern == "dots" { circle(radius: 1*t.u,fill:t.border,stroke:none) } else if t.pattern == "grid" { rect(width:25*t.u,height:25*t.u,stroke:0.35*t.u+t.border) }
  ]
  set page(background: if t.pattern != "none" {rect(width:100%,height:100%,fill:pattern,stroke:none)} else {none})
  let content = block(width:d.width*t.u,inset:(x:20*t.u,y:35*t.u))[
    #block(width:100%,inset:35*t.u,fill:t.paper,radius:t.radius*t.u,stroke:1*t.u+t.border)[#body]
  ]
  context {
    let size = measure(content)
    [#metadata((height: size.height/1pt))<report-size>]
    content
  }
}

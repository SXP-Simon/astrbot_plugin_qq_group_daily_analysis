// 各主题共享的语言标签、投影与行内身份标记；正文始终来自 JSON 字符串。
#let labels = (
  "zh-Hans": (title: "群聊日常分析看板", log: "分析日志", messages: "今日消息数", members: "活跃成员数", emoji: "表情互动", characters: "今日字数累计", peak: "峰值活跃时间段", activity: "24小时活动", topics: "话题总结", portraits: "群友画像", quotes: "今日圣经", review: "群聊锐评", verdict: "Miku 综合点评", participants: "参与成员", reason: "AI 锐评"),
  "zh-Hant": (title: "群聊日常分析看板", log: "分析日誌", messages: "今日訊息數", members: "活躍成員數", emoji: "表情互動", characters: "今日字數累計", peak: "峰值活躍時段", activity: "24 小時活動", topics: "話題總結", portraits: "群友畫像", quotes: "今日聖經", review: "群聊銳評", verdict: "Miku 綜合點評", participants: "參與成員", reason: "AI 銳評"),
  "en": (title: "Group Chat Daily Report", log: "Analysis Log", messages: "Messages Today", members: "Active Members", emoji: "Emoji Reactions", characters: "Characters Today", peak: "Peak Activity Window", activity: "24-Hour Activity", topics: "Topics", portraits: "Member Portraits", quotes: "Quote of the Day", review: "Chat Review", verdict: "Miku's Verdict", participants: "Participants", reason: "AI Review"),
  "ja": (title: "グループチャット日報", log: "分析ログ", messages: "今日のメッセージ数", members: "アクティブメンバー数", emoji: "絵文字リアクション", characters: "今日の累計文字数", peak: "ピーク時間帯", activity: "24時間のアクティビティ", topics: "トピックまとめ", portraits: "メンバープロフィール", quotes: "今日の聖書", review: "グループ辛口レビュー", verdict: "ミクの総評", participants: "参加メンバー", reason: "AI コメント"),
)
#let words(d) = labels.at(d.language, default: labels.at("zh-Hans"))
// 卡片投影复用本地 SVG 滤镜；尺寸来自实际排版测量，不影响正文的流式高度。
#let shadow(t,body,radius:12,dy:8,blur:24,color:rgb("2a9d95").transparentize(96%)) = {
  let draw(measured) = {
    let w=measured.width/t.u
    let h=measured.height/t.u
    let pad=blur*2+calc.abs(dy)
    // 滤镜只计算 SVG 画布内可见的像素，避免为大卡片分配三倍宽高的离屏区域。
    let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"' viewBox='0 0 "+str(w+2*pad)+" "+str(h+2*pad)+"'><defs><filter id='s' filterUnits='userSpaceOnUse' x='0' y='0' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"'><feGaussianBlur stdDeviation='"+str(blur/2)+"'/></filter></defs><rect x='"+str(pad)+"' y='"+str(pad+dy)+"' width='"+str(w)+"' height='"+str(h)+"' rx='"+str(radius)+"' fill='"+color.to-hex()+"' filter='url(#s)'/></svg>"
    [#place(top+left,dx:-pad*t.u,dy:-pad*t.u,image(bytes(svg),format:"svg",width:(w+2*pad)*t.u,height:(h+2*pad)*t.u))#body]
  }
  // 固定尺寸直接绘制，避免嵌套测量复制整棵布局；自适应内容仍按原约束测量。
  let fields=if body.func()==block or body.func()==box {body.fields()}else{(:)}
  let width=fields.at("width",default:auto)
  let height=fields.at("height",default:auto)
  if type(width)==relative and width.ratio==0% and type(height)==relative and height.ratio==0% {
    context draw((width:width.length.to-absolute(),height:height.length.to-absolute()))
  }else if type(width)==relative and width.ratio==0% {
    context draw(measure(body,width:width.length))
  }else if type(width)==relative and type(height)==relative and height.ratio==0% {
    layout(size=>draw((width:width.ratio*size.width+width.length.to-absolute(),height:height.length.to-absolute())))
  }else{
    layout(size=>draw(measure(body,width:size.width)))
  }
}
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

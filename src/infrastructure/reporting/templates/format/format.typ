// Format 沿用原版编辑排版、横向小时条和蓝色质量分析区，不更改各模块配色。
#import "common.typ":shadow
#let ink=rgb("111111")
#let muted=rgb("666666")
#let border=rgb("e0e0e0")
#let soft=rgb("fafafa")
#let blue=rgb("007bff")
#let palette=("007bff","6610f2","6f42c1","e83e8c","fd7e14","28a745","20c997","17a2b8")
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.6,font:none,tracking:0,italic:false) = {
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="serif" {t.serif}else if font=="sc" {("Noto Serif SC","Noto Serif TC")}else{t.body}
  let baseline=if font in ("serif","sc") {.4325}else{.36377}
  // 浏览器会合成中文斜体，逐字倾斜才能避免长段落整体错位或被裁切。
  let result=text(font:fonts,size:size*t.u,weight:weight,fill:fill,tracking:tracking*1em,style:if italic {"italic"}else{"normal"},top-edge:(lh/2+baseline)*1em,bottom-edge:-(lh/2-baseline)*1em,body)
  if italic {
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*"):it=>box(height:lh*size*t.u,baseline:(at:top,shift:-(lh/2+baseline)*size*t.u))[#skew(ax:-12deg,origin:bottom+left,it)]
    result
  }else{result}
}
#let runs(t,parts) = {
  for part in parts {
    if part.avatar!="" {
      h(2*t.u)
      box(inset:(left:3*t.u,right:7*t.u,y:3*t.u),fill:black.transparentize(95%),stroke:1*t.u+black.transparentize(90%),radius:12*t.u,baseline:(at:bottom,shift:7*t.u))[
        #set text(top-edge:.85em,bottom-edge:-.15em)
        #box(width:18*t.u,height:18*t.u,radius:50%,clip:true,baseline:25%)[#image(part.avatar,width:100%,height:100%,fit:"cover")]
        #if part.text!="" {h(4*t.u);text(size:.85em,weight:500,top-edge:.85em,bottom-edge:-.15em,part.text)}
      ]
      h(2*t.u)
    }else{for (i,line) in part.text.split("\n").enumerate(){if i>0 {linebreak()};line}}
  }
}
#let heading(t,title) = {
  block(width:100%,inset:(left:16*t.u))[
    #place(top+left,dx:-16*t.u,dy:(38.4 - 20)/2*t.u,rect(width:3*t.u,height:20*t.u,fill:rgb("222222"),stroke:none))
    #copy(t,title,size:24,weight:600,font:"serif")
  ]
  v(25*t.u)
}
// 话题、画像和质量点评均使用逐行等高的双栏；只测各张卡片，不重复测整份长图。
#let cards(t,bodies,padding:25,gap:15,radius:12,fill:soft,line:border,profiles:()) = layout(size=>{
  let width=(size.width - gap*t.u)/2
  for start in range(0,bodies.len(),step:2) {
    let row=bodies.slice(start,calc.min(start+2,bodies.len())).map(body=>block(width:width,inset:(padding+1)*t.u)[#body])
    let height=calc.max(..row.map(body=>measure(body).height))
    grid(columns:(width,width),gutter:gap*t.u,..row.enumerate().map(((i,body))=>block(width:width,height:height,fill:fill,stroke:1*t.u+line,outset:-.5*t.u,radius:radius*t.u,clip:true)[
      #body
      #if profiles.len()>start+i {
        let p=profiles.at(start+i)
        if p.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(p.image,width:width*.38,height:calc.min(measure(image(p.image,width:width*.38)).height,height*.82),fit:p.image_fit))}
      }
    ]))
    if start+2 < bodies.len() {v(gap*t.u)}
  }
})
#let statistics(t,d) = {
  heading(t,"基础统计")
  grid(columns:(1fr,)*4,gutter:15*t.u,..((d.message_count,"消息总数"),(d.participant_count,"参与人数"),(d.characters,"总字符数"),(d.emoji_count,"表情数量")).map(e=>block(width:100%,inset:(x:11*t.u,y:21*t.u),fill:soft,stroke:1*t.u+border,outset:-.5*t.u,radius:12*t.u)[
    #align(center)[
      #copy(t,str(e.at(0)).clusters().join(sym.zws),size:28.8,weight:600,tracking:-.02,lh:1)
      #v(6*t.u)#copy(t,e.at(1),size:12,weight:500,fill:muted,tracking:.05)
    ]
  ]))
  v(30*t.u)
  block(width:100%,inset:30*t.u,fill:rgb("222222"),radius:12*t.u)[#align(center)[
    #copy(t,d.peak,size:35.2,fill:white,font:"serif")#v(6*t.u)
    #copy(t,"最活跃时段",size:13.6,weight:500,fill:rgb("d3d3d3"),tracking:.1)
  ]]
  v(50*t.u)
}
#let activity(t,d) = {
  copy(t,"24小时活跃度分布",size:20.8,weight:600,font:"sc")
  // 原组件开头的 BOM 在浏览器形成一行，保留其占据的 25.6px 间隔。
  v((25+25.6+10)*t.u)
  let highest=calc.max(1,..d.hours)
  for (hour,count) in d.hours.enumerate() {
    let ratio=count/highest
    grid(columns:(45*t.u,1fr),align:horizon,
      copy(t,(if hour < 10 {"0"}else{""})+str(hour)+":00",size:12,weight:500,fill:muted,lh:1.5),
      layout(size=>{
        // 高占比数字沿用 HTML 的白色小字，低占比数字显示在条形右侧。
        let outside=copy(t,str(count),size:11,weight:500,fill:muted)
        let natural=ratio*size.width
        let bar-width=if ratio<=.15 {calc.min(natural,calc.max(0pt,size.width - 10*t.u - calc.max(25*t.u,measure(outside).width)))}else{natural}
        box(width:size.width,height:18*t.u)[
          #place(top+left,dy:5*t.u,block(width:bar-width,height:8*t.u,fill:rgb("4e4e4e"),radius:4*t.u)[
            #if ratio>.15 {place(top+left,dy:8*t.u,block(inset:(x:5*t.u))[#copy(t,str(count),size:10,weight:600,fill:white,lh:1.6)])}
          ])
          #if ratio<=.15 {place(top+left,dx:bar-width+10*t.u,dy:.2*t.u,box(width:calc.max(25*t.u,measure(outside).width))[#align(right,outside)])}
        ]
      }),
    )
    if hour < 23 {v(10*t.u)}
  }
  v(50*t.u)
}
#let quality(t,d) = {
  if d.review==none {return}
  let r=d.review
  heading(t,"群聊质量分析")
  v(25.6*t.u)
  layout(size=>{
    let total=calc.max(100,r.dimensions.map(x=>x.percentage).sum(default:0))
    let inside=block(width:size.width,inset:(left:30*t.u,right:25*t.u,y:25*t.u))[
      #copy(t,r.title,size:24,weight:700,fill:rgb("212529"))
      #v(5*t.u)#if r.subtitle!="" {copy(t,upper(r.subtitle),size:14.4,fill:rgb("6c757d"),tracking:.5/14.4)}
      #v(15*t.u)#rect(width:100%,height:1*t.u,fill:rgb("f1f3f5"),stroke:none)
      #v(25*t.u)
      #block(width:100%,height:20*t.u,inset:1*t.u,fill:rgb("f8f9fa"),radius:4*t.u,stroke:1*t.u+rgb("e9ecef"),outset:-.5*t.u,clip:true)[
        #layout(dim=>{
          for (i,x) in r.dimensions.enumerate() {
            if x.percentage>0 {
              place(top+left,dx:r.dimensions.slice(0,i).map(x=>x.percentage).sum(default:0)/total*dim.width,
                block(width:x.percentage/total*dim.width,height:18*t.u,fill:rgb(palette.at(calc.rem(i,8))),stroke:if i < r.dimensions.len()-1 {(right:1*t.u+white.transparentize(85%))}else{none},outset:-.5*t.u))
            }
          }
        })
      ]
      #v(25*t.u)
      #cards(t,r.dimensions.filter(x=>x.percentage>0).map(x=>[
        #copy(t,upper(x.name),size:12.92,weight:700,fill:blue,lh:1.6)#v(8*t.u)
        #copy(t,[#x.percentage%],size:12.92,weight:600,fill:rgb("6c757d"))#v(8*t.u)
        #copy(t,runs(t,x.comment),size:15.2,fill:rgb("495057"))
      ]),padding:15,gap:20,radius:4,fill:rgb("fcfcfc"),line:rgb("f1f3f5"))
      #v(25*t.u)
      #block(width:100%,inset:19*t.u,fill:rgb("f8f9fa"),stroke:1*t.u+rgb("e9ecef"),outset:-.5*t.u,radius:4*t.u)[
        #copy(t,[#box(inset:(x:8*t.u),fill:rgb("e9ecef"),radius:3*t.u)[#text(weight:800,fill:rgb("212529"))[EXECUTIVE SUMMARY]]#h(12*t.u)#runs(t,r.summary)],fill:rgb("495057"))
      ]
    ]
    let height=measure(inside).height
    shadow(t,block(width:size.width,height:height,fill:white,stroke:(rest:1*t.u+rgb("dee2e6"),left:6*t.u+blue),outset:(rest:-.5*t.u,left:-3*t.u))[
      #inside
    ],radius:0,blur:6,dy:4,color:black.transparentize(95%))
  })
  v(50*t.u)
}
#let topics(t,d) = {
  if d.topics.len()==0 {return}
  v(25.6*t.u)
  heading(t,"热门话题")
  cards(t,d.topics.enumerate().map(((i,x))=>[
    #grid(columns:(24*t.u,1fr),gutter:12*t.u,align:horizon,
      circle(radius:12*t.u,fill:ink,stroke:none)[#align(center+horizon,copy(t,str(i+1),size:12.8,weight:600,fill:white))],
      copy(t,x.title,size:17.6,weight:600,font:"sc",lh:1.3))
    #v(14*t.u)
    #block(inset:(left:36*t.u))[
      #copy(t,[参与者: #runs(t,x.contributors)],size:12.8,fill:muted,italic:true)#v(10*t.u)
      #copy(t,runs(t,x.detail),size:14.4,fill:rgb("444444"))
    ]
  ]))
  v(50*t.u)
}
#let portraits(t,d) = {
  if d.portraits.len()==0 {return}
  v(25.6*t.u)
  heading(t,"群友称号")
  cards(t,d.portraits.map(p=>[
    #grid(columns:(44*t.u,1fr),gutter:15*t.u,align:horizon,
      box(width:44*t.u,height:44*t.u,radius:50%,fill:border,stroke:1*t.u+black.transparentize(95%),outset:-.5*t.u,inset:1*t.u)[
        #box(width:100%,height:100%,radius:50%,clip:true)[#if p.avatar!="" {image(p.avatar,width:100%,height:100%,fit:"cover")}else{align(center+horizon,text(font:"Noto Color Emoji",size:17.6*t.u)[👤])}]
      ],[
        #block(width:100%,height:25.6*t.u,clip:true)[#layout(size=>{
          let clusters=p.name.clusters()
          let name=p.name
          while measure(copy(t,name,size:16,weight:600)).width>size.width and clusters.len()>0 {
            clusters=clusters.slice(0,clusters.len()-1)
            name=clusters.join()+"…"
          }
          copy(t,name,size:16,weight:600)
        })]#v(5*t.u)
        #box(inset:(x:9*t.u,y:4*t.u),fill:white,stroke:1*t.u+ink,outset:-.5*t.u,radius:4*t.u)[#copy(t,upper(p.title),size:12,weight:600,tracking:.05)]#h(6*t.u,weak:true)#box(height:27.2*t.u,inset:(x:8*t.u,y:3*t.u),fill:border,radius:4*t.u)[#copy(t,p.profile,size:12,weight:600)]
      ])
    #v(14*t.u)#copy(t,runs(t,p.reason),size:13.6,weight:500,fill:muted,italic:true)#v(10*t.u)
  ]),padding:20,profiles:d.portraits)
  v(50*t.u)
}
#let quotes(t,d) = {
  if d.quotes.len()==0 {return}
  v(25.6*t.u)
  heading(t,"群圣经")
  for (i,q) in d.quotes.enumerate() {
    block(width:100%,inset:(left:28*t.u,right:25*t.u,y:25*t.u),fill:soft,radius:12*t.u,stroke:(left:3*t.u+ink),outset:(left:-1.5*t.u),clip:true)[
      #copy(t,["#runs(t,q.content)"],size:17.6,weight:500,font:"serif",italic:true)#v(10*t.u)
      #align(right,copy(t,[—— #q.sender],size:13.6,weight:600))#v(6*t.u)
      #align(right,box(inset:(x:10*t.u,y:5*t.u),fill:rgb("f2f2f2"),radius:4*t.u)[#align(left,copy(t,runs(t,q.reason),size:12,fill:muted))])
    ]
    if i < d.quotes.len()-1 {v(15*t.u)}
  }
  v(50*t.u)
}
#let render(d) = {
  let u=.5pt
  let cjk=if d.font_language=="zh-Hant" {("Noto Sans TC","Noto Sans SC")}else{("Noto Sans SC","Noto Sans TC")}
  let serif=if d.font_language=="zh-Hant" {("Noto Serif TC","Noto Serif SC")}else{("Noto Serif SC","Noto Serif TC")}
  let t=(u:u,body:("Inter",..cjk,"Noto Color Emoji"),serif:serif)
  set page(width:940*u,height:auto,margin:0pt,fill:rgb("f2f2f2"))
  set text(font:t.body,size:16*u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none)
  set par(spacing:0pt,leading:0pt)
  set smartquote(enabled:false)
  set page(background:layout(size=>{
    box(width:size.width,height:size.height)[
      #place(top+left,dx:20*u,dy:20*u,shadow(t,block(width:900*u,height:size.height - 40*u,fill:white,radius:12*u),radius:12,blur:10,dy:2,color:black.transparentize(97%)))
    ]
  }))
  block(width:940*u,inset:20*u)[
    #block(width:100%,inset:(x:30*u,top:50*u,bottom:30*u),stroke:(bottom:1*u+border),outset:(bottom:-.5*u))[
      #align(center)[
        #copy(t,"群聊日常分析报告",size:38.4,weight:700,font:"serif",tracking:-.03)#v(12*u)
        #copy(t,upper(d.date),size:14.4,weight:500,fill:muted,tracking:.1)
      ]
      #v(1*u)
    ]
    #block(width:100%,inset:(x:30*u,y:40*u))[
      #statistics(t,d)#activity(t,d)#quality(t,d)#topics(t,d)#portraits(t,d)#quotes(t,d)
    ]
    #block(width:100%,inset:(x:30*u,top:31*u,bottom:30*u),stroke:(top:1*u+border),outset:(top:-.5*u))[
      #align(center)[
        #copy(t,[由 AstrBot 群日常分析插件 生成 | #d.generated_at],size:13.6,fill:muted,lh:1.8)
        #copy(t,"SXP-Simon/astrbot_plugin_qq_group_daily_analysis",size:13.6,fill:muted,lh:1.8)
        #copy(t,[AI分析消耗：#d.tokens.at(0) tokens (输入: #d.tokens.at(1), 输出: #d.tokens.at(2))],size:13.6,fill:rgb("949494"),lh:1.8)
      ]
    ]
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

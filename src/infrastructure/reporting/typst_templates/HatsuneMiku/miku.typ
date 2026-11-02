// Miku 长图的独立布局：逐项保留原版的尺寸、层级、图标、底纹和气泡关系。
#import "common.typ": words, runs, deco
#let base = rgb("39c5bb")
#let dark = rgb("2a9d95")
#let light = rgb("a7e7e3")
#let pink = rgb("f8bbd0")
#let ink = rgb("2c3e50")
#let muted = rgb("7f8c8d")
#let soft = rgb("f0fafa")
#let border = rgb("39c5bb").transparentize(85%)
#let icon(t,name,size:24) = box(width:size*t.u,height:size*t.u)[#image("icon-"+name+".svg",width:100%,height:100%)]
// 显式行框使多行正文的高度与 CSS line-height 一致，不依赖默认段间距。
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.45,font:none) = {
  set par(leading:(lh - 1)*size*t.u,spacing:0pt)
  let edge=(lh - 1)/2
  text(size:size*t.u,weight:weight,fill:fill,top-edge:(0.88+edge)*1em,bottom-edge:(0.12+edge)*1em,font:if font==none {t.fonts} else {font})[#body]
}
#let frame(t,body,inset:30,fill:white,radius:12,stroke:border,height:auto) = block(width:100%,height:height,fill:fill,radius:radius*t.u,inset:inset*t.u,stroke:1*t.u+stroke,breakable:false)[#body]
#let face(t,path,size:48) = box(width:size*t.u,height:size*t.u,radius:50%,clip:true,fill:soft,stroke:2*t.u+light,inset:3*t.u)[
  #box(width:100%,height:100%,radius:50%,clip:true,fill:base)[#if path!="" {image(path,width:100%,height:100%,fit:"cover")}]
]
#let capsule(t,body,fill:rgb("e0f2f1"),size:13.6) = box(fill:fill,radius:20*t.u,inset:(x:16*t.u,y:8*t.u),stroke:0.7*t.u+border)[#copy(t,body,size:size,fill:dark,lh:1.4)]
#let section(t,title,name,pink-bar:false,gap:30) = {
  block(width:100%,height:48*t.u,stroke:(bottom:1*t.u+base.transparentize(90%)),inset:(bottom:12*t.u))[
    #grid(columns:(5*t.u,24*t.u,1fr),gutter:15*t.u,align:horizon,
      rect(width:5*t.u,height:24*t.u,radius:2.5*t.u,fill:if pink-bar {pink}else{base},stroke:none),
      icon(t,name),copy(t,title,size:24,weight:800,lh:1.45))
  ]
  v(gap*t.u)
}
#let heading(t,d) = context {
  grid(columns:(1fr,auto),rows:65*t.u,align:bottom,gutter:15*t.u,
    [#let size=if d.language=="en" {32} else if d.language=="ja" {36} else {44.8}
      #let title=copy(t,words(d).title,size:size,weight:800)
      #box(width:measure(title).width)[#place(bottom,dy:-3*t.u,rect(width:100%,height:8*t.u,radius:4*t.u,fill:base.transparentize(45%),stroke:none))#move(dy:-12*t.u,title)]],
    move(dy:-5*t.u,copy(t,[#words(d).log #text("//") #d.date],size:17.6,weight:700,fill:dark,font:"Outfit",lh:1.35)))
  v(40*t.u)
}
#let stats(t,d) = {
  let w=words(d)
  let items=((w.messages,d.message_count,"message-square"),(w.members,d.participant_count,"users"),(w.emoji,d.emoji_count,"smile"),(w.characters,d.characters,"type"))
  grid(columns:(1fr,)*4,gutter:15*t.u,..items.map(item=>frame(t,height:107*t.u,inset:18,[
    #align(center)[#grid(columns:(auto,auto),gutter:6*t.u,align:horizon,icon(t,item.at(2),size:18),copy(t,item.at(0),size:13.6,weight:700,fill:muted))#v(5*t.u)#copy(t,str(item.at(1)),size:35.2,weight:800,font:"Outfit",lh:1.25)]
  ])))
  v(30*t.u)
}
#let peak(t,d) = {
  block(width:100%,height:120*t.u,fill:gradient.linear(base,light,angle:0deg),radius:12*t.u,inset:(x:35*t.u),clip:true)[
    #place(right+horizon,dx:10*t.u,copy(t,[#text(style:"italic")[MIKU]],size:140,weight:800,fill:white.transparentize(80%),font:"Outfit",lh:1))
    #grid(columns:(1fr,150*t.u),rows:120*t.u,align:horizon,
      [#grid(columns:(auto,1fr),gutter:8*t.u,align:horizon,icon(t,"trending-up",size:20),copy(t,words(d).peak,size:17.6,weight:700,fill:white))#v(6*t.u)#copy(t,d.peak,size:44.8,weight:800,fill:white,font:"Outfit",lh:1.25)],
      deco(d,0,width:150*t.u,height:120*t.u))
  ]
  v(30*t.u)
}
#let activity(t,d) = {
  section(t,words(d).activity,"line-chart")
  frame(t,height:262*t.u,inset:0,[
    #block(inset:(x:10*t.u,y:20*t.u))[
      #let highest=calc.max(1,..d.hours)
      #let colors=("66d1c7","6fd3c6","79d5c4","85d8c3","93dac1","a3ddbf","b4e0bd","c7e2ba","dbe5b8","efe8b5","ffeab3","ffdf9e","ffd38b","ffc67a","ffb96d","ffac62","ffa059","ff9552","ff8b4d","ff834b","ff7d4d","ff7752","ff745a","ff7365")
      #grid(columns:(1fr,)*24,column-gutter:4*t.u,align:bottom,..d.hours.enumerate().map(((hour,n))=>[
        #align(center)[
          #box(width:100%,height:180*t.u)[#align(bottom)[
            #if n>0 {copy(t,str(n),size:12,weight:800,fill:rgb(colors.at(hour)),font:"Outfit",lh:1.25);v(5*t.u)}
            #rect(width:100%,height:calc.max(4,n/highest*135)*t.u,radius:(top:4*t.u,bottom:1*t.u),fill:if n==0 {soft} else {rgb(colors.at(hour))},stroke:none)
          ]]
          #v(15*t.u)
          #copy(t,[#((if hour < 10 {"0"}else{""})+str(hour))#if calc.rem(hour,4)==0 or hour==23 {text(size:9*t.u)[时]}],size:11.2,weight:700,fill:muted,font:"Outfit",lh:1.25)
        ]
      ]))
    ]
  ])
  v(50*t.u)
}
#let topics(t,d) = {
  if d.topics.len()==0 {return}
  section(t,words(d).topics,"message-square",pink-bar:true)
  for (i,topic) in d.topics.enumerate() {
    block(width:100%,fill:white,radius:12*t.u,stroke:(left:6*t.u+base,rest:1*t.u+border),inset:(left:30*t.u,right:24*t.u,top:25*t.u,bottom:25*t.u),breakable:false)[
      #grid(columns:(50*t.u,1fr),gutter:20*t.u,
        copy(t,"#"+(if i < 9 {"0"}else{""})+str(i+1),size:28.8,weight:800,fill:pink,font:"Outfit",lh:1.25),
        [#copy(t,topic.title,size:20,weight:800,lh:1.4)#v(10*t.u)
          #block(inset:12*t.u)[#copy(t,runs(t,topic.detail),lh:1.8)]
          #v(18*t.u)
          #grid(columns:(1fr,auto),rows:65*t.u,gutter:12*t.u,align:horizon,
            [#capsule(t,[#icon(t,"mic",size:16)#h(8*t.u)#text(fill:muted)[#words(d).participants: ]#text(weight:700)[#runs(t,topic.contributors)]])],
            deco(d,1+calc.rem(i,calc.max(1,d.decorations.len()-1)),width:100*t.u,height:65*t.u))
        ])
    ]
    if i < d.topics.len()-1 {v(25*t.u)}
  }
  v(50*t.u)
}
#let portraits(t,d) = {
  if d.portraits.len()==0 {return}
  section(t,words(d).portraits,"users",gap:54)
  grid(columns:(1fr,1fr),gutter:20*t.u,..d.portraits.map(p=>block(width:100%,fill:white,radius:12*t.u,stroke:(top:4*t.u+light,rest:1*t.u+border),inset:(x:25*t.u,top:28*t.u,bottom:25*t.u),breakable:false)[
    #grid(columns:(60*t.u,1fr),gutter:15*t.u,align:horizon,face(t,p.avatar,size:60),[
      #copy(t,p.name,size:18.4,weight:800,lh:1.3)#v(6*t.u)
      #box(fill:rgb("e0f2f1"),radius:6*t.u,inset:(x:8*t.u,y:2*t.u),stroke:0.7*t.u+border)[#copy(t,p.title,size:11.2,weight:800,fill:dark)]#h(6*t.u)
      #box(fill:pink,radius:6*t.u,inset:(x:8*t.u,y:2*t.u))[#copy(t,p.profile,size:11.2,weight:800,fill:white,font:"Outfit")]
    ])
    #v(15*t.u)
    #block(width:100%,fill:soft,inset:15*t.u,radius:12*t.u,stroke:(paint:border,thickness:1*t.u,dash:"dashed"))[
      #if p.image!="" {place(bottom+right,image(p.image,width:110*t.u,height:100*t.u,fit:"contain"))}
      #copy(t,runs(t,p.reason),size:15.2,fill:muted,lh:1.6)
    ]
  ]))
  v(50*t.u)
}
#let quotes(t,d) = context {
  if d.quotes.len()==0 {return}
  section(t,words(d).quotes,"quote",pink-bar:true,gap:54)
  let review-label=("zh-Hans":"Miku 锐评","zh-Hant":"Miku 銳評","en":"Miku's Review","ja":"ミクのコメント").at(d.language)
  for (i,q) in d.quotes.enumerate() {
    let reverse=calc.odd(i)
    let content-width=calc.min(818*0.85-63,calc.max(measure(copy(t,runs(t,q.content),size:16.8,weight:600,lh:1.6)).width/t.u+44,measure(copy(t,runs(t,q.reason),size:14.4,fill:muted,lh:1.6)).width/t.u+36))
    align(if reverse {right}else{left})[
      #block(width:(content-width+63)*t.u)[
        #grid(columns:if reverse {(content-width*t.u,48*t.u)}else{(48*t.u,content-width*t.u)},gutter:15*t.u,
          ..(if reverse {(true,false)}else{(false,true)}).map(content=>if not content {face(t,q.avatar)} else {[
            #align(if reverse {right}else{left})[#copy(t,q.sender,size:13.6,weight:700,fill:muted)#v(6*t.u)]
            #block(width:100%,fill:white,inset:(x:22*t.u,y:16*t.u),stroke:1*t.u+border,radius:if reverse {(top-left:18*t.u,top-right:4*t.u,bottom:18*t.u)}else{(top-left:4*t.u,top-right:18*t.u,bottom:18*t.u)})[#copy(t,runs(t,q.content),size:16.8,weight:600,lh:1.6)]
            #v(12*t.u)
            #block(width:100%,fill:soft,inset:(x:18*t.u,y:12*t.u),radius:12*t.u,stroke:(left:4*t.u+pink))[
              #set align(left)
              #grid(columns:(18*t.u,1fr),gutter:8*t.u,align:horizon,icon(t,"music",size:18),copy(t,review-label,size:15.2,weight:700,fill:dark))
              #v(6*t.u)#copy(t,runs(t,q.reason),size:14.4,fill:muted,lh:1.6)
            ]
          ]}))
      ]
    ]
    if i < d.quotes.len()-1 {v(25*t.u)}
  }
  v(50*t.u)
}
#let quality(t,d) = {
  if d.review==none {return}
  let r=d.review
  let colors=(base,pink,light,rgb("fff9c4"),rgb("80cbc4"))
  section(t,words(d).review,"award")
  frame(t,inset:30,[
    #block(width:100%,inset:(bottom:15*t.u),stroke:(bottom:(paint:base.transparentize(80%),thickness:2*t.u,dash:"dashed")))[#grid(columns:(1fr,auto),align:bottom,copy(t,r.title,size:25.6,fill:dark),capsule(t,r.subtitle,size:14.4))]
    #v(25*t.u)
    #grid(columns:r.dimensions.map(x=>calc.max(0.1,x.percentage)*1fr),..r.dimensions.enumerate().map(((i,x))=>rect(width:100%,height:14*t.u,fill:colors.at(calc.rem(i,5)),stroke:none)))
    #v(30*t.u)
    #grid(columns:(1fr,1fr),gutter:15*t.u,..r.dimensions.enumerate().map(((i,x))=>block(width:100%,fill:soft,inset:(x:15*t.u,y:12*t.u),radius:10*t.u)[
      #grid(columns:(10*t.u,1fr),gutter:10*t.u,circle(radius:5*t.u,fill:colors.at(calc.rem(i,5)),stroke:none),[
        #copy(t,[#x.name (#(str(x.percentage))%)],size:14.4,weight:700)#v(4*t.u)#copy(t,runs(t,x.comment),size:13.6,fill:muted,lh:1.5)
      ])
    ]))
    #v(30*t.u)
    #block(width:100%,fill:gradient.linear(dark,base,angle:315deg),inset:25*t.u,radius:12*t.u)[
      #grid(columns:(1fr,auto),gutter:20*t.u,align:bottom,
        [#grid(columns:(20*t.u,1fr),gutter:8*t.u,align:horizon,icon(t,"mic",size:20),copy(t,words(d).verdict,size:17.6,weight:700,fill:white))#v(10*t.u)#copy(t,runs(t,r.summary),fill:white,lh:1.8)],
        deco(d,1,width:110*t.u,height:100*t.u))
    ]
  ])
  v(50*t.u)
}
#let footer(t,d) = {
  frame(t,height:114*t.u,inset:0,fill:rgb("ebf7f6"),stroke:base.transparentize(70%),[
    #block(inset:(x:30*t.u,y:20*t.u))[
      #grid(columns:(1fr,auto),gutter:15*t.u,align:horizon,
        [#icon(t,"github",size:18)#h(7*t.u)#copy(t,"SXP-Simon/astrbot_plugin_qq_group_daily_analysis",size:15.2,weight:700,fill:dark,font:"Outfit")],
        [#icon(t,"cpu",size:14)#h(6*t.u)#copy(t,[Token usage: #text(weight:800)[#d.tokens.at(0)] #text(fill:muted,size:12*t.u)[( P: #d.tokens.at(1) | C: #d.tokens.at(2) )]],size:13.6,font:"Outfit")])
      #v(15*t.u)#line(length:100%,stroke:(paint:base.transparentize(70%),thickness:1*t.u,dash:"dashed"))#v(15*t.u)
      #grid(columns:(1fr,auto),gutter:15*t.u,align:horizon,
        [#icon(t,"clock",size:14)#h(5*t.u)#copy(t,[Generated at #d.generated_at],size:12.8,fill:muted,font:"Outfit")],
        [#icon(t,"heart",size:14)#h(5*t.u)#copy(t,[#text(style:"italic")[Template by shiitin]],size:16,weight:700,fill:dark,font:"Outfit")])
    ]
  ])
}
#let render(d,t) = {
  let font=if d.at("font_language",default:d.language)=="zh-Hant" {"Noto Sans TC"} else if d.language=="ja" {"Noto Sans JP"}else{"Noto Sans SC"}
  t.insert("fonts",(font,"Noto Sans SC"))
  set page(width:d.width*t.u,height:auto,margin:0pt,fill:soft)
  set text(font:t.fonts,size:16*t.u,fill:ink,cjk-latin-spacing:none,lang:if d.language=="ja" {"ja"}else if d.language=="en" {"en"}else{"zh"})
  set par(spacing:0pt,leading:0pt)
  let paper=tiling(size:(24*t.u,24*t.u))[
    #rect(width:24*t.u,height:24*t.u,fill:white,stroke:none)
    #place(top+left,dx:12*t.u,dy:12*t.u,circle(radius:0.6*t.u,fill:base.transparentize(85%),stroke:none))
  ]
  let content=block(width:d.width*t.u,inset:(x:20*t.u,y:40*t.u))[
    #block(width:100%,inset:41*t.u,fill:paper,radius:12*t.u,stroke:1*t.u+border,clip:true)[
      #place(top+right,dx:60*t.u,dy:-20*t.u,rotate(-10deg,copy(t,"01",size:256,weight:800,fill:base.transparentize(96%),font:"Outfit",lh:1)))
      #place(bottom+left,dx:-80*t.u,dy:-180*t.u,rotate(-10deg,copy(t,"39",size:352,weight:800,fill:base.transparentize(96%),font:"Outfit",lh:1)))
      #place(top+left,dx:-10*t.u,dy:140*t.u,copy(t,[[ SYSTEM_VOCALOID_INITIALIZED ]#linebreak()HATSUNE MIKU v4X],fill:dark.transparentize(90%),font:"Outfit"))
      #heading(t,d)#stats(t,d)#peak(t,d)#activity(t,d)#topics(t,d)#portraits(t,d)#quotes(t,d)#quality(t,d)#footer(t,d)
    ]
  ]
  context {let size=measure(content); [#metadata((height:size.height/1pt))<report-size>];content}
}

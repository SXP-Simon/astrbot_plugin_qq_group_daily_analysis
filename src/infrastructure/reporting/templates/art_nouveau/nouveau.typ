// 保留 Art Nouveau 的字体、双色花饰和独立阅读顺序；矢量图标直接取自同目录 HTML。
#import "common.typ":shadow
#let bg=rgb("f5f0e1")
#let paper=rgb("fcfaf4")
#let subtle=rgb("f8f4ea")
#let primary=rgb("2d5016")
#let light=rgb("4a7c3f")
#let gold=rgb("c9a227")
#let gold-dark=rgb("967515")
#let ink=rgb("1a330e")
#let muted=rgb("5e6b52")
#let border=gold.transparentize(45%)
#let thin=gold.transparentize(70%)
#let palette=(primary,gold,rgb("8b6db5"),rgb("a0522d"),light,rgb("b8860b"),rgb("704f99"),rgb("556b2f"))
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.6,font:none,tracking:0,italic:false,oblique:false) = {
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="display" {t.display}else if font=="mono" {("JetBrains Mono",..t.display)}else{t.body}
  let baseline=if font=="mono" {.36}else if font=="display" {.302}else{.3185}
  let result=text(font:fonts,size:size*t.u,weight:weight,fill:fill,tracking:tracking*1em,style:if italic {"italic"}else{"normal"},top-edge:(lh/2+baseline)*1em,bottom-edge:-(lh/2-baseline)*1em,body)
  if oblique {
    // 逐字合成宋体斜体，避免倾斜整个长段落后裁掉右侧文字；西文保留真实斜体。
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*"): it=>box(height:lh*size*t.u,baseline:(at:top,shift:-(lh/2+baseline)*size*t.u))[#skew(ax:-12deg,origin:bottom+left,it)]
    result
  }else{result}
}
#let icon(t,name,size:20,color:primary) = image(bytes(read(name+".svg").replace("currentColor",color.to-hex())),format:"svg",width:size*t.u,height:size*t.u)
// 居中行内徽章先固定自己的盒子，投影与内容共享同一个定位参照。
#let seal(t,body,..options) = context {
  let m=measure(body)
  box(width:m.width,height:m.height)[#shadow(t,block(width:m.width,height:m.height)[#body],..options)]
}
#let rosette(t,symbol,size:17.6) = text(font:"Noto Sans Symbols 2",size:size*t.u,fill:rgb("e0bc4a"),symbol)
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
#let rule(t,color:thin,height:1) = block(width:100%,height:height*t.u,fill:color)[]
#let corners(t,width,height,page:false) = {
  let path=if page {"M10.5 54V22Q10.5 10.5 22 10.5H54 M12.5 54V22Q12.5 12.5 22 12.5H54"}else{"M5 21V11Q5 5 11 5H21"}
  let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(width)+"' height='"+str(height)+"' viewBox='0 0 "+str(width)+" "+str(height)+"'><g fill='none' stroke='#c9a227' stroke-opacity='"+(if page {"1"}else{".65"})+"' stroke-width='"+(if page {"1"}else{"2"})+"'><path d='"+path+"'/><path transform='translate("+str(width)+" 0) scale(-1 1)' d='"+path+"'/><path transform='translate(0 "+str(height)+") scale(1 -1)' d='"+path+"'/><path transform='translate("+str(width)+" "+str(height)+") scale(-1 -1)' d='"+path+"'/></g></svg>"
  image(bytes(svg),format:"svg",width:width*t.u,height:height*t.u)
}
#let frame(t,body,padx:22,pady:18,radius:16,fill:subtle,stroke:1,color:border,accent:none,left-width:none,ornaments:true,blur:0,dy:0,shadow-color:primary.transparentize(96%),height:none,watermark:none,dashed:false) = layout(size=>{
  let lw=if left-width==none {stroke}else{left-width}
  let inner=block(width:size.width,inset:(left:(padx+lw)*t.u,right:(padx+stroke)*t.u,y:(pady+stroke)*t.u))[#body]
  let m=measure(inner)
  if height!=none {m.height=calc.max(m.height,height*t.u)}
  let panel=block(width:size.width,height:m.height,fill:fill,radius:radius*t.u,stroke:(rest:stroke*t.u+color,left:lw*t.u+(if accent==none {color}else{accent})),outset:(rest:-stroke/2*t.u,left:-lw/2*t.u),clip:true)[
    #if watermark!=none and watermark.image!="" {
      let w=m.width*.36
      place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(watermark.image,width:w,height:calc.min(measure(image(watermark.image,width:w)).height,m.height*.75),fit:watermark.image_fit))
    }
    #inner
    #if dashed {place(top+left,dx:5*t.u,dy:5*t.u,rect(width:m.width - 10*t.u,height:m.height - 10*t.u,radius:13*t.u,fill:none,stroke:(paint:gold.transparentize(60%),thickness:1*t.u,dash:(array:(3*t.u,3*t.u)))))}
    #if ornaments {place(top+left,corners(t,m.width/t.u,m.height/t.u))}
  ]
  if blur>0 {shadow(t,panel,radius:radius,blur:blur,dy:dy,color:shadow-color)}else{panel}
})
#let section(t,title,subtitle,body,ornaments:false) = frame(t,padx:28,pady:24,radius:20,fill:paper,ornaments:ornaments,blur:18,dy:6,[
  #align(center,grid(columns:(90*t.u,auto,90*t.u),gutter:16*t.u,align:horizon,image("flourish.svg",width:90*t.u,height:22*t.u,fit:"contain"),[
    #copy(t,title,size:21.6,weight:700,fill:primary,font:"display",lh:1.2,tracking:.04)
    #v(2*t.u)#copy(t,subtitle,size:11.52,weight:600,fill:gold-dark,font:"display",tracking:.12)
  ],scale(x:-100%,reflow:false,image("flourish.svg",width:90*t.u,height:22*t.u,fit:"contain"))))
  #v(12*t.u)#rule(t)#v(22*t.u)#body
])
#let cameo(t,path,size:52,green:true) = {
  let accent=if green {light}else{gold}
  let outer=if green {primary}else{gold-dark}
  box(width:size*t.u,height:size*t.u,fill:white,radius:50%,stroke:2*t.u+accent,outset:-1*t.u,inset:4*t.u)[
    #place(top+left,dx:-4*t.u,dy:-4*t.u,circle(radius:(size/2+1)*t.u,stroke:2*t.u+outer,fill:none))
    #box(width:100%,height:100%,radius:50%,clip:true,fill:rgb("ede4d1"))[
      #if path!="" {image(path,width:100%,height:100%,fit:"cover")}else{align(center+horizon,icon(t,"person",size:if size==52 {26}else{20},color:gold-dark))}
    ]
  ]
}
#let header(t,d) = {
  block(width:100%,inset:(x:10*t.u,top:10*t.u,bottom:24*t.u))[
    #place(top+center,dy:-25*t.u,image("halo.svg",width:420*t.u,height:180*t.u,fit:"contain"))
    #align(center)[
      #seal(t,box(inset:(x:23*t.u,y:6*t.u),radius:100*t.u,stroke:1*t.u+gold,fill:gradient.linear(rgb("fcf6e5"),rgb("faecd0"),angle:90deg,space:rgb))[
        #copy(t,[#rosette(t,"❦")#h(10*t.u)每日群聊艺术画报 · ART NOUVEAU DAILY#h(10*t.u)#rosette(t,"❧")],size:13.6,weight:700,fill:primary,font:"display",tracking:.08)
      ],radius:100,blur:8,dy:2,color:gold.transparentize(80%))
      #v(14*t.u)
      #block(width:100%,height:50*t.u)[
        #place(top+center,dx:1*t.u,dy:1*t.u,copy(t,"群聊风雅漫步",size:40,weight:800,fill:gold.transparentize(60%),font:"display",lh:1.25,tracking:.03))
        #align(center,copy(t,"群聊风雅漫步",size:40,weight:800,fill:primary,font:"display",lh:1.25,tracking:.03))
      ]
      #v(4*t.u)#copy(t,"CHRONICLES OF NATURAL HARMONY",size:16.8,weight:600,fill:gold-dark,font:"display",tracking:.18,lh:1.25)
      #v(10*t.u)
      #box(inset:(x:15*t.u,y:5*t.u),fill:rgb("fbf8ef"),stroke:1*t.u+border,radius:100*t.u)[
        #copy(t,[#box(baseline:20%)[#icon(t,"calendar",size:14,color:gold)]#h(6*t.u)日期: #d.date],size:14.72,weight:700,fill:primary)
      ]#h(3.7*t.u)#box(inset:(x:15*t.u,y:5*t.u),fill:rgb("fbf8ef"),stroke:1*t.u+border,radius:100*t.u)[
        #copy(t,[#box(baseline:20%)[#icon(t,"clock",size:14,color:gold)]#h(6*t.u)记录时间: #d.generated_at],size:14.72,weight:700,fill:primary)
      ]
    ]
  ]
  rule(t,color:border,height:2)
}
#let statistics(t,d) = {
  let entries=(("消息总数",d.message_count,"全天交流互动频次","message"),("参与人数",d.participant_count,"今日发言群友规模","people"),("表情互动",d.emoji_count,"表情包与斗图频次","smile"),("文字体量",d.characters,"累计交流字符规模","text"))
  grid(columns:(1fr,)*4,gutter:16*t.u,..entries.enumerate().map(((i,e))=>frame(t,padx:16,pady:18,ornaments:false,dashed:true,blur:12,dy:4,align(center)[
    #seal(t,circle(radius:21*t.u,fill:if calc.even(i) {rgb("f0f6ec")}else{rgb("fdf8ee")},stroke:1*t.u+(if calc.even(i) {light}else{gold}))[
      #align(center+horizon,icon(t,e.at(3),color:if calc.even(i) {primary}else{gold-dark}))
    ],radius:21,blur:6,dy:2,color:(if calc.even(i) {primary}else{gold}).transparentize(82%))
    #v(10*t.u)#copy(t,e.at(0),size:14.08,weight:700,fill:muted,font:"display",tracking:.04)
    #v(4*t.u)#copy(t,str(e.at(1)),size:31.2,weight:700,fill:primary,font:"display",lh:1.2)
    #v(2*t.u)#copy(t,e.at(2),size:13.12,fill:if calc.even(i) {light}else{gold-dark},italic:true,oblique:true)
  ])))
}
#let peak(t,d) = frame(t,padx:24,pady:18,radius:20,stroke:2,color:gold,fill:gradient.linear((rgb("fcf8ee"),0%),(rgb("faecd0"),50%),(rgb("fcf8ee"),100%),angle:135deg,space:rgb),blur:16,dy:4,shadow-color:gold.transparentize(85%),[
  #grid(columns:(1fr,auto),gutter:16*t.u,align:horizon,
    grid(columns:(46*t.u,1fr),gutter:14*t.u,align:horizon,
      seal(t,circle(radius:23*t.u,fill:primary,stroke:2*t.u+gold)[#align(center+horizon,icon(t,"bolt",size:24,color:rgb("e0bc4a")))],radius:23,blur:10,dy:4,color:primary.transparentize(70%)),
      [#copy(t,"今日高光时段 · Peak Moments",size:16.8,weight:700,fill:primary,font:"display",tracking:.04)
      #copy(t,"思维碰撞与欢声笑语最密集的时刻",size:14.4,fill:muted,italic:true,oblique:true)]),
    seal(t,box(inset:(x:22*t.u,y:10*t.u),radius:100*t.u,fill:white,stroke:2*t.u+gold)[#copy(t,d.peak,size:24.8,weight:700,fill:primary,font:"display",tracking:.04)],radius:100,blur:8,dy:2,color:gold.transparentize(75%)))
])
#let activity(t,d) = section(t,"廿四小时走势 · 24-Hour Rhythm","THE BOTANICAL TIMELINE OF ACTIVITY",ornaments:true,[
  #let highest=calc.max(1,..d.hours)
  #block(width:100%,height:188*t.u,inset:(x:6*t.u,top:24*t.u,bottom:6*t.u))[
    #grid(columns:(1fr,)*24,gutter:0pt,..d.hours.enumerate().map(((i,n))=>block(width:100%,height:158*t.u,inset:(x:2*t.u))[
      #if n>0 {place(top+center,dy:-20*t.u,copy(t,str(n),size:11.52,weight:700,fill:gold-dark,font:"display"))}
      #let pct=n/highest
      #let height=calc.min(126.8,calc.max(4,pct*130.8))
      #let fill=if n==0 {gold.transparentize(90%)}else if pct>=.7 {gradient.linear(gold,primary,angle:90deg,space:rgb)}else if pct>=.3 {gradient.linear(light.transparentize(10%),primary.transparentize(10%),angle:90deg,space:rgb)}else{gradient.linear(rgb("8ba873").transparentize(15%),light.transparentize(15%),angle:90deg,space:rgb)}
      #block(width:100%,height:130.8*t.u)[
        #place(bottom+left,block(width:100%,height:height*t.u,radius:(top-left:4*t.u,top-right:4*t.u),fill:fill)[])
        #if n>0 {place(bottom+center,dy:(3 - height)*t.u,seal(t,circle(radius:3.5*t.u,fill:gold),radius:3.5,blur:6,color:gold.transparentize(30%)))}
      ]
      #v(8*t.u)#align(center,copy(t,(if i < 10 {"0"}else{""})+str(i),size:12,weight:700,fill:primary,font:"display"))
    ]))
  ]
  #rule(t,color:gold,height:2)
])
#let quality(t,d) = {
  let r=d.review
  section(t,"群聊氛围洞察 · Atmosphere & Quality","AESTHETIC & HARMONY ANALYSIS",ornaments:true,[
    #grid(columns:(1fr,auto),gutter:10*t.u,align:horizon,
      seal(t,box(inset:(x:19*t.u,y:7*t.u),radius:100*t.u,stroke:1*t.u+gold,fill:gradient.linear(primary,rgb("3e6922"),angle:135deg,space:rgb))[
        #copy(t,[#rosette(t,"❧")#h(8*t.u)#r.title#h(8*t.u)#rosette(t,"☙")],size:16.8,weight:700,fill:white,font:"display")
      ],radius:100,blur:12,dy:4,color:primary.transparentize(75%)),
      copy(t,r.subtitle,size:14.72,fill:muted,italic:true,oblique:true))
    #v(16*t.u)
    #block(width:100%,inset:5*t.u,stroke:2*t.u+gold,outset:-1*t.u,fill:white,radius:100*t.u)[
      #block(width:100%,height:26*t.u,radius:100*t.u,clip:true)[
        #let total=calc.max(100,r.dimensions.map(x=>x.percentage).sum(default:0))
        #grid(columns:r.dimensions.enumerate().filter(((i,x))=>x.percentage>0).map(((i,x))=>x.percentage/total*100%),gutter:0pt,..r.dimensions.enumerate().filter(((i,x))=>x.percentage>0).map(((i,x))=>block(width:100%,height:26*t.u,fill:palette.at(calc.rem(i,8)),stroke:(right:1*t.u+rgb("e0bc4a")),inset:(x:6*t.u),clip:true)[
          #align(center+horizon,copy(t,[#x.name #calc.round(x.percentage)%],size:11.52,weight:700,fill:white,font:"display"))
        ]))
      ]
    ]
    #v(16*t.u)
    #grid(columns:(1fr,1fr),gutter:12*t.u,..r.dimensions.enumerate().filter(((i,x))=>x.percentage>0).map(((i,x))=>frame(t,padx:16,pady:12,radius:9.6,fill:white,ornaments:false,blur:6,dy:2,shadow-color:gold.transparentize(92%),[
      #let color=palette.at(calc.rem(i,8))
      #let tenth=calc.round(x.percentage*10)
      #grid(columns:(1fr,auto),align:horizon,
        copy(t,[#box(width:8*t.u,height:8*t.u,radius:50%,fill:color,stroke:1*t.u+gold,baseline:25%)[]#h(6*t.u)#x.name],size:14.08,weight:700,fill:primary,font:"display"),
        copy(t,str(calc.quo(tenth,10))+"."+str(calc.rem(tenth,10))+"%",size:14.72,weight:700,fill:color,font:"display"))
      #v(6*t.u)#block(width:100%,height:5*t.u,fill:rgb("ede4d1"),radius:100*t.u,clip:true)[#rect(width:x.percentage*1%,height:5*t.u,fill:color,stroke:none,radius:100*t.u)]
      #v(8*t.u)#copy(t,runs(t,x.comment),size:13.76,fill:rgb("3b4733"),lh:1.5)
    ])))
    #if r.summary.any(x=>x.text!="" or x.avatar!="") {
      v(16*t.u)
      frame(t,padx:18,pady:14,radius:16,color:gold,fill:gradient.linear(rgb("fcf8ee"),rgb("faecd0"),angle:135deg,space:rgb),ornaments:false,[
        #grid(columns:(36*t.u,1fr),gutter:14*t.u,align:top,
          seal(t,circle(radius:18*t.u,fill:primary,stroke:1*t.u+gold)[#align(center+horizon,icon(t,"summary",size:28,color:rgb("e0bc4a")))],radius:18,blur:6,dy:2,color:primary.transparentize(75%)),
          [#copy(t,"群聊综合评述 · Atmosphere Summary",size:14.08,weight:700,fill:primary,font:"display")#v(3*t.u)
          #copy(t,runs(t,r.summary),size:14.72,fill:rgb("2b3a24"))])
      ])
    }
  ])
}
#let topics(t,d) = section(t,"核心热议话题 · Selected Topics","FLORAL CHRONICLES & DISCUSSIONS",[
  #for (i,x) in d.topics.enumerate() {
    if i>0 {v(16*t.u)}
    let green=calc.even(i)
    let color=if green {primary}else{rgb("7a5c0b")}
    frame(t,accent:if green {primary}else{gold},left-width:4,[
      #grid(columns:(auto,1fr),gutter:10*t.u,align:horizon,
        box(inset:(x:9*t.u,y:3*t.u),fill:if green {rgb("f0f6ec")}else{rgb("fdf8ee")},stroke:1*t.u+(if green {light}else{gold}),radius:4*t.u)[
          #copy(t,[#text(size:11.52*t.u,fill:primary)[№] #(if i+1 < 10 {"0"}else{""})#(i+1)],size:12.8,weight:700,fill:if green {primary}else{gold-dark},font:"display")
        ],copy(t,x.title,size:18.4,weight:700,fill:color,font:"display",lh:1.35))
      #v(8*t.u)
      #if x.contributors.any(p=>p.text!="" or p.avatar!="") {
        grid(columns:(auto,1fr),gutter:8*t.u,align:horizon,
          copy(t,[#box(baseline:20%)[#icon(t,"participant",size:13,color:if green {primary}else{gold})]#h(4*t.u)主要参与群友],size:12.48,weight:700,fill:if green {light}else{gold-dark},font:"display"),
          copy(t,runs(t,x.contributors),size:14.08,weight:700,fill:color))
        v(10*t.u)
      }
      #copy(t,runs(t,x.detail),size:15.36,fill:rgb("2b3a24"),lh:1.65)
    ])
  }
])
#let portraits(t,d) = context {
  let cards=d.portraits.enumerate().map(((i,p))=>{
    let green=calc.rem(i,4)==0 or calc.rem(i,4)==3
    let color=if green {primary}else{gold}
    let raw=if p.name=="" {"匿名群友"}else{p.name}
    let name=raw
    if measure(copy(t,raw,size:16.8,weight:700,font:"display")).width>269*t.u {
      name="…"
      let letters=raw.clusters()
      for end in range(1,letters.len()+1) {
        let candidate=letters.slice(0,end).join("")+"…"
        if measure(copy(t,candidate,size:16.8,weight:700,font:"display")).width>269*t.u {break}
        name=candidate
      }
    }
    let body=[
      #grid(columns:(52*t.u,1fr),gutter:14*t.u,align:horizon,cameo(t,p.avatar,green:green),[
        #copy(t,name,size:16.8,weight:700,fill:if green {primary}else{rgb("7a5c0b")},font:"display")#v(4*t.u)
        #par(leading:6*t.u)[
          #box(inset:(x:9*t.u,y:3*t.u),radius:4*t.u,fill:gradient.linear(if green {rgb("f0f6ec")}else{rgb("fdf8ee")},if green {rgb("e1efd6")}else{rgb("faecd0")},angle:90deg,space:rgb),stroke:1*t.u+(if green {light}else{gold}))[
            #copy(t,p.title,size:12.16,weight:700,fill:if green {primary}else{gold-dark},font:"display")
          ]#h(6*t.u)#if p.profile!="" {box(inset:(x:9*t.u,y:3*t.u),radius:4*t.u,fill:rgb("f5effc"),stroke:1*t.u+rgb("8b6db5"))[#copy(t,p.profile,size:12.16,weight:700,fill:rgb("8b6db5"),font:"display")]}
        ]
      ])
      #v(12*t.u)#frame(t,padx:14,pady:10,radius:9.6,fill:white,color:thin,left-width:3,accent:color,ornaments:false)[
        #copy(t,runs(t,p.reason),size:14.72,fill:rgb("2b3a24"),lh:1.55,italic:true,oblique:true)
      ]
    ]
    (body:body,portrait:p,height:measure(body,width:335*t.u).height/t.u+38)
  })
  section(t,"群芳雅鉴 · Portraits & Personas","THE GALLERY OF MEMBER PERSONAS",[
    #for (i,row) in cards.chunks(2).enumerate() {
      if i>0 {v(16*t.u)}
      grid(columns:(1fr,1fr),gutter:16*t.u,..row.map(c=>frame(t,padx:20,pady:18,height:calc.max(..row.map(c=>c.height)),watermark:c.portrait,c.body)))
    }
  ])
}
#let quotes(t,d) = section(t,"精选金句回响 · Golden Quotes","TIMELESS EPIGRAMS & ECHOES",[
  #for (i,q) in d.quotes.enumerate() {
    if i>0 {v(16*t.u)}
    let green=calc.even(i)
    let accent=if green {light}else{gold}
    frame(t,[
      #grid(columns:(46*t.u,1fr),gutter:14*t.u,align:top,cameo(t,q.avatar,size:46,green:green),[
        #grid(columns:(auto,1fr),gutter:8*t.u,align:horizon,
          copy(t,if q.sender=="" {"匿名群友"}else{q.sender},size:16,weight:700,fill:if green {primary}else{rgb("7a5c0b")},font:"display"),
          box(inset:(x:8*t.u,y:2*t.u),radius:4*t.u,fill:if green {rgb("f0f6ec")}else{rgb("fdf8ee")},stroke:1*t.u+accent)[#copy(t,"精彩发言",size:11.52,weight:700,fill:if green {primary}else{gold-dark},font:"display")])
        #v(8*t.u)#frame(t,padx:18,pady:12,radius:9.6,fill:white,ornaments:false)[
          #place(top+right,dy:12*t.u,copy(t,"”",size:22.4,weight:700,fill:accent,font:"display",lh:0))
          #copy(t,[#box(height:0pt,baseline:(at:bottom,shift:-5*t.u))[#copy(t,"“",size:22.4,weight:700,fill:accent,font:"display",lh:0)]#runs(t,q.content)],size:16.32,weight:700,fill:if green {ink}else{rgb("3b2a03")},lh:1.55)
        ]
        #if q.reason.any(x=>x.text!="" or x.avatar!="") {
          v(8*t.u)
          frame(t,padx:12,pady:8,radius:4,fill:if green {rgb("f5f8f0")}else{rgb("fdfaf2")},color:if green {primary.transparentize(75%)}else{thin},left-width:3,accent:if green {primary}else{gold},ornaments:false,[
            #grid(columns:(auto,1fr),gutter:8*t.u,align:top,
              copy(t,[#box(baseline:20%)[#icon(t,"star",size:12,color:accent)]#h(4*t.u)AI 观察锐评],size:12.48,weight:700,fill:if green {primary}else{gold-dark},font:"display"),
              copy(t,runs(t,q.reason),size:14.08,fill:rgb("2b3a24"),lh:1.45))
          ])
        }
      ])
    ])
  }
])
#let footer(t,d) = {
  v(10*t.u);rule(t,color:border,height:2);v(20*t.u)
  let cells=(("layers","AstrBot 群分析",[
    #copy(t,"AstrBot 群日常分析总结插件",size:13.12,fill:muted,lh:1.4)
    #copy(t,"Art Nouveau Style Template",size:11.84,fill:gold-dark,lh:1.4)
  ]),("github","开源项目",[
    #set text(hyphenate:false)
    #copy(t,underline(stroke:(paint:gold.transparentize(55%),thickness:1*t.u,dash:(array:(3*t.u,3*t.u))),offset:3*t.u)[#{"SXP-Simon/astrbot_plugin_qq_group_daily_analysis".clusters().join(sym.zws)}],size:12,fill:primary,font:"mono",lh:13.12*1.4/12)
  ]),("token","Token 消耗统计",[
    #copy(t,[总计: #text(weight:700,str(d.tokens.at(0))) Tokens],size:13.12,fill:muted,lh:1.4)
    #copy(t,[提示词: #d.tokens.at(1) / 生成: #d.tokens.at(2)],size:11.84,fill:gold-dark,lh:1.4)
  ]))
  context {
    let bodies=cells.map(c=>align(center)[
      #copy(t,[#box(baseline:20%)[#icon(t,c.at(0),size:16,color:gold)]#h(6*t.u)#c.at(1)],size:14.08,weight:700,fill:primary,font:"display")
      #v(4*t.u)#c.at(2)
    ])
    let height=calc.max(..bodies.map(body=>measure(body,width:(828 - 32)/3*t.u - 34*t.u).height/t.u+34))
    grid(columns:(1fr,)*3,gutter:16*t.u,..bodies.map(body=>frame(t,padx:16,pady:16,radius:16,ornaments:false,height:height,body)))
  }
}
#let render(d) = {
  let u=72/d.ppi*d.width/940*1pt
  let cjk=if d.font_language=="zh-Hant" {("Noto Serif TC","Noto Serif SC")}else{("Noto Serif SC","Noto Serif TC")}
  let t=(u:u,display:("Cinzel",..cjk),body:("Cormorant Garamond",..cjk))
  set page(width:940*u,height:auto,margin:0pt,fill:bg)
  set text(font:t.body,size:16*u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none)
  set par(leading:0pt,spacing:0pt)
  set page(background:layout(size=>{
    let h=size.height/u
    let texture="<svg xmlns='http://www.w3.org/2000/svg' width='940' height='"+str(h)+"' viewBox='0 0 940 "+str(h)+"'><defs><pattern id='dots' width='28' height='28' patternUnits='userSpaceOnUse'><circle cx='14' cy='14' r='.75' fill='#c9a227'/></pattern><radialGradient id='gold' cx='0' cy='0' r='1.414'><stop stop-color='#c9a227' stop-opacity='.08'/><stop offset='.6' stop-color='#c9a227' stop-opacity='0'/></radialGradient><radialGradient id='green' cx='1' cy='1' r='1.414'><stop stop-color='#2d5016' stop-opacity='.06'/><stop offset='.6' stop-color='#2d5016' stop-opacity='0'/></radialGradient></defs><rect width='940' height='100%' fill='url(#dots)'/><rect width='940' height='100%' fill='url(#gold)'/><rect width='940' height='100%' fill='url(#green)'/></svg>"
    box(width:size.width,height:size.height)[
    #place(top+left,image(bytes(texture),format:"svg",width:size.width,height:size.height))
    #place(top+left,dx:26*u,dy:64*u,shadow(t,block(width:888*u,height:size.height - 88*u),radius:20,blur:45,dy:0,color:primary.transparentize(88%)))
    #place(top+left,dx:18*u,dy:36*u,shadow(t,block(width:904*u,height:size.height - 72*u),radius:28,blur:16,dy:4,color:gold.transparentize(85%)))
    #place(top+left,dx:18*u,dy:36*u,block(width:904*u,height:size.height - 72*u,radius:28*u,stroke:2*u+gold,fill:paper,outset:-1*u)[
      #place(top+left,dx:-5*u,dy:-5*u,rect(width:914*u,height:size.height - 62*u,radius:33*u,fill:none,stroke:2*u+border))
      #place(top+left,dx:-2*u,dy:-2*u,rect(width:908*u,height:size.height - 68*u,radius:30*u,fill:none,stroke:4*u+bg))
      #place(top+left,corners(t,904,h - 72,page:true))
    ])
    ]
  }))
  block(width:940*u,inset:(x:56*u,y:78*u))[
    #header(t,d)#v(28*u)#statistics(t,d)
    #if d.peak!="" {v(28*u);peak(t,d)}
    #v(28*u)#activity(t,d)
    #if d.review!=none {v(28*u);quality(t,d)}
    #if d.topics.len()>0 {v(28*u);topics(t,d)}
    #if d.portraits.len()>0 {v(28*u);portraits(t,d)}
    #if d.quotes.len()>0 {v(28*u);quotes(t,d)}
    #v(28*u)#footer(t,d)
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

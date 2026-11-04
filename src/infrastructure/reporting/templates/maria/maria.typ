// Maria 保留自己的宋体层级、蔷薇配色、画框、花茎图表与公报阅读顺序。
#import "common.typ": shadow
#let bg=rgb("f6f1e6")
#let paper=rgb("fdfbf7")
#let subtle=rgb("f4ede1")
#let primary=rgb("233a29")
#let ink=rgb("1d3022")
#let muted=rgb("5e7063")
#let gold=rgb("c5a059")
#let gold-dark=rgb("8c6c2e")
#let gold-text=rgb("93712e")
#let border=gold.transparentize(45%)
#let thin=gold.transparentize(68%)
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.65,font:none,tracking:0,italic:false,oblique:false) = {
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="display" {t.display}else if font=="mono" {("JetBrains Mono",..t.display)}else{t.body}
  let baseline=if font=="mono" {.36}else if font=="display" {.302}else{.3185}
  let result=text(font:fonts,size:size*t.u,weight:weight,fill:fill,tracking:tracking*1em,style:if italic {"italic"}else{"normal"},top-edge:(lh/2+baseline)*1em,bottom-edge:-(lh/2-baseline)*1em)[#body]
  if oblique {
    // 逐字合成宋体斜体，避免倾斜整个长段落后裁掉右侧文字；西文保留真实斜体。
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*"): it=>box(height:lh*1em,baseline:(at:top,shift:-(lh/2+baseline)*1em))[#skew(ax:-12deg,origin:bottom+left,it)]
    result
  }else{result}
}
#let art(t,d,i,width:60,height:none) = {
  let path=d.decorations.at(i,default:"")
  if path!="" {image(path,width:width*t.u,height:if height==none {auto}else{height*t.u},fit:"contain")}
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
#let corner-overlay(t,width,height,page:false) = {
  let p=if page {"M10.5 54V22Q10.5 10.5 22 10.5H54 M12.5 54V22Q12.5 12.5 22 12.5H54"}else{"M4 20V8Q4 4 8 4H20"}
  let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(width)+"' height='"+str(height)+"' viewBox='0 0 "+str(width)+" "+str(height)+"'><g fill='none' stroke='"+gold.to-hex()+"' stroke-width='"+(if page {"1"}else{"1.5"})+"'><path d='"+p+"'/><path transform='translate("+str(width)+" 0) scale(-1 1)' d='"+p+"'/><path transform='translate(0 "+str(height)+") scale(1 -1)' d='"+p+"'/><path transform='translate("+str(width)+" "+str(height)+") scale(-1 -1)' d='"+p+"'/></g></svg>"
  image(bytes(svg),format:"svg",width:width*t.u,height:height*t.u)
}
#let frame(t,body,padx:20,pady:18,radius:13.6,fill:white,stroke:1,corners:false,background:none,background-width:58,background-x:14,background-y:10,blur:8,dy:2,opacity:97%,height:none) = layout(size=>{
  let inner=block(width:size.width,inset:(x:(padx+stroke)*t.u,y:(pady+stroke)*t.u))[#body]
  let m=measure(inner)
  if height!=none {m.height=calc.max(m.height,height*t.u)}
  let panel=block(width:size.width,height:m.height,fill:fill,stroke:stroke*t.u+border,outset:-stroke/2*t.u,radius:radius*t.u,clip:true)[
    #if background!=none {place(top+left,dx:m.width - (background-width+background-x)*t.u,dy:m.height - measure(background).height - background-y*t.u,background)}
    #inner
    #if corners {place(top+left,corner-overlay(t,m.width/t.u,m.height/t.u))}
  ]
  shadow(t,panel,radius:radius,blur:blur,dy:dy,color:primary.transparentize(opacity))
})
#let section(t,title,badge,subtitle,body,quality:false) = {
  let heading=align(center)[
    #copy(t,badge,size:11.52,weight:700,fill:gold-dark,font:"display",tracking:.16)#v(2*t.u)
    #copy(t,title,size:23.2,weight:700,fill:primary,font:"display",tracking:.03)#v(2*t.u)
    #copy(t,subtitle,size:12,fill:muted,font:"display",tracking:.12)
  ]
  frame(t,padx:22,pady:24,radius:20,fill:paper,stroke:1.5,blur:16,dy:4,opacity:95%,[
    #layout(size=>{
      let w=measure(heading).width
      let wing=calc.min(140,(size.width/t.u - w/t.u - 32)/2)
      align(center,grid(columns:(wing*t.u,auto,wing*t.u),gutter:16*t.u,align:horizon,image(if quality {"flourish-quality-left.svg"}else{"flourish.svg"},width:wing*t.u),heading,image(if quality {"flourish-quality-right.svg"}else{"flourish.svg"},width:wing*t.u)))
    })
    #v(22*t.u)#body
  ])
}
#let number(n) = str(n).clusters().rev().chunks(3).map(x=>x.rev().join("")).rev().join(",")
#let hero(t,d) = {
  grid(columns:(1fr,auto),align:horizon,
    copy(t,[#text(fill:gold,size:19.2*t.u)[✝]#h(10*t.u)LILLIAN GIRLS' ACADEMY · YAMAYURIKAI],size:15.2,weight:700,fill:primary,font:"display",tracking:.08),
    box(inset:(x:15*t.u,y:5*t.u),fill:subtle,stroke:1*t.u+border,radius:100*t.u)[#copy(t,"✿ ごきげんよう",size:13.6,weight:600,fill:rgb("38553f"),tracking:.05)])
  v(14*t.u);line(length:100%,stroke:(paint:thin,thickness:1*t.u,dash:"dashed"));v(20*t.u)
  grid(columns:(1.15fr,.85fr),gutter:24*t.u,align:horizon,[
    #copy(t,[#box(width:30*t.u,height:1*t.u,fill:gold)#h(8*t.u)MARIA-SAMA GA MITERU · DAILY SALON#h(8*t.u)#box(width:30*t.u,height:1*t.u,fill:gold)],size:13.12,weight:700,fill:gold-text,font:"display",tracking:.14)
    #v(14*t.u)#layout(size=>{
      place(top+left,dx:1*t.u,dy:1*t.u,copy(t,"莉莉安茶会 · 今日群聊公报",size:37.6,weight:800,fill:gold.transparentize(65%),font:"display",lh:1.25,tracking:.04))
      copy(t,"莉莉安茶会 · 今日群聊公报",size:37.6,weight:800,fill:primary,font:"display",lh:1.25,tracking:.04)
    })
    #v(4*t.u)#copy(t,"BULLETIN DU SALON DES ROSES",size:16.8,weight:600,fill:gold-dark,font:"display",tracking:.12,lh:1.25)
    #v(14*t.u)#block(inset:(left:16.5*t.u),stroke:(left:2.5*t.u+gold))[
      #copy(t,"「ごきげんよう。今日もマリア様が見守ってくださる庭園で、心穏やかな時間をお過ごしください。」",size:15.68,lh:1.8,fill:muted,italic:true,oblique:true)
    ]
    #v(18*t.u)#box(fill:subtle,stroke:1*t.u+border,radius:13.6*t.u,inset:(x:19*t.u,y:9*t.u))[
      #copy(t,[#text(size:12.48*t.u,fill:muted)[公报日期]#h(12*t.u)#text(font:t.display,size:15.2*t.u,weight:700,fill:primary,d.date)],size:15.2)
    ]
  ],layout(size=>{
    let w=size.width/t.u
    block(width:size.width,height:320*t.u)[
      #place(top+left,dx:-5*t.u,dy:-5*t.u,rect(width:(w+10)*t.u,height:330*t.u,radius:(top-left:180*t.u,top-right:180*t.u,bottom-left:21*t.u,bottom-right:21*t.u),stroke:2*t.u+border,fill:none))
      #block(width:100%,height:100%,radius:(top-left:175*t.u,top-right:175*t.u,bottom-left:16*t.u,bottom-right:16*t.u),stroke:2*t.u+gold,outset:-1*t.u,fill:gradient.radial((white,0%),(rgb("f7f1e4"),70%),(rgb("eddcc2"),100%),center:(50%,35%),radius:85%,space:rgb),clip:true)[
        #place(top+center,dy:22*t.u,circle(radius:113*t.u,stroke:1.5*t.u+gold.transparentize(70%),fill:none))
        #place(top+center,dy:18.5*t.u,circle(radius:116.5*t.u,stroke:1*t.u+gold.transparentize(86%),fill:none))
        #align(center+horizon)[#art(t,d,0,width:(w - 24)*.9)]
      ]
      #place(bottom+center,dy:10*t.u,box(fill:gradient.linear(paper,rgb("f5efe4"),angle:90deg,space:rgb),stroke:1*t.u+gold,radius:100*t.u,inset:(x:20*t.u,y:4*t.u))[
        #copy(t,"『マリア様がみてる』",size:13.12,weight:700,fill:primary,tracking:.06)
      ])
    ]
  }))
  v(24*t.u);line(length:100%,stroke:2*t.u+border)
}
#let statistics(t,d) = {
  let stats=(("消息总数",d.message_count,"条温存私语"),("登校群友",d.participant_count,"位出席淑女"),("交流字数",d.characters,"字优雅谈吐"),("表情互动",d.emoji_count,"次嫣然笑颜"))
  grid(columns:(1fr,1fr,1fr,1fr),gutter:14*t.u,..stats.enumerate().map(((i,s))=>{
    let gap=if i < 3 {(29.04 - 19.008)/3}else{0}
    frame(t,padx:14,pady:16,fill:subtle,stroke:1.5,corners:true,background:if i < 3 {art(t,d,8+i,width:48,height:48)}else{none},background-width:48,background-x:-6,background-y:-6,blur:10,dy:3,opacity:96%,[
    #grid(columns:(1fr,auto),align:horizon,copy(t,[№ #("0"+str(i+1))],size:11.52,font:"display",weight:700,fill:gold-dark,tracking:.1),if i < 3 {art(t,d,1+i,width:18,height:18)}else{image("emblem.svg",width:15.89*t.u,height:29.04*t.u)})
    #v((6+gap)*t.u)#copy(t,s.at(0),size:13.6,weight:600,fill:muted)
    #v((4+gap)*t.u)#copy(t,number(s.at(1)),size:29.6,weight:700,fill:primary,font:"display",lh:1.2)
    #v((2+gap)*t.u)#copy(t,s.at(2),size:12.16,weight:600,fill:gold-text)
  ])}))
  if d.peak!="" {
    v(14*t.u)
    block(width:100%,inset:(x:19*t.u,y:11*t.u),fill:gradient.linear(paper,subtle,space:rgb),radius:13.6*t.u,stroke:1*t.u+border)[
      #grid(columns:(1fr,auto),align:horizon,
        copy(t,[#text(fill:gold,size:17.6*t.u)[❦]#h(10*t.u)学园最喧闹时刻：#h(10*t.u)#text(font:t.display,weight:700,fill:primary,d.peak)],size:14.08),
        copy(t,"微风吹拂的午后庭院",size:12.8,fill:muted))
    ]
  }
}
#let handover(t,d) = frame(t,padx:26,pady:18,fill:gradient.linear(paper,subtle,angle:45deg,space:rgb),radius:20,stroke:1.5,background:art(t,d,5,width:170),background-width:170,background-x:12,background-y:-15,blur:10,opacity:96%,[
  #grid(columns:(86*t.u,1fr),gutter:22*t.u,align:horizon,
    box(width:86*t.u,height:86*t.u,fill:white,stroke:2*t.u+gold,radius:50%,inset:4*t.u,clip:true)[#if d.decorations.at(4,default:"")!="" {image(d.decorations.at(4),width:100%,height:100%,fit:"cover")}],
    [#copy(t,"LILLIAN HERITAGE · 学园寄语",size:11.52,weight:700,fill:gold-dark,tracking:.12)#v(4*t.u)
    #copy(t,"『タイが曲がっていてよ』",size:17.28,weight:700,fill:primary,font:"display")#v(4*t.u)
    #copy(t,"「无论何时，都要保持整洁与优雅。愿今日茶会中的每一次相逢，皆如蔷薇盛放般恒久芬芳。」",size:14.08,fill:muted,lh:1.7,italic:true,oblique:true)])
])
#let activity(t,d) = section(t,"钟楼时刻 · 24小时作息","HORLOGE DE L'ACADÉMIE","24-HOUR ACTIVITY DISTRIBUTION",[
  #let highest=calc.max(1,..d.hours)
  #block(width:100%,height:160*t.u,inset:(top:10*t.u,x:6*t.u))[
    #grid(columns:(1fr,)*24,gutter:6*t.u,..d.hours.enumerate().map(((hour,n))=>{
      let percent=n/highest
      let stem=if n==0 {gold.transparentize(91.25%)}else if percent>=.7 {gradient.linear((rgb("ba6f7c").transparentize(5%),0%),(rgb("caa96e").transparentize(5%),45%),(rgb("344d3b").transparentize(5%),100%),angle:90deg,space:rgb)}else if percent>=.35 {gradient.linear(rgb("caa96e").transparentize(12%),rgb("46634d").transparentize(12%),angle:90deg,space:rgb)}else{gradient.linear(rgb("8ba891").transparentize(20%),rgb("46634d").transparentize(20%),angle:90deg,space:rgb)}
      block(height:150*t.u,width:100%)[
        #if n>0 {align(center,copy(t,str(n),size:10.4,weight:700,fill:primary,font:"mono"))}
        #place(bottom+center,dy:-23.95*t.u,block(width:6*t.u,height:if n==0 {4*t.u}else{percent*105.89*t.u},fill:stem,radius:(top-left:3*t.u,top-right:3*t.u,bottom-left:1*t.u,bottom-right:1*t.u))[
          #if n>0 {place(top+center,dy:-3*t.u,circle(radius:3*t.u,stroke:1*t.u+rgb("b88d3e"),fill:gradient.radial((rgb("f2e2c4"),0%),(rgb("caa05a"),60%),(rgb("997532"),100%),center:(35%,35%),space:rgb)))}
        ])
        #place(bottom+center,copy(t,(if hour < 10 {"0"}else{""})+str(hour),size:10.88,weight:600,fill:muted,font:"display"))
      ]
    }))
  ]
])
#let topics(t,d) = {
  if d.topics.len()==0 {return}
  section(t,"花语拾遗 · 核心议题","YAMAYURIKAI CHRONICLES","LES DISCUSSIONS DU SALON DES ROSES",[
    #for (i,topic) in d.topics.enumerate() {
      let rose=calc.rem(i,3)
      frame(t,corners:true,background:art(t,d,8+rose,width:58,height:58),[
        #grid(columns:(auto,1fr),gutter:10*t.u,align:horizon,
          box(fill:subtle,stroke:1*t.u+border,radius:4*t.u,inset:(x:9*t.u,y:3*t.u))[
            #copy(t,[#box(width:14*t.u,height:14*t.u,baseline:20%)[#art(t,d,1+rose,width:14,height:14)]#h(5*t.u)#text(size:15.2*t.u,fill:gold-dark)[№]#h(5*t.u)#if i+1 < 10 {"0"}#(i+1)],size:13.6,weight:700,fill:primary,font:"display")
          ],copy(t,topic.title,size:18.4,weight:700,fill:primary,font:"display",lh:1.35))
        #v(10*t.u)#line(length:100%,stroke:(paint:thin,thickness:1*t.u,dash:"dashed"))#v(10*t.u)
        #copy(t,runs(t,topic.detail),size:15.04,lh:1.8)
        #if topic.contributors.map(x=>x.text).join("")!="" or topic.contributors.any(x=>x.avatar!="") {
          v(14*t.u)
          copy(t,[#box(fill:subtle,stroke:1*t.u+thin,radius:100*t.u,inset:(x:9*t.u,y:2*t.u))[
            #box(width:12*t.u,height:12*t.u,baseline:20%)[#image("participant.svg",width:12*t.u,height:12*t.u)]#h(4*t.u)#text(size:12.16*t.u,weight:600,fill:primary)[出席讨论]
          ]#h(8*t.u)#runs(t,topic.contributors)],size:13.12,fill:muted)
        }
      ])
      if i < d.topics.len()-1 {v(16*t.u)}
    }
  ])
}
#let portraits(t,d) = context {
  if d.portraits.len()==0 {return}
  section(t,"学园名册 · 淑女风采","PORTRAITS OF SŒURS","TABLEAU DES PERSONNALITÉS DU SALON",[
    #let cards=d.portraits.enumerate().map(((i,p))=>{
      let body=[
      #grid(columns:(58*t.u,1fr),gutter:14*t.u,align:horizon,
        box(width:58*t.u,height:68*t.u)[
          #place(top+left,dx:-3*t.u,dy:-3*t.u,ellipse(width:64*t.u,height:74*t.u,fill:none,stroke:1*t.u+border))
          #place(top+left,dx:-2*t.u,dy:-2*t.u,ellipse(width:62*t.u,height:72*t.u,fill:none,stroke:2*t.u+white))
          #ellipse(width:58*t.u,height:68*t.u,fill:subtle,stroke:2*t.u+gold,inset:0pt)[
            #if p.avatar!="" {align(center+horizon,image(p.avatar,width:50*t.u,height:60*t.u))}else{align(center+horizon,copy(t,if p.name=="" {"✿"}else{p.name.first()},size:22.4,fill:gold-dark))}
          ]
        ],[
          #let name=if p.name=="" {"匿名群友"}else{p.name}
          #let letters=name.clusters()
          #while letters.len()>0 and measure(copy(t,name,size:16.8,weight:700,font:"display")).width>272.5*t.u {
            let _=letters.pop()
            name=letters.join()+"…"
          }
          #copy(t,name,size:16.8,weight:700,fill:primary,font:"display")#v(5*t.u)
          #box(fill:gradient.linear(rgb("fdf6e6"),rgb("f7ecd2"),angle:45deg,space:rgb),stroke:1*t.u+gold,inset:(x:9*t.u,y:3*t.u),radius:4*t.u)[#copy(t,[#box(width:12*t.u,height:12*t.u,baseline:20%)[#art(t,d,1+calc.rem(i,3),width:12,height:12)]#h(4*t.u)#p.title],size:12,weight:700,fill:gold-dark)]
          #h(5*t.u)
          #if p.mbti!="" {box(fill:white,stroke:1*t.u+rgb("5a7288").transparentize(65%),inset:(x:7*t.u,y:3*t.u),radius:4*t.u)[#copy(t,p.mbti,size:11.52,weight:700,fill:rgb("5a7288"),font:"mono")]}
        ])
      #if p.reason.map(x=>x.text).join("")!="" {v(10*t.u);line(length:100%,stroke:(paint:thin,thickness:1*t.u,dash:"dashed"));v(8*t.u);copy(t,runs(t,p.reason),size:14.08,fill:muted,lh:1.75)}
      ]
      (portrait:p,body:body,height:measure(body,width:344.5*t.u).height/t.u+34)
    })
    #for (i,row) in cards.chunks(2).enumerate() {
      let height=calc.max(..row.map(x=>x.height))
      grid(columns:(1fr,1fr),gutter:16*t.u,..row.map(x=>frame(t,x.body,padx:18,pady:16,corners:true,height:height,background:if x.portrait.image!="" {image(x.portrait.image,width:145.35*t.u,height:calc.min(measure(image(x.portrait.image,width:145.35*t.u)).height,height*.75*t.u),fit:"contain")}else{none},background-width:145.35,background-x:4,background-y:4)))
      if i < calc.ceil(cards.len()/2)-1 {v(16*t.u)}
    }
  ])
}
#let quotes(t,d) = {
  if d.quotes.len()==0 {return}
  section(t,"蔷薇私语 · 今日金句","WORDS OF ROSES","PENSÉES & CITATIONS D'OR",[
    #for (i,q) in d.quotes.enumerate() {
      frame(t,padx:22,pady:18,corners:true,background:art(t,d,8+calc.rem(i,3),width:54,height:54),background-width:54,background-x:16,background-y:10,[
        #grid(columns:(auto,1fr,auto),gutter:10*t.u,align:top,
          copy(t,"“",size:35.2,fill:gold.transparentize(30%),font:"display",lh:1),
          copy(t,runs(t,q.content),size:16.8,weight:600,fill:primary,lh:1.8,italic:true,oblique:true),
          copy(t,"”",size:35.2,fill:gold.transparentize(30%),font:"display",lh:1))
        #v(12*t.u)#line(length:100%,stroke:(paint:thin,thickness:1*t.u,dash:"dashed"))#v(10*t.u)
        #copy(t,[#box(width:26*t.u,height:26*t.u,fill:subtle,stroke:1*t.u+gold,radius:50%,clip:true,baseline:25%)[#if q.avatar!="" {image(q.avatar,width:100%,height:100%,fit:"cover")}else{align(center+horizon)[✿]}]#h(8*t.u)#text(font:t.display,weight:700,if q.sender=="" {"匿名群友"}else{q.sender})],size:14.4,fill:primary)
        #if q.reason.map(x=>x.text).join("")!="" or q.reason.any(x=>x.avatar!="") {v(6*t.u);copy(t,[#text(fill:gold)[——]#h(4*t.u)#runs(t,q.reason)],size:13.12,fill:muted,italic:true,oblique:true)}
      ])
      if i < d.quotes.len()-1 {v(16*t.u)}
    }
  ])
}
#let quality(t,d) = {
  if d.review==none {return}
  let r=d.review
  section(t,if r.title!="" {r.title}else{"学园庭园的省察 · 群聊质感"},"SALON EVALUATION & HARMONIE",if r.subtitle!="" {r.subtitle}else{"REVUE DE LA QUALITÉ DU SALON"},quality:true,[
    #grid(columns:(190*t.u,1fr),gutter:22*t.u,align:horizon,
      align(center)[
        #block(width:170*t.u,height:220*t.u)[
          #place(top+left,dx:-4*t.u,dy:-4*t.u,rect(width:178*t.u,height:228*t.u,radius:(top-left:89*t.u,top-right:89*t.u,bottom-left:16*t.u,bottom-right:16*t.u),fill:none,stroke:1.5*t.u+border))
          #block(width:100%,height:100%,fill:gradient.radial((white,0%),(subtle,80%),(rgb("eadbc5"),100%),center:(50%,30%),radius:85%,space:rgb),radius:(top-left:85*t.u,top-right:85*t.u,bottom-left:12*t.u,bottom-right:12*t.u),stroke:2*t.u+gold,clip:true)[
          #place(top+center,dy:18*t.u,circle(radius:60*t.u,stroke:1.2*t.u+gold.transparentize(66%),fill:gradient.radial(white.transparentize(50%),subtle.transparentize(80%),white.transparentize(100%),space:rgb)))
          #place(top+center,dy:14*t.u,circle(radius:64*t.u,stroke:1*t.u+gold.transparentize(83%),fill:none))
          #align(center+horizon)[#art(t,d,6,width:153,height:195)]
          ]
        ]
        #v(8*t.u)#copy(t,"『窓辺の静かな省察』",size:12.48,weight:600,fill:muted)
        #v(10*t.u)#copy(t,"✦ 私語",size:10.4,fill:gold.transparentize(50%))
      ],[
        #if r.dimensions.len()>0 {
          grid(columns:(1fr,1fr),column-gutter:18*t.u,row-gutter:12*t.u,..r.dimensions.map(x=>[
            #grid(columns:(1fr,auto),gutter:4*t.u,align:horizon,copy(t,x.name,size:14.08,weight:600,fill:primary),copy(t,[#x.percentage%],size:14.08,weight:700,fill:gold-dark,font:"mono"))
            #v(6*t.u)
            #block(width:100%,height:8*t.u,fill:subtle,stroke:1*t.u+thin,radius:100*t.u,inset:1*t.u,clip:true)[#block(width:x.percentage*1%,height:6*t.u,fill:gradient.linear(gold,rgb("38553f"),space:rgb),radius:100*t.u)]
            #if x.comment.map(p=>p.text).join("")!="" {v(6*t.u);copy(t,runs(t,x.comment),size:12.8,fill:muted,lh:1.6)}
          ]))
        }
        #if r.summary.map(x=>x.text).join("")!="" {
          if r.dimensions.len()>0 {v(16*t.u)}
          block(width:100%,inset:(x:17*t.u,y:15*t.u),fill:subtle,stroke:1*t.u+border,radius:13.6*t.u)[
            #grid(columns:(20*t.u,1fr),gutter:12*t.u,align:top,copy(t,"✿",size:19.2,fill:gold,lh:1),[
              #copy(t,"总评纪要 · Conclusion du Salon",size:14.72,weight:700,fill:primary,font:"display")#v(3*t.u)
              #copy(t,runs(t,r.summary),size:13.76,lh:1.7)
            ])
          ]
        }
      ])
  ])
}
#let receipt(t,d) = frame(t,padx:20,pady:12,fill:subtle,stroke:1.5,[
  #grid(columns:(80*t.u,1fr,90*t.u,110*t.u),gutter:16*t.u,align:horizon,
    align(center)[#image("fleur.svg",width:22.55*t.u,height:42.24*t.u)#v(4*t.u)#copy(t,"MEMOIRE",size:12,weight:700,fill:gold-dark,font:"display",tracking:.1)],
    [#copy(t,"茶会纪要消耗 · TOKEN CONSOMMATION",size:12.48,weight:600,fill:muted,tracking:.06)#v(4*t.u)
      #if d.tokens.at(0)>0 {
        copy(t,[#text(font:t.display,weight:700,size:28.8*t.u,fill:primary,number(d.tokens.at(0)))#h(8*t.u)#text(size:12.8*t.u,weight:600,fill:gold-dark)[Tokens]],size:28.8,lh:1.65)
        v(4*t.u);copy(t,[输入 #number(d.tokens.at(1)) ／ 输出 #number(d.tokens.at(2))],size:12.48,fill:muted)
      }else{copy(t,"本次茶会未产生额外消耗",size:14.4,fill:muted)}
    ],art(t,d,7,width:90,height:68),
    block(inset:(left:14*t.u),stroke:(left:(paint:border,thickness:1*t.u,dash:"dashed")))[#align(center)[
      #copy(t,"莉莉安之苑",size:14.08,weight:700,fill:rgb("38553f"),font:"display",tracking:.08)#v(2*t.u)#copy(t,"纯洁与典雅",size:11.52,fill:muted)
    ]])
])
#let footer(t,d) = {
  line(length:100%,stroke:1.5*t.u+border);v(22*t.u)
  grid(columns:(319*t.u,268*t.u,1fr),gutter:16*t.u,align:horizon,[
    #copy(t,"私立莉莉安女学园 · 山百合会公报",size:14.72,weight:700,fill:primary,font:"display",tracking:.04)#v(2*t.u)
    #copy(t,[Maria-sama ga Miteru Theme · #underline[Templated by \@HelianNuits]],size:12,fill:gold-text)
  ],box(fill:gradient.linear(white,subtle,angle:45deg,space:rgb),stroke:1*t.u+gold,radius:100*t.u,inset:(x:18*t.u,y:6*t.u))[
    #grid(columns:(15*t.u,auto,auto),gutter:9*t.u,align:horizon,image("github.svg",width:15*t.u),align(center)[
      #copy(t,"LILLIAN ATELIER",size:13.12,weight:700,fill:primary,font:"display",tracking:.08,lh:1.25)
      #copy(t,"astrbot_plugin_qq_group_daily_analysis",size:10.88,fill:muted,tracking:.05,lh:1.25)
    ],copy(t,"❦",size:14.4,fill:gold))
  ],align(right)[#copy(t,"AstrBot 群聊日常分析总结插件",size:12.48,fill:muted)#v(2*t.u)#copy(t,d.generated_at,size:12.48,fill:muted)])
}
#let render(d,t) = {
  let serif=if d.font_language=="zh-Hant" {"Noto Serif TC"}else{"Noto Serif SC"}
  t.insert("display",("Cinzel",serif));t.insert("body",("Cormorant Garamond",serif))
  set page(width:940*t.u,height:auto,margin:0pt,fill:bg)
  set text(font:t.body,size:16*t.u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none)
  set par(leading:0pt,spacing:0pt)
  let dots=tiling(size:(30*t.u,30*t.u))[
    #place(top+left,dx:14.25*t.u,dy:14.25*t.u,circle(radius:.75*t.u,fill:gold,stroke:none))
  ]
  set page(background:rect(width:100%,height:100%,fill:dots,stroke:none))
  let inner=[
    #hero(t,d)#v(28*t.u)#statistics(t,d)#v(28*t.u)#handover(t,d)#v(28*t.u)#activity(t,d)
    #if d.topics.len()>0 {v(28*t.u);topics(t,d)}
    #if d.portraits.len()>0 {v(28*t.u);portraits(t,d)}
    #if d.quotes.len()>0 {v(28*t.u);quotes(t,d)}
    #if d.review!=none {v(28*t.u);quality(t,d)}
    #v(28*t.u)#receipt(t,d)#v(28*t.u)#footer(t,d)
  ]
  let body=block(width:940*t.u,inset:(x:18*t.u,y:36*t.u))[
    #layout(size=>{
      let content=block(width:size.width,inset:(x:38*t.u,y:42*t.u))[#inner]
      let m=measure(content)
      place(top+left,dx:-6*t.u,dy:-6*t.u,rect(width:m.width+12*t.u,height:m.height+12*t.u,radius:31.6*t.u,fill:none,stroke:1.5*t.u+border))
      shadow(t,block(width:size.width,height:m.height,radius:25.6*t.u,fill:paper,stroke:2*t.u+gold,outset:-1*t.u)[
        #content
        #place(top+left,corner-overlay(t,m.width/t.u,m.height/t.u,page:true))
      ],radius:25.6,dy:20,blur:45,color:primary.transparentize(86%))
    })
  ]
  body
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

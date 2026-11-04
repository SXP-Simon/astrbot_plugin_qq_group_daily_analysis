// 阿洛娜作战报告保留独立信息卡、双色对话气泡和原版图表配色。
#import "common.typ":shadow
#let blue=rgb("3593f3")
#let cyan=rgb("58c3e5")
#let pale=rgb("b3e5fc")
#let ink=rgb("3a456e")
#let secondary=rgb("6b7a99")
#let muted=rgb("99a8c0")
#let border=rgb("d0dff0")
#let pink=rgb("f06292")
#let purple=rgb("7c6ff7")
#let orange=rgb("ff9800")
#let green=rgb("66bb6a")
#let blend(a:blue,b:cyan)=gradient.linear(a,b,angle:45deg)
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.6,tracking:0)=text(font:t.fonts,size:size*t.u,weight:if weight>=700 {700}else{600},fill:fill,tracking:tracking*t.u,top-edge:(lh/2+.35)*1em,bottom-edge:-(lh/2-.35)*1em,body)
#let icon(t,name,size:18,color:white)=image(bytes(read(name+".svg").replace("currentColor",color.to-hex())),format:"svg",width:size*t.u,height:size*t.u)
#let runs(t,parts)={
  for part in parts {
    if part.avatar!="" {
      h(2*t.u)
      box(inset:(left:3*t.u,right:7*t.u,y:3*t.u),radius:12*t.u,fill:black.transparentize(95%),stroke:1*t.u+black.transparentize(90%),baseline:(at:bottom,shift:7*t.u))[
        #set text(top-edge:.85em,bottom-edge:-.15em)
        #box(width:18*t.u,height:18*t.u,radius:50%,clip:true,baseline:25%)[#image(part.avatar,width:100%,height:100%,fit:"cover")]
        #if part.text!="" {h(4*t.u);text(size:.85em,weight:600,part.text)}
      ]
      h(2*t.u)
    }else{for (i,line) in part.text.split("\n").enumerate(){if i > 0 {linebreak()};line}}
  }
}
#let panel(t,body,inset:28,radius:16,fill:white,stroke:border,blur:8,dy:2,color:black.transparentize(96%),height:auto,corners:none)=shadow(t,radius:radius,blur:blur,dy:dy,color:color,
  block(width:100%,height:height,inset:(inset+1)*t.u,radius:if corners==none {radius*t.u}else{corners},fill:fill,stroke:1*t.u+stroke,outset:-.5*t.u)[#body])
#let heading(t,name,title,centered:false)={
  align(if centered {center}else{left},grid(columns:(32*t.u,auto),gutter:10*t.u,align:horizon,
    box(width:32*t.u,height:32*t.u,radius:8*t.u,fill:blend())[#align(center+horizon,icon(t,name))],
    copy(t,title,size:20.8,weight:700)))
  v(16*t.u)
}
#let avatar(t,path,size:56,thickness:3,halo:none)=box(width:size*t.u,height:size*t.u)[
  #if halo!=none {place(top+left,dx:-3*t.u,dy:-3*t.u,circle(radius:(size/2+3)*t.u,fill:halo,stroke:none))}
  #box(width:100%,height:100%,radius:50%,fill:rgb("dbedfd"),stroke:thickness*t.u+pale,outset:-thickness/2*t.u,inset:thickness*t.u,clip:true)[
    #if path!="" {box(width:100%,height:100%,radius:50%,clip:true)[#image(path,width:100%,height:100%,fit:"cover")]}else{align(center+horizon,icon(t,"user",size:32,color:muted))}
  ]
]
#let header(t,d)=context {
  let speech=box(inset:(x:20*t.u,y:14*t.u),radius:16*t.u,fill:white,stroke:2*t.u+pale,outset:-1*t.u)[#copy(t,"老师，这是今天的作战报告！",size:15.2)]
  let speech-width=measure(speech).width/t.u
  grid(columns:((128+speech-width)*t.u,1fr),gutter:24*t.u,align:horizon,[
    #grid(columns:(128*t.u,speech-width*t.u),align:top,
      box(width:140*t.u)[#if d.decorations.at(0,default:"")!="" {
        let path=d.decorations.at(0)
        let height=measure(image(path,width:140*t.u)).height/t.u
        box(width:140*t.u,height:height*t.u)[
          #let svg="<svg xmlns='http://www.w3.org/2000/svg' width='204' height='"+str(height+64)+"'><defs><filter id='s' filterUnits='userSpaceOnUse' x='0' y='0' width='204' height='"+str(height+64)+"'><feGaussianBlur in='SourceAlpha' stdDeviation='8' result='blur'/><feOffset in='blur' dy='4' result='offset'/><feFlood flood-color='#347ceb' flood-opacity='.25' result='color'/><feComposite in='color' in2='offset' operator='in' result='shadow'/><feMerge><feMergeNode in='shadow'/><feMergeNode in='SourceGraphic'/></feMerge></filter></defs><image href='"+path+"' x='32' y='32' width='140' height='"+str(height)+"' filter='url(#s)'/></svg>"
          #place(top+left,dx:-32*t.u,dy:-32*t.u,image(bytes(svg),format:"svg",width:204*t.u,height:(height+64)*t.u))
        ]
      }else{box(width:140*t.u,height:140*t.u)[#align(center+horizon,icon(t,"user",size:64,color:pale))]}],
      pad(top:8*t.u,shadow(t,radius:16,blur:12,dy:2,color:rgb("347ceb").transparentize(88%),[
        #place(top+left,dx:-11*t.u,dy:16*t.u,polygon(fill:pale,stroke:none,(0pt,10*t.u),(13*t.u,0pt),(13*t.u,20*t.u)))
        #place(top+left,dx:-7*t.u,dy:16*t.u,polygon(fill:white,stroke:none,(0pt,10*t.u),(10*t.u,0pt),(10*t.u,20*t.u)))
        #speech
      ])))
  ],[
    #rect(width:80*t.u,height:4*t.u,radius:2*t.u,fill:gradient.linear(blue,cyan),stroke:none)#v(8*t.u)
    #copy(t,"阿洛娜的今日群聊速报！",size:35.2,weight:700,fill:blue,tracking:.5)#v(8*t.u)
    #box(inset:(x:25*t.u,y:7*t.u),radius:20*t.u,fill:blend(a:rgb("d5eefc"),b:rgb("dbedfd")),stroke:1*t.u+pale,outset:-.5*t.u)[#copy(t,d.date,size:15.2,fill:rgb("2b6cc4"))]
  ])
  v(48*t.u)
}
#let statistics(t,d)=context {
  let entries=(("message","消息总数",d.message_count,blue,cyan),("users","参与人数",d.participant_count,green,rgb("81c784")),("smile","表情统计",d.emoji_count,pink,rgb("f48fb1")),("document","总字符数",d.characters,purple,rgb("b39ddb")))
  let card(e)=panel(t,inset:0,block(width:100%,inset:(x:16*t.u,y:20*t.u))[
    #align(center)[
      #box(width:40*t.u,height:40*t.u,radius:10*t.u,fill:blend(a:e.at(3),b:e.at(4)))[#align(center+horizon,icon(t,e.at(0),size:22))]#v(14*t.u)
      #copy(t,str(e.at(2)),size:32,weight:700,lh:1)#v(4*t.u)
      #copy(t,e.at(1),size:13.6,fill:muted)
    ]
  ])
  // CSS 按内容盒分配 2:1 的剩余宽度，高峰卡另有左右共 50px 的内边距与边框。
  let peak-width=(818 - 20 - 50)/3+50
  grid(columns:(1fr,peak-width*t.u),gutter:20*t.u,align:horizon,
    grid(columns:(1fr,1fr),gutter:16*t.u,..entries.map(card)),
    layout(size=>{
      let height=measure(grid(columns:(1fr,1fr),gutter:16*t.u,..entries.map(card)),width:(818*t.u - 20*t.u - size.width)).height
      shadow(t,radius:16,blur:12,dy:0,color:blue.transparentize(75%),block(width:100%,height:height,inset:(x:25*t.u,y:29*t.u),radius:16*t.u,fill:blend(a:rgb("d5eefc"),b:rgb("dbedfd")),stroke:1*t.u+pale,outset:-.5*t.u)[
        #align(center+horizon)[
          #copy(t,"⚡ HIGHLIGHT TIME",size:14.4,fill:secondary,tracking:.5)#v(14*t.u)
          #copy(t,d.peak,size:35.2,weight:700,fill:blue)#v(6*t.u)
          #copy(t,"最活跃的时刻",size:14.4,fill:muted)
        ]
      ])
    }))
  v(40*t.u)
}
#let chart(t,d)=panel(t,[
  #heading(t,"chart","24H 活跃轨迹")#v(12*t.u)
  #block(width:100%,height:220*t.u,inset:(x:10*t.u,top:20*t.u,bottom:7*t.u),stroke:(bottom:2*t.u+border),outset:(bottom:-1*t.u))[
    #let highest=calc.max(1,..d.hours)
    #grid(columns:(1fr,)*24,gutter:4*t.u,align:bottom,..d.hours.enumerate().map(((i,n))=>block(width:100%,height:193*t.u)[
      #if n > 0 {place(top+left,dy:-20*t.u,align(center,copy(t,str(n),size:11.2,weight:700,fill:secondary)))}
      #place(bottom+left,align(center)[
        #rect(width:100%,height:calc.min(165.8,calc.max(4,n/highest*193))*t.u,radius:(top:6*t.u),stroke:none,fill:if n==0 {muted.transparentize(85%)}else if n/highest>=.7 {orange}else if n/highest>=.3 {green}else{blue})
        #v(8*t.u)#copy(t,(if i < 10 {"0"}else{""})+str(i),size:12,fill:muted)
      ])
    ]))
  ]
])
#let topics(t,d)={
  panel(t,[
    #heading(t,"topics","今日话题 Topics")
    #for (i,x) in d.topics.enumerate() {
      block(width:100%,inset:17*t.u,fill:blue.transparentize(97%),radius:10*t.u,stroke:1*t.u+border,outset:-.5*t.u)[
        #grid(columns:(36*t.u,1fr),gutter:14*t.u,align:top,
          pad(top:2*t.u,box(width:36*t.u,height:36*t.u,radius:8*t.u,fill:if calc.rem(i+2,3)==0 {blend(a:pink,b:rgb("f48fb1"))}else if calc.even(i+2) {blend(a:purple,b:rgb("9c8df7"))}else{blend()})[#align(center+horizon,copy(t,(if i < 9 {"0"}else{""})+str(i+1),size:14.4,weight:700,fill:white))]),[
          #copy(t,x.title,size:18.4,weight:700)#v(4*t.u)
          #copy(t,[🙋‍♀️ 参与者： #runs(t,x.contributors)],size:13.6,fill:secondary)#v(6*t.u)
          #copy(t,runs(t,x.detail),size:15.2,fill:secondary,lh:1.5)
        ])
      ]
      v(18*t.u)
    }
  ])
}
#let portraits(t,d)=context {
  heading(t,"user","群友画像 Portraits",centered:true)
  let width=399*t.u
  let cards=d.portraits.map(p=>{
    let body=panel(t,inset:24,[
      #grid(columns:(56*t.u,1fr),gutter:14*t.u,align:top,avatar(t,p.avatar),[
        #copy(t,if p.name=="" {"匿名群友"}else{p.name},size:17.6,weight:700,lh:1.2)#v(6*t.u)
        #par(leading:6*t.u)[
          #box(inset:(x:11*t.u,y:4*t.u),radius:12*t.u,fill:blend(a:rgb("fff3e0"),b:rgb("ffe0b2")),stroke:1*t.u+rgb("ffcc80"),outset:-.5*t.u)[#copy(t,p.title,size:12.48,fill:rgb("e65100"))]#h(6*t.u)#box(inset:(x:11*t.u,y:4*t.u),radius:12*t.u,fill:blend(a:rgb("ede7f6"),b:rgb("d1c4e9")),stroke:1*t.u+rgb("b39ddb"),outset:-.5*t.u)[#copy(t,p.profile,size:12.48,weight:700,fill:rgb("512da8"),tracking:.5)]
        ]
      ])
      #v(14*t.u)#line(length:100%,stroke:1*t.u+border)#v(14*t.u)
      #block(width:100%,inset:(left:17*t.u,right:14*t.u,y:12*t.u),fill:blue.transparentize(97%),stroke:(left:3*t.u+pale),outset:(left:-1.5*t.u),radius:(right:10*t.u))[
        #copy(t,runs(t,p.reason),size:14.4,fill:secondary)
      ]
    ])
    let m=measure(body,width:width)
    let result=block(width:width,height:m.height)[
      #body
      #if p.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(p.image,width:width*.38,height:calc.min(measure(image(p.image,width:width*.38)).height,m.height*.8),fit:p.image_fit))}
    ]
    (body:result,height:m.height+20*t.u)
  })
  let cut=cards.len();let best=1e9*1pt
  for n in range(1,cards.len()+1) {
    let h=calc.max(cards.slice(0,n).map(c=>c.height).sum(default:0pt),cards.slice(n).map(c=>c.height).sum(default:0pt))
    if h < best {best=h;cut=n}
  }
  grid(columns:(1fr,1fr),gutter:20*t.u,..(cards.slice(0,cut),cards.slice(cut)).map(column=>[
    #for card in column {card.body;v(20*t.u)}
  ]))
}
#let quotes(t,d)=context {
  heading(t,"quote","群贤毕至 Bible Quotes",centered:true)
  v(24*t.u)
  for (i,q) in d.quotes.enumerate() {
    // nth-child 包含分区标题，因此第一条采用粉色、右对齐的偶数样式。
    let reverse=calc.even(i)
    let color=if reverse {pink}else{blue}
    let content-width=818*.88 - 76
    let bubble-width=calc.min(content-width,measure(copy(t,runs(t,q.content),size:17.6,lh:1.4)).width/t.u+42)
    let note-width=calc.min(content-width,calc.max(measure(copy(t,runs(t,q.reason),size:13.6,fill:secondary,lh:1.5)).width/t.u,measure(copy(t,"🤣👉 AI 锐评：",size:13.6,weight:700,fill:color,lh:1.5)).width/t.u)+30)
    let width=calc.max(bubble-width,note-width)
    align(if reverse {right}else{left},block(width:(width+76)*t.u)[
      #grid(columns:if reverse {(width*t.u,64*t.u)}else{(64*t.u,width*t.u)},gutter:12*t.u,align:top,..(if reverse {(true,false)}else{(false,true)}).map(content=>if not content {
        if q.avatar!="" {align(center,avatar(t,q.avatar,size:52,thickness:2,halo:color.transparentize(80%)))}
      }else{align(if reverse {right}else{left})[
        #box(inset:if reverse {(right:8*t.u)}else{(left:8*t.u)})[#copy(t,q.sender,size:16,weight:700,fill:color,lh:1.2)]#v(4*t.u)
        #block(width:bubble-width*t.u)[#panel(t,inset:0,radius:16,corners:if reverse {(top-left:16*t.u,top-right:4*t.u,bottom:16*t.u)}else{(top-left:4*t.u,top-right:16*t.u,bottom:16*t.u)},stroke:if reverse {pink.transparentize(80%)}else{border},fill:if reverse {rgb("fef9fb")}else{white},color:rgb("347ceb").transparentize(92%),block(width:100%,inset:(x:20*t.u,y:14*t.u))[
          #copy(t,runs(t,q.content),size:17.6,lh:1.4)#v(4*t.u)
        ])]
        #v(-2*t.u)
        #block(width:note-width*t.u,inset:(x:15*t.u,y:11*t.u),radius:(bottom:10*t.u),fill:color.transparentize(96%),stroke:1*t.u+border,outset:-.5*t.u)[
          #align(left)[
            #copy(t,"🤣👉 AI 锐评：",size:13.6,weight:700,fill:color,lh:1.5)#v(3*t.u)
            #copy(t,runs(t,q.reason),size:13.6,fill:secondary,lh:1.5)
          ]
        ]
      ]}))
    ])
    if i < d.quotes.len()-1 {v(24*t.u)}
  }
  v(24*t.u)
}
#let quality(t,d)=panel(t,[
  #heading(t,"quality","群聊质量锐评")
  #let r=d.review
  #panel(t,inset:24,fill:rgb("f9fcff"),[
    #block(width:100%,inset:(bottom:13*t.u),stroke:(bottom:1*t.u+border),outset:(bottom:-.5*t.u))[
      #grid(columns:(auto,1fr),gutter:12*t.u,align:horizon,
        box(inset:(x:18*t.u,y:6*t.u),radius:20*t.u,fill:blend())[#copy(t,r.title,size:19.2,weight:700,fill:white)],
        align(right,copy(t,r.subtitle,weight:700,fill:secondary)))
    ]
    #v(20*t.u)
    #let colors=(blue,cyan,purple,pink,orange,green,rgb("ffc107"),rgb("26c6da"))
    #let dims=r.dimensions.enumerate().filter(((i,x))=>x.percentage > 0)
    #block(width:100%,height:34*t.u,inset:1*t.u,radius:10*t.u,clip:true,fill:white,stroke:1*t.u+border,outset:-.5*t.u)[
      #if dims.len() > 0 {
        let total=calc.max(100,dims.map(((i,x))=>x.percentage).sum())
        grid(columns:dims.map(((i,x))=>x.percentage/total*100%),..dims.map(((i,x))=>block(width:100%,height:32*t.u,fill:colors.at(calc.rem(i,8)),clip:true,inset:(x:4*t.u),stroke:if i==dims.last().at(0) {none}else{(right:1*t.u+white.transparentize(70%))})[
          #layout(size=>context {
            let value=x.name
            if measure(copy(t,value,size:12.8,weight:700)).width > size.width {
              let clusters=value.clusters()
              while clusters.len() > 0 and measure(copy(t,clusters.join("")+"…",size:12.8,weight:700)).width > size.width {clusters=clusters.slice(0,clusters.len()-1)}
              value=clusters.join("")+"…"
            }
            align(center+horizon,copy(t,value,size:12.8,weight:700,fill:white))
          })
        ]))
      }
    ]
    #v(20*t.u)
    #layout(size=>context {
      let width=(size.width - 12*t.u)/2
      let cards=dims.map(((i,x))=>{
        let color=colors.at(calc.rem(i,8))
        let body=[
          #block(width:100%,inset:(bottom:4*t.u),stroke:(bottom:2*t.u+color),outset:(bottom:-1*t.u))[
            #copy(t,x.name,size:13.6,weight:700,fill:color,lh:1.5)
          ]#v(2*t.u)
          #let tenth=calc.round(x.percentage*10)
          #copy(t,str(calc.quo(tenth,10))+"."+str(calc.rem(tenth,10))+"%",size:13.12,weight:700,fill:color,lh:20.4/13.12)#v(8*t.u)
          #copy(t,runs(t,x.comment),size:13.6,fill:secondary,lh:1.5)
        ]
        (body:body,color:color,height:measure(body,width:width - 30*t.u).height+30*t.u)
      })
      for (i,row) in cards.chunks(2).enumerate() {
        if i > 0 {v(12*t.u)}
        let height=calc.max(..row.map(card=>card.height))
        grid(columns:(1fr,1fr),gutter:12*t.u,..row.map(card=>block(width:100%,height:height,inset:15*t.u,radius:10*t.u,fill:white,stroke:1*t.u+card.color,outset:-.5*t.u)[#card.body]))
      }
    })
    #v(20*t.u)
    #grid(columns:(96*t.u,1fr),gutter:16*t.u,align:top,avatar(t,d.decorations.at(1,default:""),size:96),layout(size=>{
      let body=block(width:100%,inset:(x:25*t.u,y:19*t.u))[#copy(t,runs(t,r.summary),lh:1.7)]
      let m=measure(body,width:size.width);let w=m.width/t.u;let h=calc.max(72,m.height/t.u)
      let f=calc.min(1,w/270,h/270);let a=255*f;let b=15*f;let c=225*f
      let path="M"+str(a)+" .5H"+str(w - b)+"A"+str(b)+" "+str(c)+" 0 0 1 "+str(w - .5)+" "+str(c)+"V"+str(h - b)+"A"+str(c)+" "+str(b)+" 0 0 1 "+str(w - c)+" "+str(h - .5)+"H"+str(b)+"A"+str(b)+" "+str(a)+" 0 0 1 .5 "+str(h - a)+"V"+str(b)+"A"+str(a)+" "+str(b)+" 0 0 1 "+str(a)+" .5Z"
      let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w)+"' height='"+str(h)+"'><path d='"+path+"' fill='white' stroke='#d0dff0'/></svg>"
      shadow(t,radius:16,blur:8,dy:2,color:rgb("347ceb").transparentize(92%),block(width:m.width,height:h*t.u)[
        #place(top+left,image(bytes(svg),format:"svg",width:100%,height:100%))
        #place(top+left,dx:-14*t.u,dy:28*t.u,polygon(fill:border,stroke:none,(0pt,12*t.u),(12*t.u,0pt),(12*t.u,24*t.u)))
        #place(top+left,dx:-10*t.u,dy:28*t.u,polygon(fill:white,stroke:none,(0pt,12*t.u),(12*t.u,0pt),(12*t.u,24*t.u)))
        #align(horizon,body)
      ])
    }))
  ])
  #v(20*t.u)
])
#let footer(t,d)={
  v(48*t.u)
  block(width:100%,inset:(x:21*t.u,y:29*t.u),radius:16*t.u,fill:blend(a:blue.transparentize(97%),b:cyan.transparentize(97%)),stroke:(paint:pale,thickness:1*t.u,dash:(array:(3*t.u,3*t.u))),outset:-.5*t.u)[
    #layout(size=>context {
      let bodies=("info","repo","tokens").map(kind=>align(center)[
        #let title=if kind=="info" {("📋","Sensei Report")}else if kind=="repo" {("🏫","Schale Office")}else{("⚙️","Token 消耗")}
        #align(center,grid(columns:(auto,auto),gutter:6*t.u,align:horizon,copy(t,title.at(0),size:19.2,fill:muted.transparentize(30%)),copy(t,title.at(1),weight:700)))#v(4*t.u)
        #if kind=="info" {
          block[#copy(t,d.generated_at,size:13.6,fill:muted,lh:1.4)]
          block[#copy(t,[AstrBot 群分析总结插件#linebreak()主题设计：香草味的纳西妲喵（VanillaNahida）],size:10.88,fill:muted.transparentize(30%),lh:1.4)]
        }else if kind=="repo" {
          copy(t,"SXP-Simon/astrbot_plugin_qq_group_daily_analysis".clusters().join(sym.zws),size:12.8,fill:muted,lh:1.4)
        }else{
          copy(t,[Total: #d.tokens.at(0) Tokens#linebreak()Prompt/Compl: #d.tokens.at(1)/#d.tokens.at(2)],size:13.6,fill:muted,lh:1.4)
        }
      ])
      let width=(size.width - 32*t.u)/3
      let height=calc.max(..bodies.map(body=>measure(body,width:width - 34*t.u).height))+34*t.u
      grid(columns:(1fr,1fr,1fr),gutter:16*t.u,..bodies.enumerate().map(((i,body))=>panel(t,inset:16,radius:10,height:height,stroke:(pale,purple.transparentize(70%),green.transparentize(70%)).at(i),blur:6,align(horizon,body))))
    })
  ]
}
#let render(d)={
  let u=.5pt
  let cjk=if d.font_language=="zh-Hant" {("Noto Sans TC","Noto Sans SC")}else{("Noto Sans SC","Noto Sans TC")}
  let t=(u:u,fonts:(..cjk,"Noto Color Emoji"))
  set page(width:940*u,height:auto,margin:0pt,fill:rgb("edf5fc"))
  set text(font:t.fonts,size:16*u,weight:600,lang:"zh",cjk-latin-spacing:none,hyphenate:false)
  set par(leading:0pt,spacing:0pt)
  set smartquote(enabled:false)
  set page(background:layout(size=>{
    box(width:size.width,height:size.height)[
      #place(top+left,box(width:940*u,height:900*u,clip:true)[#image("background.svg",width:100%,height:100%,fit:"cover")])
      #place(top+left,dx:20*u,dy:40*u,shadow(t,radius:24,blur:24,dy:4,color:rgb("347ceb").transparentize(88%),block(width:900*u,height:size.height - 80*u,radius:24*u,fill:white,stroke:1*u+border,outset:-.5*u)))
    ]
  }))
  block(width:940*u,inset:(x:61*u,top:105*u,bottom:89*u))[
    #header(t,d)#statistics(t,d)#chart(t,d)
    #if d.topics.len() > 0 {v(24*u);topics(t,d)}
    #if d.portraits.len() > 0 {v(28*u);portraits(t,d)}
    #if d.quotes.len() > 0 {v(28*u);quotes(t,d)}
    #if d.review!=none {v(28*u);quality(t,d)}
    #footer(t,d)
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}


// 角色图层、闭眼线条及铁盆裁切沿用 inline_assets.html；美术来源见 SOURCE-NOTICE.md。
#import "common.typ": shadow
#let ink=rgb("233858")
#let muted=rgb("71839c")
#let blue=rgb("477ac9")
#let pale=rgb("eef5ff")
#let border=rgb("e0e9f7")
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.7,tracking:0,mono:false) = {
  set par(leading:0pt,spacing:0pt)
  let baseline=if mono {.86}else{.936}
  let edge=(lh - 1)/2
  text(font:if mono {("JetBrains Mono",..t.font)}else{t.font},size:size*t.u,weight:weight,fill:fill,tracking:tracking*t.u,top-edge:(baseline+edge)*1em,bottom-edge:-(1-baseline+edge)*1em,body)
}
#let number(n) = str(n).clusters().rev().chunks(3).map(x=>x.rev().join("")).rev().join(",")
#let rule(t,paint:border,dashed:false) = block(width:100%,height:1*t.u)[
  #place(horizon,line(length:100%,stroke:(paint:paint,thickness:1*t.u,dash:if dashed {"dashed"}else{"solid"})))
]
#let runs(t,parts) = {
  for part in parts {
    if part.avatar!="" {
      h(2*t.u)
      box(inset:(left:3*t.u,right:7*t.u,y:3*t.u),radius:12*t.u,fill:black.transparentize(95%),stroke:1*t.u+black.transparentize(90%),baseline:(at:bottom,shift:7*t.u))[
        #set text(top-edge:.85em,bottom-edge:-.15em)
        #box(width:18*t.u,height:18*t.u,radius:50%,clip:true,baseline:25%)[#image(part.avatar,width:100%,height:100%,fit:"cover")]
        #if part.text!="" {h(4*t.u);text(size:.85em,weight:500,top-edge:.85em,bottom-edge:-.15em,part.text)}
      ]
      h(2*t.u)
    }else{for (i,line) in part.text.split("\n").enumerate(){if i>0 {linebreak()};line}}
  }
}
#let face(t,path,size:45) = box(width:size*t.u,height:size*t.u,radius:50%,clip:true,fill:rgb("e6efff"))[
  #if path!="" {image(path,width:100%,height:100%,fit:"cover")}else{align(center+horizon,copy(t,"✦",size:size*.45,fill:rgb("78a0d8")))}
]
#let character(t,d,mood:"open",detail:"full",basin:false,width:235,height:332) = {
  let required=if basin {6}else{0}
  if d.decorations.at(required,default:"")=="" {return box(width:width*t.u,height:height*t.u)}
  let viewport=if basin and detail=="head" {(80,60,780,535)}else if basin {(80,0,780,1024)}else if detail=="head" {(180,0,650,590)}else{(110,0,710,1024)}
  let (x,y,w,h)=viewport
  let scale=calc.min(width/w,height/h)
  let indices=if basin {(6,)}else if mood=="sleep" {(0,4,5)}else{(0,1,2,3)}
  let opening="<svg xmlns='http://www.w3.org/2000/svg' viewBox='"+viewport.map(str).join(" ")+"'>"
  let body=box(width:w*scale*t.u,height:h*scale*t.u,clip:true)[
    // SVG 嵌入位图的缩放会产生锯齿；角色图层直接使用原生图片，滤镜只绘制底部阴影。
    #if detail=="full" {
      let layers=""
      for i in indices {
        let path=d.decorations.at(i,default:"")
        if path!="" {layers+="<image href='"+path+"' x='"+(if i==6 {"50"}else{"0"})+"' width='"+(if i==6 {"820"}else{"1536"})+"' height='1024'/>"}
      }
      let filter="<defs><filter id='shadow' x='-10%' y='-10%' width='120%' height='120%'><feGaussianBlur in='SourceAlpha' stdDeviation='"+str(4/scale)+"'/><feOffset dy='"+str(7/scale)+"' result='offset'/><feFlood flood-color='#5372a9' flood-opacity='0.0941'/><feComposite in2='offset' operator='in'/></filter></defs>"
      place(top+left,image(bytes(opening+filter+"<g filter='url(#shadow)'>"+layers+"</g></svg>"),format:"svg",width:100%,height:100%))
    }
    #let path=d.decorations.at(required)
    #place(top+left,dx:((if basin {50}else{0}) - x)*scale*t.u,dy:-y*scale*t.u,
      image(path,width:(if basin {820}else{1536})*scale*t.u,height:1024*scale*t.u,fit:"contain"))
    // 小块表情图层统一合成，避免分别缩放透明边缘产生矩形接缝。
    #if not basin {
      let overlays=""
      for i in indices.filter(i=>i!=0) {
        let path=d.decorations.at(i,default:"")
        if path!="" {overlays+="<image href='"+path+"' width='1536' height='1024'/>"}
      }
      if mood=="sleep" {
        overlays+="<path d='M338 420Q372 442 403 420M495 420Q529 442 560 420' fill='none' stroke='#342136' stroke-width='5' stroke-linecap='round'/><path d='M436 459Q446 471 458 459' fill='none' stroke='#BD7480' stroke-width='3' stroke-linecap='round'/>"
      }
      place(top+left,image(bytes(opening+overlays+"</svg>"),format:"svg",width:100%,height:100%))
    }
  ]
  box(width:width*t.u,height:height*t.u)[#place(center+horizon,body)]
}
#let panel(t,body,padx:18,pady:18,radius:13,fill:white,stroke:border,height:none) = block(
  width:100%,height:if height==none {auto}else{height*t.u},inset:(x:(padx+1)*t.u,y:(pady+1)*t.u),radius:radius*t.u,fill:fill,stroke:1*t.u+stroke,outset:-.5*t.u,clip:true,
)[#body]
#let section(t,title,caption,index,body,before:none) = block(width:100%,radius:14*t.u,fill:white,stroke:1*t.u+border,outset:-.5*t.u,inset:1*t.u,clip:true)[
  #block(width:100%,inset:(x:23*t.u,y:16*t.u),fill:rgb("f7faff"))[
    #grid(columns:(auto,1fr,auto),gutter:10*t.u,align:horizon,
      box(inset:(right:10*t.u),stroke:(right:1*t.u+rgb("cedcf0")))[#copy(t,index,size:11,weight:600,fill:rgb("89a6d3"))],
      copy(t,title,size:17,weight:700),copy(t,caption,size:10,fill:rgb("91a3bb"),tracking:1))
  ]
  #rule(t,paint:rgb("e9eff8"))
  #if before!=none {before}
  #block(width:100%,inset:(x:23*t.u,y:21*t.u))[#body]
]
#let topline(t,d) = {
  grid(columns:(1fr,auto),gutter:16*t.u,align:horizon,
    grid(columns:(35*t.u,auto),gutter:9*t.u,align:horizon,image("brand.svg",width:35*t.u,height:26*t.u),copy(t,"大肥鱼值班室",size:15,weight:700,fill:blue)),
    copy(t,[DAILY LOG / #d.date],size:11,fill:muted,tracking:1.3))
  v(18*t.u);rule(t)
}
#let hero(t,d) = {
  let sleepy=d.message_count==0
  let busy=d.message_count>=1000
  v(30*t.u)
  grid(columns:(1fr,290*t.u),gutter:18*t.u,align:horizon,[
    #copy(t,[#box(width:7*t.u,height:7*t.u,radius:50%,fill:rgb("86a9e3"),baseline:25%)[]#h(8*t.u)DeepSeek 鲸鱼女仆 · DAILY LOG],size:13,fill:blue,tracking:1)
    #v(18*t.u)#copy(t,[大肥鱼#linebreak()#text(fill:blue)[今日打工实录]],size:43,weight:800,lh:1.35,tracking:1)#v(18*t.u)
    #copy(t,if sleepy {[今天鱼塘很安静。#linebreak()本鱼先闭会儿眼，有新消息再叫我。]}else if busy {[鱼塘这么热闹，铁盆已经扣好了。#linebreak()别催，本鱼正在把名场面整理进上下文。]}else{[嗯哼，这样啊。#linebreak()先把日报交了，再去干饭。]},size:14,lh:1.9,fill:muted)
    #v(22*t.u)#box(inset:(x:18*t.u,y:11*t.u),fill:rgb("f2f7ff"),stroke:1*t.u+rgb("d7e4f9"),radius:9*t.u)[
      #copy(t,[#text(size:12*t.u,fill:muted)[值班日期]#h(15*t.u)#text(weight:600,d.date)],size:14)
    ]
    #v(12*t.u)#rotate(-2deg,box(inset:(x:10*t.u,y:3*t.u),radius:4*t.u,stroke:(paint:rgb("aabdd9"),thickness:1*t.u,dash:"dashed"))[
      #copy(t,if sleepy {"DeepSleep 小剧场"}else if busy {"铁盆防御模式"}else{"今日份工作，真的做了"},size:10,fill:rgb("7b8fad"))
    ])
  ],block(width:290*t.u,height:360*t.u)[
    #place(top+center,dy:45*t.u,circle(radius:122.5*t.u,fill:gradient.radial((rgb("eef2ff"),0%),(rgb("e5efff"),70%),(rgb("e5efff"),100%),center:(45%,35%),space:rgb),stroke:(paint:rgb("c3d5f4"),thickness:1*t.u,dash:"dashed")))
    #place(top+center,character(t,d,mood:if sleepy {"sleep"}else{"open"},basin:busy,width:if busy {253}else{235}))
    #place(top+right,dx:-18*t.u,dy:72*t.u,image("star.svg",width:24*t.u,height:24*t.u))
    #place(top+left,dx:14*t.u,dy:224*t.u,image("star-outline.svg",width:18*t.u,height:18*t.u))
    #place(bottom+center,rotate(-3deg,box(inset:(x:17*t.u,y:5*t.u),fill:white,radius:30*t.u,stroke:1*t.u+rgb("dce6f6"))[
      #copy(t,if sleepy {"zzz · 等待下一次投喂"}else if busy {"盆在，发型就在"}else{"不是鱼，是鲸！"},size:12,fill:blue)
    ]))
  ])
  v(26*t.u)
}
#let thinking(t,d) = {
  block(width:100%,inset:(left:26*t.u,right:23*t.u,y:18*t.u),fill:rgb("f0f1fb"),radius:(top-right:11*t.u,bottom-right:11*t.u),stroke:(left:3*t.u+rgb("94a4d6")),outset:(left:-1.5*t.u))[
    #grid(columns:(1fr,auto),gutter:8*t.u,align:horizon,
      copy(t,[#box(width:6*t.u,height:6*t.u,radius:50%,fill:rgb("9293c7"),baseline:25%)[]#h(8*t.u)鱼鱼的内心 OS],size:12,weight:600,fill:rgb("6f72a4")),
      box(inset:(x:7*t.u,y:1*t.u),radius:4*t.u,stroke:1*t.u+rgb("d7d9ee"))[#copy(t,"工作便签",size:9,fill:rgb("8a8dae"))])
    #v(8*t.u)#copy(t,if d.message_count==0 {"没有新消息。很好，先做一会儿 DeepSleep 稳定性测试。"}else{[
      今天有 #text(weight:700,number(d.message_count)) 条消息。先看看大家在聊什么……#h(5*t.u)#underline(stroke:(paint:rgb("b7b2cb"),thickness:.7*t.u,dash:"dotted"),offset:4*t.u)[#text(fill:rgb("9490af"))[有点饿了。中午吃什么呢？]]#h(5*t.u)不行，先把上下文整理完。
    ]},size:13,lh:1.9,fill:rgb("71768f"))
    #v(7*t.u)#copy(t,"// 日报已交，饭碗待领",size:10,fill:rgb("989ab8"),mono:true)
  ]
  v(25*t.u)
}
#let statistics(t,d) = {
  grid(columns:(1fr,auto),gutter:12*t.u,align:horizon,copy(t,"鱼塘今日收获",size:18,weight:700),copy(t,"数字记清楚，才好理直气壮下班",size:12,fill:muted))
  v(13*t.u)
  let entries=(("消息总数",d.message_count,"条消息"),("参与人数",d.participant_count,"位群友"),("总字符数",d.characters,"个字符"),("表情数量",d.emoji_count,"个表情"))
  grid(columns:(1fr,)*4,gutter:12*t.u,..entries.enumerate().map(((i,e))=>panel(t,fill:rgb("f4f8fe"),stroke:rgb("dee8f7"),[
    #place(top+right,dx:7*t.u,dy:-8*t.u,copy(t,"0"+str(i+1),size:10,fill:rgb("a6b8d4")))
    #copy(t,e.at(0),size:12,fill:rgb("677f9f"))#v(8*t.u)
    #copy(t,number(e.at(1)),size:29,weight:700,fill:rgb("396bae"),lh:1.45)
    #copy(t,e.at(2),size:10,fill:rgb("96a5bb"))
  ])))
  v(12*t.u);copy(t,[最热闹的时段 · #d.peak],size:12,fill:muted);v(25*t.u)
}
#let receipt(t,d) = {
  block(width:100%,inset:(x:24*t.u,y:21*t.u),fill:rgb("f1f7ff"),radius:8*t.u,stroke:(top:(paint:rgb("bccfe9"),thickness:2*t.u,dash:"dashed"),bottom:(paint:rgb("bccfe9"),thickness:2*t.u,dash:"dashed"),left:1*t.u+rgb("d6e3f6"),right:1*t.u+rgb("d6e3f6")),outset:-.5*t.u)[
    #grid(columns:(76*t.u,1fr,100*t.u),gutter:17*t.u,align:horizon,
      align(center)[#image("rice-bowl.svg",width:70*t.u,height:59*t.u)#copy(t,"饭票",size:11,fill:rgb("7698c7"),tracking:5)],
      [#copy(t,[本鱼的投喂记录#h(8*t.u)#text(size:9*t.u,weight:400,fill:rgb("8e9fb7"))[Token 消耗]],size:13,weight:600,fill:rgb("6888b6"))
        #if d.tokens.at(0)>0 {
          copy(t,[#text(weight:700,number(d.tokens.at(0)))#h(7*t.u)#text(size:11*t.u,fill:rgb("91a7c5"))[Tokens]],size:33,fill:rgb("4874ad"),lh:1.5)
        }else{v(8*t.u);copy(t,"本次暂无 Token 消耗记录",size:15,fill:rgb("7291b9"));v(5*t.u)}
        #copy(t,[输入 #number(d.tokens.at(1))#h(5*t.u)#text(fill:rgb("b4c3d8"))[／]#h(5*t.u)输出 #number(d.tokens.at(2))],size:10,fill:rgb("8a9db6"))
      ],block(inset:(left:18*t.u),stroke:(left:(paint:rgb("b6cbe7"),thickness:1*t.u,dash:"dashed")))[
        #place(top+left,dx:-24*t.u,dy:-21*t.u,circle(radius:6*t.u,fill:rgb("fcfdff"),stroke:.5*t.u+rgb("d6e3f6")))
        #copy(t,[先记账#linebreak()再干饭],size:14,weight:700,lh:1.55,fill:rgb("8aa4c8"),tracking:2)
        #v(6*t.u)#copy(t,"不许偷偷加餐",size:9,fill:rgb("8aa4c8"))
      ])
  ]
  v(25*t.u)
}
#let activity(t,d) = section(t,"摸鱼雷达","24H 群聊活跃度","01",[
  #copy(t,"本鱼巡逻过了：群里在哪些时段最热闹？",size:12,fill:muted)
  #v(3*t.u)#copy(t,"柱高按当天消息峰值归一化",size:10,fill:rgb("96a4bb"))#v(15*t.u)
  #let highest=calc.max(1,..d.hours)
  #grid(columns:(1fr,)*24,gutter:7*t.u,..d.hours.map(n=>block(width:100%,height:100*t.u,fill:gradient.linear(white,rgb("f4f7fd"),angle:90deg,space:rgb),radius:5*t.u)[
    #place(bottom+left,rect(width:100%,height:calc.max(3,n/highest*100)*t.u,fill:if n/highest>=.9 {rgb("537fc6")}else{rgb("abc3ed")},radius:(top-left:4*t.u,top-right:4*t.u),stroke:none))
  ]))
  #rule(t)#v(8*t.u)
  #grid(columns:(1fr,)*24,gutter:7*t.u,..range(24).map(i=>align(center,copy(t,if calc.rem(i,4)==0 or i==23 {(if i < 10 {"0"}else{""})+str(i)}else{""},size:9,fill:rgb("91a3bb")))))
])
#let topics(t,d) = section(t,"上下文还在，别急",[今日话题 / #d.topics.len() 则],"02",[
  #for (i,topic) in d.topics.enumerate() {
    if i>0 {v(19*t.u);rule(t,dashed:true);v(19*t.u)}
    grid(columns:(31*t.u,1fr),gutter:13*t.u,align:top,
      box(width:31*t.u,height:31*t.u,fill:pale,radius:8*t.u)[#align(center+horizon,copy(t,(if i+1 < 10 {"0"}else{""})+str(i+1),size:12,weight:700,fill:blue))],
      [#copy(t,topic.title,size:17,weight:700)#v(6*t.u)
        #if topic.contributors.any(x=>x.text!="" or x.avatar!="") {copy(t,[参与群友 · #runs(t,topic.contributors)],size:11,fill:rgb("8a9ab1"));v(9*t.u)}
        #copy(t,runs(t,topic.detail),size:14,lh:1.85,fill:rgb("566b88"))
      ])
  }
])
#let portraits(t,d) = context {
  let cards=d.portraits.map(p=>{
    let body=[
      #grid(columns:(45*t.u,1fr),gutter:12*t.u,align:horizon,face(t,p.avatar),[
        #copy(t,if p.name=="" {"匿名群友"}else{p.name},size:14,weight:600)#v(6*t.u)
        #par(leading:5*t.u)[
          #box(inset:(x:7*t.u,y:1*t.u),radius:5*t.u,fill:rgb("eaf1ff"))[#copy(t,p.title,size:10,fill:rgb("6086bf"))]#h(5*t.u)#box(inset:(x:7*t.u,y:1*t.u),radius:5*t.u,fill:rgb("f1eefa"))[#copy(t,p.profile,size:10,fill:rgb("8c7eaf"))]
        ]
      ])
      #v(13*t.u)#copy(t,runs(t,p.reason),size:12,lh:1.8,fill:rgb("73839b"))
    ]
    (body:body,portrait:p,height:measure(body,width:336*t.u).height/t.u+38)
  })
  section(t,"今日鱼塘图鉴","群友画像","03",[
    #for (i,row) in cards.chunks(2).enumerate() {
      let height=calc.max(..row.map(c=>c.height))
      grid(columns:(1fr,1fr),gutter:14*t.u,..row.map(c=>panel(t,height:height,radius:11,fill:rgb("fafcff"),stroke:rgb("e4ebf7"),[
        #if c.portrait.image!="" {
          let path=c.portrait.image
          let width=127.16*t.u
          place(bottom+right,dx:15*t.u,dy:15*t.u,image(path,width:width,height:calc.min(measure(image(path,width:width)).height,height*.75*t.u),fit:c.portrait.image_fit))
        }
        #c.body
      ])))
      if i < calc.ceil(cards.len()/2) - 1 {v(14*t.u)}
    }
  ])
}
#let quotes(t,d) = section(t,"今日名言收藏","精选群聊金句","04",[
  #v(-4*t.u)
  #grid(columns:(64*t.u,1fr,auto),gutter:10*t.u,align:horizon,character(t,d,detail:"head",width:64,height:64),[
    #copy(t,"大肥鱼看完这些金句：",size:10,fill:rgb("98a4b8"))#copy(t,"嗯哼，这样啊。",size:16,weight:700,fill:rgb("6082b4"))
  ],rotate(-4deg,copy(t,"本鱼先记下来",size:10,fill:rgb("8e9fb7"))))
  #v(12*t.u)#rule(t,paint:rgb("e4eaf5"),dashed:true)#v(15*t.u)
  #for (i,q) in d.quotes.enumerate() {
    if i>0 {v(18*t.u);rule(t,dashed:true)}
    v(18*t.u)
    grid(columns:(26*t.u,1fr),gutter:9*t.u,align:horizon,face(t,q.avatar,size:26),copy(t,if q.sender=="" {"匿名群友"}else{q.sender},size:12,fill:rgb("7185a3")))
    v(10*t.u)
    block(width:100%,inset:(left:23*t.u,right:20*t.u,y:15*t.u),fill:rgb("f0f5ff"),radius:(top-right:9*t.u,bottom-right:9*t.u),stroke:(left:3*t.u+rgb("8caee2")),outset:(left:-1.5*t.u))[#copy(t,runs(t,q.content),size:16,lh:1.8,fill:rgb("496c9f"))]
    if q.reason.any(x=>x.text!="" or x.avatar!="") {v(10*t.u);copy(t,[女仆的小注 · #runs(t,q.reason)],size:12,fill:rgb("8b96ac"))}
  }
])
#let quality(t,d) = {
  let r=d.review
  let warning=block(width:100%,inset:(x:23*t.u,top:14*t.u))[
    #grid(columns:(72*t.u,1fr,auto),gutter:12*t.u,align:horizon,character(t,d,detail:"head",basin:true,width:72,height:58),[
      #copy(t,"盆已经扣好了。",size:11,fill:rgb("91a0b8"),lh:1.8)#copy(t,"接下来，本鱼要说两句。",size:13,weight:500,fill:rgb("7189ad"),lh:1.8)
    ],rotate(5deg,box(inset:(x:9*t.u,y:3*t.u),stroke:(paint:rgb("c8d4e5"),thickness:1*t.u,dash:"dashed"))[#copy(t,"请勿敲盆",size:9,fill:rgb("a0acc0"))]))
  ]
  section(t,"铁盆防御 · 鱼塘锐评","群聊质量小结","05",before:warning,[
    #copy(t,r.title,size:15,weight:600)#v(4*t.u)
    #if r.subtitle!="" {copy(t,r.subtitle,size:11,fill:rgb("92a0b7"));v(16*t.u)}
    #grid(columns:(1fr,1fr),column-gutter:22*t.u,row-gutter:14*t.u,..r.dimensions.map(x=>[
      #grid(columns:(1fr,auto),gutter:10*t.u,align:horizon,copy(t,x.name,size:12,fill:rgb("617da2")),copy(t,[#calc.round(x.percentage)%],size:12,weight:700,fill:rgb("617da2")))#v(6*t.u)
      #block(width:100%,height:6*t.u,fill:rgb("edf2fb"),radius:4*t.u,clip:true)[#rect(width:x.percentage*1%,height:6*t.u,fill:rgb("88a9dd"),stroke:none,radius:4*t.u)]
      #v(6*t.u)#copy(t,runs(t,x.comment),size:11,fill:rgb("8b9ab0"))
    ]))
    #if r.summary.any(x=>x.text!="" or x.avatar!="") {v(20*t.u);block(width:100%,inset:(x:16*t.u,y:13*t.u),fill:rgb("f8f7fd"),radius:9*t.u)[#copy(t,runs(t,r.summary),size:13,fill:rgb("83789f"))]}
  ])
}
#let handover(t,d) = {
  v(23*t.u)
  block(width:100%,inset:(x:26*t.u,y:16*t.u),fill:rgb("f4f8fe"),radius:13*t.u,stroke:(paint:rgb("ccd9ec"),thickness:1*t.u,dash:"dashed"),outset:-.5*t.u)[
    #place(top+right,dy:6*t.u,copy(t,[z#h(5*t.u)#super[z]#h(4*t.u)#super[#text(size:11*t.u)[z]]],size:22,fill:rgb("bac9df"),mono:true))
    #grid(columns:(94*t.u,1fr),gutter:20*t.u,align:horizon,character(t,d,mood:"sleep",detail:"mini",width:94,height:135),[
      #copy(t,"LET ME GO · 今日交班",size:9,fill:rgb("98a8c3"),tracking:1.7)#v(7*t.u)
      #copy(t,"我去吃饭，测完告诉我就行。",size:17,weight:600,fill:rgb("6e86af"))#v(8*t.u)
      #copy(t,[今天的热闹，已经留在上下文里了。#linebreak()剩下的时间，本鱼申请 DeepSleep。],size:12,lh:1.8,fill:rgb("8e9eb5"))#v(7*t.u)
      #copy(t,"—— 大肥鱼，先溜了",size:10,fill:rgb("a0aec4"))
    ])
  ]
}
#let footer(t,d) = {
  v(25*t.u);rule(t);v(25*t.u)
  grid(columns:(1fr,auto),gutter:15*t.u,align:bottom,[
    #copy(t,"DeepSeek 鲸鱼女仆娘 · 社区同人主题",size:13,weight:500,fill:rgb("6380ab"))
    #copy(t,[角色：#underline[上善无形] / #underline[ZipZipPipe] · #underline[素材署名] · #underline[CC BY-NC-SA 4.0]（改绘）],size:10,fill:rgb("9aa8bc"))
  ],align(right)[
    #copy(t,"AstrBot 群分析总结插件",size:10,fill:rgb("9aa8bc"))
    #copy(t,underline[Template by StuGRua],size:10,fill:rgb("9aa8bc"))
    #copy(t,d.generated_at,size:10,fill:rgb("9aa8bc"))
  ])
}
#let render(d,t) = {
  t.insert("font",("Noto Sans SC","Noto Sans TC"))
  set page(width:940*t.u,height:auto,margin:0pt,fill:rgb("e9f0fb"))
  set text(font:t.font,size:16*t.u,fill:ink,lang:"zh",region:"CN",cjk-latin-spacing:none)
  set par(leading:0pt,spacing:0pt)
  // 页背景的高度已确定；只为边框阴影绘制空盒子，避免再次测量整份报告。
  set page(background:layout(size=>place(top+left,dx:20*t.u,dy:32*t.u,shadow(t,block(width:900*t.u,height:size.height - 64*t.u),radius:22,dy:12,blur:50,color:ink.transparentize(95.7%)))))
  block(width:940*t.u,inset:(x:20*t.u,y:32*t.u))[
    #block(width:900*t.u,inset:(x:45*t.u,y:33*t.u),fill:rgb("fcfdff"),stroke:1*t.u+rgb("dce6f6"),outset:-.5*t.u,radius:22*t.u,clip:true)[
      #topline(t,d)#hero(t,d)#thinking(t,d)#statistics(t,d)#receipt(t,d)#activity(t,d)
      #if d.topics.len()>0 {v(20*t.u);topics(t,d)}
      #if d.portraits.len()>0 {v(20*t.u);portraits(t,d)}
      #if d.quotes.len()>0 {v(20*t.u);quotes(t,d)}
      #if d.review!=none {v(20*t.u);quality(t,d)}
      #handover(t,d)#footer(t,d)
    ]
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

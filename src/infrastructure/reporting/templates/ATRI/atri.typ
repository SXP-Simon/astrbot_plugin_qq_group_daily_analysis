// ATRI 使用独立的海景、玻璃卡片、贴纸与聊天气泡布局。
#import "common.typ": shadow
#let ink=rgb("5e5358")
#let muted=rgb("8d818a")
#let deep=rgb("5a4c5a")
#let sea=rgb("6d9afa")
#let sky=rgb("8fc5ff")
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.25,mono:false,tracking:0) = {
  set par(leading:0pt,spacing:0pt)
  // 浏览器在原字体之上合成六百字重；细描边保留同样的标题厚度。
  text(font:if mono {t.mono}else{t.font},size:size*t.u,weight:weight,fill:fill,stroke:if weight>=600 {.25*t.u+fill}else{none},tracking:tracking*1em,top-edge:(lh/2+.34)*1em,bottom-edge:-(lh/2-.34)*1em,body)
}
#let icon(t,name,size:20,fill:sea,solid:false) = {
  let svg=read(name+".svg")
  if solid {svg=svg.replace("fill=\"none\"","fill=\"currentColor\"")}
  image(bytes(svg.replace("currentColor",fill.to-hex())),format:"svg",width:size*t.u,height:size*t.u)
}
#let art(t,d,index,width:44,height:none) = {
  let path=d.decorations.at(index,default:"")
  if path!="" {image(path,width:width*t.u,height:if height==none {auto}else{height*t.u},fit:"contain")}
}
#let sticker(t,d,index,size:44) = box(width:size*t.u,height:size*t.u,radius:12*t.u,fill:white,stroke:2*t.u+white,inset:2*t.u,clip:true)[#art(t,d,index,width:size - 4,height:size - 4)]
#let runs(t,parts) = {
  for part in parts {
    if part.avatar!="" {
      box(inset:(x:3*t.u,y:2*t.u),fill:rgb("e8edf3"),radius:14*t.u,stroke:.7*t.u+rgb("cbd2dd"),baseline:(at:bottom,shift:5*t.u))[
        #box(width:18*t.u,height:18*t.u,radius:50%,clip:true,baseline:25%)[#image(part.avatar,width:100%,height:100%,fit:"cover")]
        #if part.text!="" {h(3*t.u);text(size:.85em,part.text)}
      ]
    }else{for (i,line) in part.text.split("\n").enumerate(){if i>0 {linebreak()};line}}
  }
}
#let glass(t,body,padx:24,pady:24,radius:20,fill:none,stroke:1.5,height:none,background:none,clip:true,dy:6,blur:16,dots:none) = layout(size=>{
  let inner=block(width:size.width,inset:(x:(padx+stroke)*t.u,y:(pady+stroke)*t.u))[#body]
  let h=calc.max(measure(inner).height,if height==none {0pt}else{height*t.u})
  let panel=block(width:size.width,height:h,radius:radius*t.u,fill:if fill==none {gradient.linear(white.transparentize(20%),white.transparentize(60%),angle:45deg,space:rgb)}else{fill},stroke:stroke*t.u+white.transparentize(10%),outset:-stroke/2*t.u,clip:clip)[
    #if background!=none {place(top+left,block(width:size.width,height:h)[#background])}
    #inner
  ]
  // 原 HTML 将花点放在半透明渐变下面，保留顺序以免把浅色纹理画成深色斑点。
  let panel=if dots==none {panel}else{block(width:size.width,height:h)[
    #place(top+left,dx:stroke*t.u,dy:stroke*t.u,rect(width:size.width - 2*stroke*t.u,height:h - 2*stroke*t.u,radius:calc.max(0,radius - stroke)*t.u,stroke:none,fill:tiling(size:(24*t.u,24*t.u))[
      #place(top+left,dx:10*t.u,dy:10*t.u,circle(radius:2*t.u,fill:dots,stroke:none))
    ]))
    #panel
  ]}
  shadow(t,panel,radius:radius,blur:blur,dy:dy,color:rgb("557ea9").transparentize(96%))
})
#let label(t,d,title,subtitle,symbol,index) = box(inset:(left:8*t.u,right:24*t.u,y:8*t.u),fill:gradient.linear(white.transparentize(25%),white.transparentize(65%),angle:45deg,space:rgb),radius:20*t.u,stroke:1.5*t.u+white.transparentize(5%))[
  #grid(columns:(42*t.u,auto),gutter:12*t.u,align:horizon,
    box(width:42*t.u,height:42*t.u,fill:gradient.linear(rgb("75c1f0").transparentize(82%),white.transparentize(8%),angle:45deg,space:rgb),radius:14*t.u)[#align(center+horizon,icon(t,symbol))],
    [#copy(t,[#title#h(6*t.u)#box(width:28*t.u,height:28*t.u,baseline:20%)[#sticker(t,d,index,size:28)]],size:22,weight:600,fill:deep)
      #v(4.1*t.u)#copy(t,subtitle,size:13,fill:muted)
      #place(top+right,dx:52*t.u,dy:-8*t.u,copy(t,"memo",size:11,fill:rgb("5ba0c9").transparentize(42%),mono:true,tracking:.08))])
]
#let section(t,d,title,subtitle,badge,symbol,index,badge-index,fill,body,dots:none) = {
  glass(t,stroke:2,fill:fill,dots:dots,[
    #place(top+right,dx:8*t.u,dy:-8*t.u,copy(t,"✦",size:14,fill:rgb("5cadd9").transparentize(64%)))
    #grid(columns:(auto,1fr),gutter:16*t.u,align:horizon,label(t,d,title,subtitle,symbol,index),align(right)[
      #box(inset:(x:12*t.u,y:6*t.u),fill:rgb("74c8f3").transparentize(88%),radius:100*t.u)[#copy(t,[#badge#h(6*t.u)#box(width:22*t.u,height:22*t.u,baseline:20%)[#sticker(t,d,badge-index,size:22)]],size:12,fill:deep)]
    ])
    #v(18*t.u)#body
  ])
}
#let header(t,d) = context {
  let eyebrow=box(inset:(x:14*t.u,y:6*t.u),stroke:1*t.u+white.transparentize(40%),radius:100*t.u)[#copy(t,"A.T.R.I · Daily Communication Report",size:13,fill:white,tracking:.077)]
  let left-copy=block(width:492.8*t.u)[
    #eyebrow
    #v(12*t.u)#copy(t,"亚托莉的群聊观测日志",size:38,weight:600,fill:white,lh:1.2)
    #v(12*t.u)#copy(t,"主人，今天群里的大家也超级精神呢！身为高性能的亚托莉，已经把所有闪闪发光的聊天记忆，像打捞海底宝藏一样全都收集好啦！",size:15,lh:1.8,fill:white.transparentize(8%))
  ]
  let date-box=box(width:220*t.u,inset:(x:24*t.u,y:18*t.u),stroke:1.5*t.u+white.transparentize(40%),radius:20*t.u)[#align(center)[
    #copy(t,"REPORT GENERATED",size:11,weight:600,fill:white,tracking:.227)#v(8*t.u)
    #copy(t,"✦",size:11,fill:white.transparentize(30%))#v(6*t.u)
    #copy(t,[#d.date#linebreak()#d.generated_at],size:15,weight:600,fill:white,mono:true,lh:1.7,tracking:.033)
  ]]
  // 按实际文字高度定位玻璃区域，日期换行或字体变化时仍与前景同步。
  let content-height=calc.max(measure(left-copy).height,measure(date-box).height)/t.u
  let header-height=content-height+60.74
  let eyebrow-size=measure(eyebrow)
  let date-height=measure(date-box).height/t.u
  // CSS 的角度以画布的投影长度计算，不按 SVG 的单位正方形拉伸渐变。
  let sea-length=834*calc.cos(30deg)+header-height*calc.sin(30deg)
  let sea-dx=sea-length*calc.cos(30deg)/2
  let sea-dy=sea-length*calc.sin(30deg)/2
  let shine-d=(834+header-height)/4
  let diagonal=" x1='"+str(417-shine-d)+"' y1='"+str(header-height/2-shine-d)+"' x2='"+str(417+shine-d)+"' y2='"+str(header-height/2+shine-d)+"' gradientUnits='userSpaceOnUse'"
  let defs="<linearGradient id='sea' gradientUnits='userSpaceOnUse' x1='"+str(417-sea-dx)+"' y1='"+str(header-height/2-sea-dy)+"' x2='"+str(417+sea-dx)+"' y2='"+str(header-height/2+sea-dy)+"'><stop stop-color='#2c76a1' stop-opacity='.78'/><stop offset='.56' stop-color='#58b0dd' stop-opacity='.62'/><stop offset='1' stop-color='#aee2f7' stop-opacity='.38'/></linearGradient>"
  defs+="<linearGradient id='base-shine'"+diagonal+"><stop stop-color='white' stop-opacity='.1'/><stop offset='.5' stop-color='white' stop-opacity='0'/></linearGradient><linearGradient id='shine'"+diagonal+"><stop stop-color='white' stop-opacity='.22'/><stop offset='.45' stop-color='white' stop-opacity='0'/></linearGradient>"
  defs+="<radialGradient id='glow' gradientUnits='userSpaceOnUse' cx='700.56' cy='"+str(header-height*.24)+"' r='"+str(calc.sqrt(calc.pow(700.56,2)+calc.pow(header-height*.76,2))*.2)+"'><stop stop-color='white' stop-opacity='.52'/><stop offset='1' stop-color='white' stop-opacity='0'/></radialGradient><linearGradient id='top-shine' x2='0' y2='1'><stop stop-color='white' stop-opacity='.25'/><stop offset='1' stop-color='white' stop-opacity='0'/></linearGradient>"
  let scene=""
  let path=d.decorations.at(0,default:"")
  if path!="" {scene+="<image href='"+path+"' width='834' height='"+str(header-height)+"' preserveAspectRatio='xMidYMid slice'/>"}
  for paint in ("base-shine","sea","glow","shine") {scene+="<rect width='834' height='"+str(header-height)+"' fill='url(#"+paint+")'/>"}
  defs+="<g id='scene'>"+scene+"</g>"
  let layers="<use href='#scene'/>"
  for (name,x,y,width,height,blur,radius,opacity) in (
    ("eyebrow",32,30,eyebrow-size.width/t.u,eyebrow-size.height/t.u,12,100,.35),
    ("date",582,30 + content-height - date-height,220,date-height,16,20,.4),
  ) {
    // 只计算卡片及三倍标准差的周边，避免对整幅海景反复分配滤镜缓冲。
    let pad=blur*3
    let dimensions=" x='"+str(x)+"' y='"+str(y)+"' width='"+str(width)+"' height='"+str(height)+"'"
    let delta=(width+height)/4
    defs+="<filter id='f-"+name+"' filterUnits='userSpaceOnUse' x='"+str(x - pad)+"' y='"+str(y - pad)+"' width='"+str(width+pad*2)+"' height='"+str(height+pad*2)+"' color-interpolation-filters='sRGB'><feGaussianBlur stdDeviation='"+str(blur)+"'/></filter>"
    defs+="<clipPath id='c-"+name+"'><rect"+dimensions+" rx='"+str(calc.min(radius,width/2,height/2))+"'/></clipPath>"
    defs+="<linearGradient id='g-"+name+"' gradientUnits='userSpaceOnUse' x1='"+str(x+width/2-delta)+"' y1='"+str(y+height/2-delta)+"' x2='"+str(x+width/2+delta)+"' y2='"+str(y+height/2+delta)+"'><stop stop-color='white' stop-opacity='"+str(opacity)+"'/><stop offset='1' stop-color='white' stop-opacity='.1'/></linearGradient>"
    layers+="<g clip-path='url(#c-"+name+")'><use href='#scene' filter='url(#f-"+name+")'/><rect"+dimensions+" fill='url(#g-"+name+")'/>"
    if name=="date" {layers+="<rect x='"+str(x)+"' y='"+str(y)+"' width='"+str(width)+"' height='"+str(height/2)+"' fill='url(#top-shine)'/>"}
    layers+="</g>"
  }
  let svg="<svg xmlns='http://www.w3.org/2000/svg' width='834' height='"+str(header-height)+"'><defs>"+defs+"</defs>"+layers+"</svg>"
  // str 的负数使用 Unicode 负号，SVG 数字只接受 ASCII 连字符。
  let backdrop=image(bytes(svg.replace("−","-")),format:"svg",width:834*t.u,height:header-height*t.u)
  glass(t,padx:32,pady:0,radius:22,stroke:0,background:backdrop,dy:16,blur:40,[
    #v(30*t.u)
    #grid(columns:(1fr,220*t.u),gutter:24*t.u,align:bottom,left-copy,date-box)
    #v(30.74*t.u)
  ])
}
#let hero(t,d) = {
  grid(columns:(1fr,1fr),gutter:20*t.u,
    glass(t,padx:0,pady:0,stroke:2,radius:22,fill:gradient.linear(rgb("ffe6ea").transparentize(10%),rgb("fff0f5").transparentize(30%),angle:45deg,space:rgb),height:418,background:place(bottom+right,dx:-10*t.u,art(t,d,1,width:205)),[
      #block(width:100%,inset:(left:28*t.u,right:200*t.u,top:28*t.u,bottom:22*t.u))[
        #box(inset:(left:8*t.u,right:24*t.u,y:8*t.u),radius:20*t.u,stroke:1.5*t.u+white,fill:white.transparentize(40%))[
          #grid(columns:(42*t.u,auto,22*t.u),gutter:12*t.u,align:horizon,box(width:42*t.u,height:42*t.u,radius:14*t.u,fill:rgb("f4f8ff"))[#align(center+horizon,icon(t,"sparkles",size:16))],copy(t,"Overview",size:14,weight:600),sticker(t,d,4,size:22))
        ]
        #v(20*t.u)#copy(t,[来看看今天#linebreak()都发生了什#linebreak()么吧！],size:34,weight:600,lh:1.25)
        #v(14*t.u)#copy(t,[报告主人！今天一共捕获了 #text(weight:600,str(d.message_count)) 条消息，有 #text(weight:600,str(d.participant_count)) 位群友浮出水面参与了互动哦！我都仔细做好了备忘录哦，哼哼！],size:15,lh:1.9,fill:muted)
      ]
    ]),
    glass(t,padx:0,pady:0,stroke:2,radius:22,fill:gradient.linear(rgb("74c8f3"),rgb("dcd3ff"),angle:50deg,space:rgb),height:418,background:[
      #place(top+right,dx:-8*t.u,dy:18*t.u,copy(t,"ACTIVE",size:72,fill:white.transparentize(88%),mono:true,tracking:.028))
      #place(bottom+right,dx:-6*t.u,dy:30*t.u,art(t,d,2,width:205))
    ],[
      #block(width:100%,inset:(left:24*t.u,right:175*t.u,y:24*t.u))[
        #box(radius:16*t.u,inset:(x:18*t.u,y:8*t.u),fill:white.transparentize(40%),stroke:1.5*t.u+white.transparentize(10%))[
          #copy(t,"MOST ACTIVE PERIOD",size:13,fill:deep,tracking:.077)
        ]
        #v(14*t.u)#copy(t,d.generated_at,size:12,mono:true,fill:white.transparentize(12%))
        #v(16*t.u)#box(width:300*t.u)[#copy(t,d.peak,size:32,weight:600,mono:true,fill:white,lh:1.3)]
        #v(28*t.u)#copy(t,"这段时间的心跳值达到最高峰！大家的讨论就像退缩时沙滩上的贝壳一样密集，是今天最棒的高光时刻！",size:16,fill:white.transparentize(5%),lh:1.8)
      ]
    ]))
}
#let statistics(t,d) = {
  let stats=(("消息总数",d.message_count,"message-circle","ffe6ea","ff8eaa"),("参与人数",d.participant_count,"users","dcf5ff","72bcf5"),("总字符数",d.characters,"text","fff9d7","f5b742"),("表情数量",d.emoji_count,"smile","f0ebff","aa8af5"))
  grid(columns:(1fr,)*4,gutter:16*t.u,..stats.map(s=>glass(t,padx:16,pady:14,stroke:2,radius:18,fill:gradient.linear(rgb(s.at(3)).transparentize(10%),white.transparentize(20%),angle:45deg,space:rgb),[
    #grid(columns:(36*t.u,auto,auto),column-gutter:(12*t.u,8*t.u),align:horizon,
      box(width:36*t.u,height:36*t.u,fill:white.transparentize(30%),stroke:1.5*t.u+white,radius:12*t.u)[#align(center+horizon,icon(t,s.at(2),size:18,fill:rgb(s.at(4))))],
      copy(t,str(s.at(1)),size:22,weight:600,mono:true,lh:1),box(copy(t,s.at(0),size:13,fill:muted)))
  ])))
}
#let activity(t,d) = section(t,d,"心跳潮汐","一整天的心跳节拍，由亚托莉为您完美记录","TIDE CHART","bar-chart-3",5,11,gradient.linear(rgb("c8f5e6").transparentize(10%),rgb("dcfaf0").transparentize(15%),angle:90deg,space:rgb),dots:rgb("82dcb9").transparentize(65%),[
  #v(32*t.u)
  #glass(t,padx:24,pady:24,[
    #block(width:100%,height:220*t.u,inset:(top:20*t.u,bottom:10*t.u))[
      #let highest=calc.max(1,..d.hours)
      #grid(columns:(1fr,)*24,gutter:5*t.u,..d.hours.enumerate().map(((i,n))=>{
        let ratio=i/23
        let r=if ratio<.3333 {ratio/.3333}else if ratio<.6666 {(ratio - .3333)/.3333}else{(ratio - .6666)/.3334}
        let top-color=if ratio<.3333 {(210+r*45,225+r*15,255-r*25)}else if ratio<.6666 {(255-r*20,240+r*15,230+r*10)}else{(235-r*25,255-r*30,240+r*15)}
        let bottom-color=if ratio<.3333 {(170+r*85,190-r*5,255-r*55)}else if ratio<.6666 {(255-r*105,185+r*45,200)}else{(150+r*20,230-r*40,200+r*55)}
        let a=rgb(..top-color.map(x=>calc.round(x)/255*100%))
        let b=rgb(..bottom-color.map(x=>calc.round(x)/255*100%))
        let bar=calc.max(5,158*n/highest)
        block(height:190*t.u,width:100%)[
          #place(bottom+center,dy:-18*t.u,block(width:100%)[
            #align(center,copy(t,str(n),size:10,weight:700,fill:rgb(..bottom-color.map(x=>calc.round(calc.round(x)*.7)/255*100%)),lh:1))#v(4*t.u)
            #align(center,rect(width:100% - 4*t.u,height:bar*t.u,fill:gradient.linear(a,b,angle:90deg,space:rgb),stroke:none,radius:(top-left:10*t.u,top-right:10*t.u)))
          ])
          #place(bottom+center,copy(t,str(i),size:10,fill:rgb("9a8aa3"),lh:1))
        ]
      }))
    ]
  ])
])
#let topics(t,d) = section(t,d,"高亮记忆碎片","亚托莉捕获的最亮眼的记忆碎片！","TOPIC BOARD","flame",6,5,gradient.linear(rgb("ffd7e1").transparentize(10%),rgb("ffebf2").transparentize(15%),angle:90deg,space:rgb),dots:rgb("ff96b4").transparentize(65%),[
  #let ranks=(("a9d8ff","8fc5ff","8aaeff"),("ffc8d8","ffb7cd","ffb2b2"),("ffe0ad","ffd29f","ffc3b8"),("c7efe7","bfe7ff","c8d8ff"))
  #for (i,topic) in d.topics.enumerate() {
    let colors=ranks.at(calc.rem(i,4)).map(x=>rgb(x))
    glass(t,padx:20,pady:16,background:[
      #place(top+right,dx:-60*t.u,dy:-6*t.u,box(width:48*t.u,height:12*t.u,fill:rgb("ffb3c6").transparentize(40%),stroke:1*t.u+white,radius:4*t.u))
      #place(bottom+right,dx:-14*t.u,dy:-12*t.u,sticker(t,d,14+calc.rem(i,5)))
    ],clip:false,[
      #copy(t,[#box(radius:100*t.u,inset:(x:10*t.u,y:3*t.u),fill:gradient.linear(..colors,angle:45deg,space:rgb),stroke:1*t.u+white.transparentize(18%))[
        #text(size:14*t.u,weight:600,fill:muted)[\##(i+1)]
      ]#h(14*t.u)#topic.title],size:18,weight:600,fill:deep)
      #v(6*t.u)#copy(t,[#text(weight:600,fill:sea)[参与的群友:] #runs(t,topic.contributors)],fill:muted,lh:1.7)
      #v(8*t.u)#block(width:100% - 76*t.u,inset:(x:18*t.u,y:12*t.u),fill:gradient.linear(rgb("f5faff").transparentize(5%),rgb("ecf7ff").transparentize(12%),angle:90deg,space:rgb),stroke:1.5*t.u+white.transparentize(20%),radius:16*t.u)[#copy(t,runs(t,topic.detail),lh:1.6)]
    ])
    if i < d.topics.len() - 1 {v(12*t.u)}
  }
  #v(12*t.u)
])
#let portraits(t,d) = context {
  let colors=(("ffcadf","ffc1cc","ffd9b8","b85c7b"),("bfe7ff","c8dbff","d8ccff","5d71b8"),("c7f3df","d3f1ff","e1ddff","4e8e88"),("ffe5b7","ffd6c7","ffd7ef","b57752"))
  let cards=d.portraits.enumerate().map(((i,p))=>{
    let c=colors.at(calc.rem(i,4)).map(x=>rgb(x))
    let body=[
      #block(width:100% - 72*t.u)[
        #grid(columns:(50*t.u,1fr),gutter:15*t.u,align:horizon,
          box(width:50*t.u,height:50*t.u,radius:50%,clip:true,stroke:2*t.u+rgb("667eea"),fill:white)[#if p.avatar!="" {image(p.avatar,width:100%,height:100%,fit:"cover")}],
          [#copy(t,[#p.name#h(10*t.u)#box(inset:(x:10*t.u,y:5*t.u),radius:100*t.u,fill:gradient.linear(c.at(0),c.at(1),c.at(2),angle:45deg,space:rgb),stroke:1*t.u+c.at(0))[
              #text(size:14.04*t.u,weight:600,fill:muted,p.title)
            ]],size:18,weight:600,fill:deep)
            #v(6*t.u)#copy(t,[#text(weight:600,fill:sea)[人格标签:] #p.profile],fill:muted,lh:1.7)
            #v(6*t.u)#copy(t,[#text(weight:600,fill:sea)[称号理由:] #runs(t,p.reason)],fill:muted,lh:1.7)
          ])
      ]
    ]
    let background=[
      #if p.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(p.image,width:136.8*t.u,height:140*t.u,fit:p.image_fit))}
      #place(bottom+right,dx:-14*t.u,dy:-12*t.u,sticker(t,d,19+calc.rem(i,3)))
      #place(top+right,dx:-60*t.u,dy:-6*t.u,box(width:48*t.u,height:12*t.u,fill:rgb("fff3b0").transparentize(20%),stroke:1*t.u+white,radius:4*t.u))
    ]
    (body:body,background:background,height:measure(body,width:338*t.u).height/t.u+35)
  })
  section(t,d,"神人名片颁发","颁发给各位的高性能称号！","SPOTLIGHT","badge-check",7,8,gradient.linear(rgb("fff0b4").transparentize(10%),rgb("fffad7").transparentize(15%),angle:90deg,space:rgb),dots:rgb("ffdc64").transparentize(65%),[
    #for (i,row) in cards.chunks(2).enumerate() {
      let height=calc.max(..row.map(x=>x.height))
      grid(columns:(1fr,1fr),gutter:20*t.u,..row.map(x=>glass(t,x.body,padx:20,pady:16,height:height,background:x.background)))
      if i < calc.ceil(cards.len()/2) - 1 {v(18*t.u)}
    }
  ])
}
#let quotes(t,d) = section(t,d,"亚托莉的宝藏瓶","亚托莉偷偷记在小本子上的宝藏名言！","PRECIOUS WORDS","quote",9,10,gradient.linear(rgb("d7beff").transparentize(5%),rgb("e1cdff").transparentize(10%),angle:90deg,space:rgb),dots:rgb("b48cff").transparentize(65%),[
  #for (i,q) in d.quotes.enumerate() {
    let even=calc.odd(i)
    let photo=box(width:44*t.u,height:44*t.u)[
      #place(top+left,dx:-2*t.u,dy:-2*t.u,circle(radius:24*t.u,stroke:2*t.u+if even {rgb("dcd3ff")}else{sky},fill:none))
      #box(width:44*t.u,height:44*t.u,radius:50%,clip:true,fill:white,inset:2*t.u)[#if q.avatar!="" {image(q.avatar,width:100%,height:100%,fit:"cover")}]
    ]
    let content=[
      #align(if even {right}else{left})[
        #copy(t,if q.sender=="" {"匿名群友"}else{q.sender},size:13,fill:muted)#v(4*t.u)
        #let bubble=box(inset:(x:16*t.u,y:10*t.u),radius:(top-left:if even {18*t.u}else{4*t.u},top-right:if even {4*t.u}else{18*t.u},bottom-left:18*t.u,bottom-right:18*t.u),stroke:1*t.u+white,fill:gradient.linear(rgb("f6eeff").transparentize(5%),white.transparentize(2%),space:rgb))[
          #copy(t,runs(t,q.content),size:15,lh:1.6)
        ]
        #grid(columns:if even {(44*t.u,auto)}else{(auto,44*t.u)},gutter:8*t.u,align:bottom,..if even {(sticker(t,d,22+calc.rem(i,3)),bubble)}else{(bubble,sticker(t,d,22+calc.rem(i,3)))})
        #v(6*t.u)#box(inset:(x:14*t.u,y:8*t.u),radius:12*t.u,stroke:1*t.u+rgb("75c1f0").transparentize(85%),fill:gradient.linear(rgb("f6eeff").transparentize(5%),white.transparentize(5%),space:rgb))[
          #copy(t,[#box(width:13*t.u,height:13*t.u,baseline:20%)[#icon(t,"notebook-pen",size:13,fill:rgb("f59b72"))]#h(4*t.u)#text(weight:600)[亚托莉的高性能分析:] #runs(t,q.reason)],size:13,fill:muted,lh:1.5)
        ]
      ]
    ]
    glass(t,padx:20,pady:14,[#grid(columns:if even {(1fr,44*t.u)}else{(44*t.u,1fr)},gutter:12*t.u,..if even {(content,photo)}else{(photo,content)})])
    v(14*t.u)
  }
])
#let quality(t,d) = {
  let r=d.review
  section(t,d,"亚托莉观测报告","来自高性能亚托莉的每日特别观测报告！","GROUP VIBE","flower-2",11,5,gradient.linear(rgb("ffcdaf").transparentize(5%),rgb("ffe1c3").transparentize(10%),angle:90deg,space:rgb),dots:rgb("ffb48c").transparentize(55%),[
    #v(24*t.u)
    #glass(t,padx:24,pady:24,radius:24,stroke:1,fill:gradient.linear(rgb("fff0e6").transparentize(5%),white.transparentize(2%),space:rgb),background:place(top+right,dx:-18*t.u,dy:14*t.u,copy(t,"锐评",size:46,weight:700,fill:rgb("53abdb").transparentize(92%),tracking:.087)),[
      #copy(t,r.title,size:28,weight:700,fill:rgb("2a6587"))#v(4*t.u)
      #box(inset:(x:12*t.u,y:7*t.u),radius:100*t.u,fill:rgb("75cbf4").transparentize(84%))[
        #copy(t,r.subtitle,size:14,fill:rgb("5492b7"))
      ]
      #v(18*t.u)
      #for (i,x) in r.dimensions.enumerate() {
        let color=rgb(x.at("color",default:"#607d8b"))
        let faded=rgb(..color.components().slice(0,3).map(c=>c*.65+35%))
        grid(columns:(94*t.u,1fr,54*t.u),gutter:12*t.u,align:horizon,copy(t,x.name,size:14,weight:600,fill:rgb("52768d")),
          block(width:100%,height:12*t.u,radius:100*t.u,fill:rgb("7ec7eb").transparentize(84%),clip:true)[#rect(width:x.percentage*1%,height:12*t.u,radius:100*t.u,stroke:none,fill:gradient.linear(color,faded,space:rgb))],
          align(right,copy(t,[#x.percentage%],size:13,weight:700,fill:rgb("5d88a3"))))
        if i < r.dimensions.len() - 1 {v(12*t.u)}
      }
      #if r.dimensions.len()>0 {v(16*t.u)}
      #grid(columns:(1fr,1fr),gutter:12*t.u,..r.dimensions.map(x=>block(width:100%,inset:(x:14*t.u,top:14*t.u,bottom:12*t.u),radius:16*t.u,fill:white.transparentize(26%),stroke:(paint:rgb("71bfed").transparentize(66%),thickness:1*t.u,dash:"dashed"))[
        #copy(t,x.name,weight:600,fill:rgb("3f84ad"))#v(6*t.u)#copy(t,runs(t,x.comment),lh:1.25)
      ]))
      #if r.dimensions.len()>0 {v(16*t.u)}
      #block(width:100%,inset:(x:16*t.u,y:14*t.u),radius:18*t.u,fill:white.transparentize(35%),stroke:1*t.u+rgb("70bdec").transparentize(80%))[
        #copy(t,runs(t,r.summary),fill:rgb("4f7389"),lh:1.8)
      ]
    ])
  ])
}
#let energy(t,d) = block(width:66%)[
  #section(t,d,"能量解析雷达","维持亚托莉运行与心跳的能量消耗~","ENERGY COST","sparkles",12,13,gradient.linear(rgb("b4e4ff").transparentize(5%),rgb("d2f0ff").transparentize(10%),angle:90deg,space:rgb),dots:rgb("78b9ff").transparentize(55%),[
    #v(6*t.u)
    #grid(columns:(1fr,1fr,1fr),gutter:14*t.u,..("总消耗","提示词 Token","生成内容 Token").enumerate().map(((i,s))=>glass(t,padx:16,pady:16,[
      #copy(t,s,size:13,fill:muted)#v(8*t.u)#copy(t,str(d.tokens.at(i)),size:24,fill:deep,mono:true)
    ])))
  ])
]
#let footer(t,d) = block(width:66%)[
  #glass(t,padx:24,pady:24,stroke:2,fill:gradient.linear(rgb("b4e4ff").transparentize(5%),rgb("d2f0ff").transparentize(10%),angle:90deg,space:rgb),dots:rgb("78b9ff").transparentize(55%),[
    #copy(t,[#box(width:14*t.u,height:14*t.u,baseline:20%)[#icon(t,"heart",size:14,fill:deep,solid:true)]#h(6*t.u)ATRI | Template by Liangyu-G],weight:600,fill:deep)
    #v(10*t.u)#copy(t,[#box(width:14*t.u,height:14*t.u,baseline:20%)[#icon(t,"github",size:14,fill:deep)]#h(6*t.u)SXP-Simon/astrbot_plugin_qq_group_daily_analysis],size:11,weight:600,fill:deep,mono:true)
    #v(6*t.u)#copy(t,"亚托莉会永远把大家珍贵的聊天记忆藏在海底哦。",size:13,fill:muted)
  ])
]
#let render(d,t) = {
  let fallback=if d.font_language=="zh-Hant" {"Noto Sans TC"}else{"Noto Sans SC"}
  t.insert("font",("LXGW WenKai",fallback));t.insert("mono",("LXGW WenKai Mono",..t.font))
  set page(width:940*t.u,height:auto,margin:0pt,fill:white)
  set text(font:t.font,size:16*t.u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none)
  set par(leading:0pt,spacing:0pt)
  let dots=tiling(size:(22*t.u,22*t.u))[
    #place(top+left,dx:3.4*t.u,dy:4.6*t.u,circle(radius:2*t.u,fill:rgb("76c4f0").transparentize(90%),stroke:none))
  ]
  set page(background:block(width:100%,height:100%,radius:28*t.u,clip:true,fill:rgb("dff4ff"),stroke:1*t.u+white)[
    #if d.decorations.at(0,default:"")!="" {place(top+left,image(d.decorations.at(0),width:100%,height:100%,fit:"cover"))}
    #place(top+left,rect(width:100%,height:100%,fill:gradient.linear(rgb("effaff").transparentize(28%),rgb("effaff").transparentize(8%),angle:90deg,space:rgb),stroke:none))
    #place(top+left,rect(width:100%,height:100%,fill:gradient.linear(white.transparentize(20%),rgb("f2fbff").transparentize(6%),angle:90deg,space:rgb),stroke:none))
    #place(top+left,rect(width:100%,height:100%,fill:dots,stroke:none))
    #place(top+right,dx:-76*t.u,dy:124*t.u,circle(radius:90*t.u,stroke:(paint:rgb("72c8f4").transparentize(76%),thickness:2*t.u,dash:"dashed"),fill:none))
    #place(bottom+right,dx:8*t.u,dy:18*t.u,art(t,d,3,width:440))
    #for (p,x,name,color) in ((5,-14,"heart","ff90b3"),(8,904,"star","7bcdf3"),(12,18,"heart-handshake","ff9ec4"),(18,882,"notebook-pen","8fc8ff"),(20,-8,"cloud","a5d8ff"),(28,10,"fish","7fcff3"),(28,899,"shell","9dcfff"),(36,-8,"heart","ff9fc0"),(38,880,"star","ffd79c"),(44,-12,"flower-2","ff9bb8"),(48,874,"moon-star","78c7f0"),(52,10,"wand-sparkles","ffd38f"),(60,-18,"sparkles","8ac7ff"),(58,906,"badge-check","ffb2cf"),(68,12,"gem","a9b8ff"),(68,879,"moon-star","88cfff"),(76,-6,"flower-2","ffb0c8"),(78,899,"sparkles","a9b9ff"),(84,24,"gift","8fd4ff")) {
      place(top+left,dx:x*t.u,dy:p*1%,box(width:46*t.u,height:46*t.u,fill:white.transparentize(8%),stroke:1*t.u+rgb("95d2f2").transparentize(66%),radius:14*t.u)[#align(center+horizon,icon(t,name,fill:rgb(color)))])
    }
  ])
  set page(foreground:place(top+right,dx:-40*t.u,dy:10*t.u,copy(t,"ATRI",size:156,fill:rgb("4ba9dc").transparentize(65%),mono:true,tracking:.0385,lh:1)))
  block(width:940*t.u,inset:(x:53*t.u,top:71*t.u,bottom:94*t.u))[
    #header(t,d)#v(28*t.u)#hero(t,d)#v(28*t.u)#statistics(t,d)#v(28*t.u)#activity(t,d)#v(24*t.u)
    #if d.topics.len()>0 {topics(t,d);v(24*t.u)}
    #if d.portraits.len()>0 {portraits(t,d);v(24*t.u)}
    #if d.quotes.len()>0 {quotes(t,d);v(24*t.u)}
    #if d.review!=none {quality(t,d);v(24*t.u)}
    #energy(t,d)#v(24*t.u)#footer(t,d)
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

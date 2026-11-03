// 春节主题保留红包、木窗、印章和交错气泡；emoji 使用受管理彩色字体直接排字。
#import "common.typ":shadow
#let red=rgb("b71c1c")
#let gold=rgb("ffca28")
#let wood=rgb("3e2723")
#let paper=rgb("fff9e6")
#let palette=("f5222d","fa541c","fa8c16","faad14","d46b08","ad2102")
#let copy(t,body,size:16,weight:400,fill:wood,lh:none,font:none,tracking:0,italic:false) = {
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="calligraphy" {("Ma Shan Zheng",..t.body)}else if font=="heading" {("ZCOOL XiaoWei",..t.body)}else if font=="chart" {("Noto Sans SC",)}else{t.body}
  let baseline=if font in ("calligraphy","heading") {.38}else if font=="chart" {.36}else{.4325}
  let height=if lh!=none {lh}else if font in ("calligraphy","heading") {1}else{1.4375}
  let result=text(font:fonts,size:size*t.u,weight:weight,fill:fill,tracking:tracking*1em,stroke:if font in ("calligraphy","heading") and weight>500 {.03*size*t.u+fill}else{none},style:if italic {"italic"}else{"normal"},top-edge:(height/2+baseline)*1em,bottom-edge:-(height/2-baseline)*1em,body)
  if italic {
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*"):it=>box(height:height*size*t.u,baseline:(at:top,shift:-(height/2+baseline)*size*t.u))[#skew(ax:-12deg,origin:bottom+left,it)]
    result
  }else{result}
}
#let emoji(t,symbol,size:16) = text(font:"Noto Color Emoji",size:size*t.u,symbol)
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
#let frame(t,body,padx:25,pady:25,stroke:2,color:red,fill:white,radius:0,left-width:none,right-width:none,accent:none,blur:0,dx:0,dy:0,shade:red.transparentize(90%),hard:false,height:none,centered:false,stamp:none,dots:none,watermark:none) = layout(size=>{
  let lw=if left-width==none {stroke}else{left-width}
  let rw=if right-width==none {stroke}else{right-width}
  let inside=block(width:size.width,inset:(left:(padx+lw)*t.u,right:(padx+rw)*t.u,y:(pady+stroke)*t.u))[#body]
  let h=measure(inside).height
  if height!=none {h=calc.max(h,height*t.u)}
  let radii=(:)
  if type(radius)==dictionary {for (k,v) in radius {radii.insert(k,v*t.u)}}else{radii=radius*t.u}
  if hard {place(top+left,dx:dx*t.u,dy:dy*t.u,rect(width:size.width,height:h,radius:radii,fill:shade,stroke:none))}
  else if blur>0 {
    if type(radius)==dictionary {
      // 红包下缘的大圆角必须参与投影，避免用普通圆角投影露出矩形色块。
      let w=size.width/t.u
      let hh=h/t.u
      let a=radius.at("top-left",default:0)
      let b=radius.at("top-right",default:0)
      let c=radius.at("bottom-right",default:0)
      let d=radius.at("bottom-left",default:0)
      let path="M"+str(a)+" 0H"+str(w - b)+"A"+str(b)+" "+str(b)+" 0 0 1 "+str(w)+" "+str(b)+"V"+str(hh - c)+"A"+str(c)+" "+str(c)+" 0 0 1 "+str(w - c)+" "+str(hh)+"H"+str(d)+"A"+str(d)+" "+str(d)+" 0 0 1 0 "+str(hh - d)+"V"+str(a)+"A"+str(a)+" "+str(a)+" 0 0 1 "+str(a)+" 0Z"
      let pad=2*blur+calc.abs(dx)+calc.abs(dy)
      let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w+2*pad)+"' height='"+str(hh+2*pad)+"'><defs><filter id='s' filterUnits='userSpaceOnUse' x='0' y='0' width='"+str(w+2*pad)+"' height='"+str(hh+2*pad)+"'><feGaussianBlur stdDeviation='"+str(blur/2)+"'/></filter></defs><path transform='translate("+str(pad+dx)+" "+str(pad+dy)+")' d='"+path+"' fill='"+shade.to-hex()+"' filter='url(#s)'/></svg>"
      place(top+left,dx:-pad*t.u,dy:-pad*t.u,image(bytes(svg),format:"svg",width:(w+2*pad)*t.u,height:(hh+2*pad)*t.u))
    }else{place(top+left,dx:dx*t.u,shadow(t,block(width:size.width,height:h),radius:radius,blur:blur,dy:dy,color:shade))}
  }
  block(width:size.width,height:h,fill:fill,radius:radii,stroke:(rest:stroke*t.u+color,left:lw*t.u+(if accent==none {color}else{accent}),right:rw*t.u+color),outset:(rest:-stroke/2*t.u,left:-lw/2*t.u,right:-rw/2*t.u),clip:true)[
    #if dots!=none {place(top+left,rect(width:size.width,height:h,fill:tiling(size:(dots.step*t.u,dots.step*t.u))[#place(top+left,dx:(dots.step/2 - 1)*t.u,dy:(dots.step/2 - 1)*t.u,circle(radius:1*t.u,fill:dots.color,stroke:none))],stroke:none))}
    #if stamp!=none {place(if stamp.bottom {bottom+right}else{top+right},dx:stamp.x*t.u,dy:stamp.y*t.u,rotate(stamp.angle,reflow:false,copy(t,stamp.text,size:stamp.size,font:stamp.font,fill:stamp.fill)))}
    #if centered {align(horizon,inside)}else{inside}
    #if watermark!=none and watermark.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(watermark.image,width:size.width*.36,height:calc.min(measure(image(watermark.image,width:size.width*.36)).height,h*.78),fit:watermark.image_fit))}
  ]
})
#let heading(t,symbol,title) = {
  block(width:100%,height:65*t.u,fill:gradient.linear(red.transparentize(95%),red.transparentize(100%),angle:0deg,space:rgb))[
    #grid(columns:(19.2*t.u,38.4*t.u,1fr),gutter:15*t.u,align:horizon,
      emoji(t,"☁️",size:19.2),emoji(t,symbol,size:38.4),copy(t,title,size:38.4,font:"calligraphy",fill:red,lh:51/38.4))
    #place(bottom+left,rect(width:100%,height:2*t.u,fill:red,stroke:none))
    #place(bottom+left,dy:3*t.u,polygon((0pt,0pt),(80*t.u,0pt),(68*t.u,8*t.u),(0pt,8*t.u),fill:gold,stroke:none))
  ]
  v(35*t.u)
}
#let header(t,d) = {
  // 原版在 940px 下将末尾红包折到第二行；整块牌匾一起倾斜。
  let title=block(width:100%,inset:(x:63*t.u,y:23*t.u),fill:red,stroke:1*t.u+gold,outset:-.5*t.u)[
    #place(top+left,dx:-61*t.u,dy:-21*t.u,rect(width:746*t.u,height:234*t.u,fill:none,stroke:1*t.u+gold))
    #align(center)[
      #place(top+center,dx:3*t.u,dy:3*t.u,copy(t,[#hide(emoji(t,"🧧",size:80)) 春节特供日报#linebreak()#hide(emoji(t,"🧧",size:80))],size:80,weight:700,fill:black.transparentize(80%),font:"calligraphy",lh:1.2))
      #copy(t,[#emoji(t,"🧧",size:80) 春节特供日报#linebreak()#emoji(t,"🧧",size:80)],size:80,weight:700,fill:gold,font:"calligraphy",lh:1.2)
    ]
  ]
  skew(ax:-5deg,origin:center,reflow:false,title)
  v(15*t.u)
  align(center,copy(t,[—— #d.date · 岁在丙午 ——],size:24,weight:700,font:"heading",fill:red,lh:32/24))
  v(60*t.u)
}
#let statistics(t,d) = layout(size=>{
  // flex-basis 分配需扣掉巅峰卡片的固定内边距，得到原 HTML 的 410.625 / 314.375。
  let left-width=410.625*t.u
  let right-width=size.width - left-width - 25*t.u
  let peak=align(center)[
    #copy(t,"巅峰时刻",size:32,font:"calligraphy",fill:red,lh:1)#v(5*t.u)
    #copy(t,d.peak,size:51.2,weight:800,font:"heading",lh:1)
    #v(12*t.u)#copy(t,[#emoji(t,"🏮",size:14.4) 鸿运齐天 · 众友云集 #emoji(t,"🏮",size:14.4)],size:14.4,weight:700,fill:red,lh:21/14.4)
  ]
  let peak-height=calc.max(218.4,measure(peak,width:right-width - 68*t.u).height/t.u+68)
  let extra=calc.max(0,peak-height - (90+108.4+20))/2
  let entries=(("消息总数",d.message_count,16),("参与群友",d.participant_count,16),("表情统计",d.emoji_count,16),("总字符数",d.characters,28.8))
  grid(columns:(left-width,right-width),gutter:25*t.u,align:top,
    grid(columns:(1fr,1fr),gutter:20*t.u,..entries.enumerate().map(((i,e))=>frame(t,padx:15,pady:20,color:gold,fill:red,radius:(top-left:12,top-right:12,bottom-left:60,bottom-right:60),blur:15,dy:8,shade:black.transparentize(80%),centered:true,height:if i < 2 {90+extra}else{108.4+extra},stamp:(text:"福",font:"calligraphy",size:64,angle:15deg,bottom:false,x:10,y:-10,fill:gold.transparentize(90%)),align(center)[
      #copy(t,e.at(0),fill:gold)#copy(t,str(e.at(1)),size:e.at(2),fill:gold)
    ]))),
    frame(t,padx:30,pady:30,stroke:4,fill:gold,radius:20,hard:true,dx:8,dy:8,shade:red,centered:true,height:peak-height,[
      #peak
      #place(bottom+center,dy:24*t.u,copy(t,"YEAR OF THE HORSE",size:11.2,weight:700,fill:red.transparentize(50%),tracking:2/11.2))
    ]),
  )
  v(40*t.u)
})
#let quality(t,d) = {
  if d.review==none {return}
  heading(t,"🏺","聊天质量锐评")
  v(23*t.u)
  let r=d.review
  frame(t,padx:24,pady:24,fill:rgb("fff5f5"),color:rgb("ff4d4f"),radius:12,blur:15,dy:4,shade:rgb("ff4d4f").transparentize(85%),stamp:(text:"福",font:none,size:100,angle:15deg,bottom:false,x:15,y:-15,fill:rgb("ff4d4f").transparentize(95%)),[
    #align(center)[
      #copy(t,[#emoji(t,"🧧",size:25.6) #r.title #emoji(t,"🧧",size:25.6)],size:25.6,weight:700,fill:rgb("cf1322"),lh:36/25.6)
      #if r.subtitle!="" {v(5*t.u);copy(t,r.subtitle,fill:rgb("fa541c"),weight:500,lh:23/16)}
    ]
    #v(15*t.u)#rect(width:100%,height:2*t.u,fill:none,stroke:(paint:rgb("ffccc7"),thickness:2*t.u,dash:(array:(6*t.u,6*t.u))))#v(25*t.u)
    #block(width:100%,height:35*t.u,fill:rgb("fff1f0"),inset:1*t.u,radius:18*t.u,stroke:1*t.u+rgb("ffa39e"),outset:-.5*t.u,clip:true)[
      #layout(size=>{
        let total=calc.max(100,r.dimensions.map(x=>x.percentage).sum(default:0))
        for (i,x) in r.dimensions.enumerate() {
          if x.percentage>0 {
            let width=x.percentage/total*size.width
            let clusters=x.name.clusters()
            let label=x.name
            while measure(copy(t,label,size:14.4,weight:700,lh:1)).width>width - 8*t.u and clusters.len()>0 {
              clusters=clusters.slice(0,clusters.len()-1)
              label=clusters.join()+"…"
            }
            if width < 22.4*t.u {label=""}
            place(top+left,dx:r.dimensions.slice(0,i).map(x=>x.percentage).sum(default:0)/total*size.width,
              block(width:width,height:33*t.u,fill:rgb(palette.at(calc.rem(i,6))),stroke:if i < r.dimensions.len()-1 {(right:1*t.u+white.transparentize(70%))}else{none},outset:-.5*t.u,inset:(x:4*t.u),clip:true)[#align(center+horizon,copy(t,label,size:14.4,weight:700,fill:white,lh:1))])
          }
        }
      })
    ]
    #v(25*t.u)
    #layout(size=>{
      let bodies=r.dimensions.filter(x=>x.percentage>0).map(x=>[
        #copy(t,[#emoji(t,"✨",size:14.4) #x.name],size:14.4,weight:700,fill:rgb("cf1322"),lh:21/14.4)#v(5*t.u)
        #copy(t,[占比: #x.percentage%],size:11.808,weight:600,fill:rgb("fa541c"),lh:17/11.808)#v(5*t.u)
        #copy(t,runs(t,x.comment),size:14.4,lh:21/14.4)
      ])
      let width=(size.width - 15*t.u)/2
      for start in range(0,bodies.len(),step:2) {
        let row=bodies.slice(start,calc.min(start+2,bodies.len()))
        let height=calc.max(..row.map(body=>measure(body,width:width - 29*t.u).height/t.u+26))
        grid(columns:(width,width),gutter:15*t.u,..row.map(body=>frame(t,padx:12,pady:12,stroke:1,left-width:4,accent:rgb("f5222d"),color:rgb("ffccc7"),radius:8,height:height,[
          #body
        ])))
        if start+2 < bodies.len() {v(15*t.u)}
      }
    })
    #v(25*t.u)
    #frame(t,padx:15,pady:15,stroke:1,color:rgb("ff4d4f"),fill:rgb("fff1f0"),radius:10,[
      #copy(t,[#underline(stroke:2*t.u+rgb("ff4d4f"),offset:4*t.u,text(fill:rgb("cf1322"),weight:700)[#emoji(t,"📜") 分析总结])#h(10*t.u)#runs(t,r.summary)],fill:rgb("434343"),lh:1.6)
    ])
  ])
  v(25*t.u)
}
#let topics(t,d) = {
  if d.topics.len()==0 {return}
  heading(t,"🏮","核心话题回顾")
  v(23*t.u)
  for x in d.topics {
    frame(t,hard:true,dx:8,dy:8,[
      #copy(t,[#emoji(t,"🏮")#h(6*t.u)#x.title],size:28.8,font:"heading",fill:red,lh:30/28.8)
      #copy(t,[参与者: #runs(t,x.contributors)],size:14.4,fill:rgb("666666"),italic:true,lh:21/14.4)#v(15*t.u)
      #copy(t,runs(t,x.detail),size:17.6,lh:1.8)
    ])
    v(25*t.u)
  }
}
#let activity(t,d) = {
  heading(t,"📈","活跃时序图")
  block(width:100%,height:343*t.u,inset:10*t.u,fill:wood)[
    #block(width:100%,height:323*t.u,fill:white,clip:true)[
      #place(top+left,image(bytes("<svg xmlns='http://www.w3.org/2000/svg' width='730' height='323'><defs><filter id='inset' filterUnits='userSpaceOnUse' x='0' y='0' width='730' height='323'><feGaussianBlur in='SourceAlpha' stdDeviation='10' result='b'/><feComposite in='SourceAlpha' in2='b' operator='out' result='s'/><feFlood flood-color='#000' flood-opacity='.05'/><feComposite in2='s' operator='in'/></filter></defs><rect width='730' height='323' fill='white' filter='url(#inset)'/></svg>"),format:"svg",width:730*t.u,height:323*t.u))
      #place(top+center,dy:-20*t.u,box(inset:(x:25*t.u,y:5*t.u),fill:wood,radius:4*t.u)[#copy(t,"ACTIVITY CHRONICLE",size:14.4,fill:gold,lh:21/14.4)])
      #block(width:100%,inset:(x:25*t.u,top:53*t.u))[
        #let highest=calc.max(1,..d.hours)
        #grid(columns:(1fr,)*24,gutter:2*t.u,..d.hours.enumerate().map(((hour,count))=>align(center)[
          #box(width:100%,height:210*t.u)[#align(bottom)[
            #if count>0 {copy(t,str(count),size:10,weight:700,fill:red,font:"chart",lh:1.4);v(4*t.u)}else{v(4*t.u)}
            #let height=calc.max(2,calc.min(192,count/highest*210))
            #context {
              let width=(680 - 46)/24*.7
              shadow(t,rect(width:width*t.u,height:height*t.u,fill:gradient.linear(red,gold,angle:270deg,space:rgb),radius:(top-left:4*t.u,top-right:4*t.u,bottom-left:0pt,bottom-right:0pt),stroke:1*t.u+gold.transparentize(60%),outset:-.5*t.u),radius:4,blur:12,dy:0,color:red.transparentize(70%))
            }
          ]]
          #v(10.5*t.u)#rotate(-45deg,reflow:false,copy(t,(if hour < 10 {"0"}else{""})+str(hour)+":00",size:10,weight:700,lh:1.4))
        ])))
      ]
    ]
  ]
}
#let seal(t,label,title:false) = context {
  let body=copy(t,label,size:12,weight:700,font:"heading",fill:if title {white}else{red.transparentize(20%)},lh:1.2)
  let width=measure(body).width+22*t.u
  let height=20.4
  box(width:width,height:height*t.u)[
    #if title {place(top+left,dx:3*t.u,dy:3*t.u,rect(width:width,height:height*t.u,fill:gold.transparentize(60%),stroke:none))}
    #box(width:width,height:height*t.u,inset:(x:11*t.u,y:3*t.u),fill:if title {red}else{white},stroke:1*t.u+(if title {red}else{red.transparentize(20%)}),outset:-.5*t.u)[
      #body
      #place(top+left,dx:-8*t.u,dy:0pt,rect(width:width - 6*t.u,height:(height - 6)*t.u,fill:none,stroke:1*t.u+(if title {white.transparentize(80%)}else{red.transparentize(84%)})))
    ]
  ]
}
#let portraits(t,d) = {
  if d.portraits.len()==0 {return}
  heading(t,"🎖️","群友风云榜")
  v(23*t.u)
  layout(size=>{
    let width=(size.width - 25*t.u)/2
    let bodies=d.portraits.map(p=>[
      #grid(columns:(65*t.u,1fr),gutter:18*t.u,align:horizon,
        box(width:65*t.u,height:65*t.u)[#shadow(t,box(width:65*t.u,height:65*t.u,fill:red,stroke:2*t.u+gold,outset:-1*t.u,inset:5*t.u)[
          #box(width:100%,height:100%,radius:50%,clip:true)[#if p.avatar!="" {image(p.avatar,width:100%,height:100%,fit:"cover")}else{align(center+horizon,copy(t,"福",size:35.2,font:"calligraphy",fill:white))}]
        ],radius:0,blur:12,dy:4,color:black.transparentize(85%))],[
          #copy(t,p.name,size:20.8,font:"heading",weight:700,fill:red,lh:20/20.8)#v(5*t.u)
          #seal(t,p.profile)#h(16*t.u,weak:true)#seal(t,p.title,title:true)#v(16*t.u)
        ])
      #v(15*t.u)#rect(width:100%,height:1*t.u,fill:red.transparentize(90%),stroke:none)#v(15*t.u)
      #set par(justify:true)
      #copy(t,runs(t,p.reason),size:16.8,lh:1.6)
    ])
    for start in range(0,bodies.len(),step:2) {
      let row=bodies.slice(start,calc.min(start+2,bodies.len()))
      let height=calc.max(..row.map(body=>measure(body,width:width - 58*t.u).height/t.u+52))
      grid(columns:(width,width),gutter:25*t.u,..row.enumerate().map(((i,body))=>frame(t,stroke:1,left-width:4,right-width:4,blur:20,dx:6,dy:6,height:height,watermark:d.portraits.at(start+i),dots:(step:15,color:red.transparentize(98%)),stamp:(text:"春",font:"calligraphy",size:48,angle:0deg,bottom:true,x:-5,y:-5,fill:red.transparentize(95%)),body)))
      if start+2 < bodies.len() {v(25*t.u)}
    }
  })
}
#let quotes(t,d) = {
  if d.quotes.len()==0 {return}
  heading(t,"✨","每日金句回响")
  // 原 HTML 内外两个时间线容器使 BOM 额外占用一行及 40px 间隔。
  v(63*t.u)
  for (i,q) in d.quotes.enumerate() {
    let flipped=calc.odd(i)
    let avatar=box(width:70*t.u,height:70*t.u)[
      #shadow(t,box(width:70*t.u,height:70*t.u,inset:3*t.u,radius:50%,fill:white,stroke:3*t.u+gold,outset:-1.5*t.u)[
        #box(width:100%,height:100%,radius:50%,clip:true)[#if q.avatar!="" {image(q.avatar,width:100%,height:100%,fit:"cover")}else{align(center+horizon,copy(t,"福",size:32,font:"calligraphy",fill:red))}]
      ],radius:35,blur:15,dy:5,color:black.transparentize(90%))
    ]
    let bubble=frame(t,padx:25,pady:25,radius:if flipped {(top-left:25,top-right:4,bottom-left:25,bottom-right:25)}else{(top-left:4,top-right:25,bottom-left:25,bottom-right:25)},hard:true,dx:6,dy:6,fill:if flipped {rgb("fffaf0")}else{white},dots:(step:20,color:red.transparentize(95%)),[
      #align(if flipped {right}else{left})[
        #copy(t,[“#runs(t,q.content)”],size:24,font:"heading",lh:1.5)#v(12*t.u)
        #copy(t,[—— #q.sender],size:28.8,font:"calligraphy",fill:red,lh:28/28.8)#v(10*t.u)
      ]
      #rect(width:100%,height:1*t.u,fill:rgb("eeeeee"),stroke:none)#v(10*t.u)
      #align(left,copy(t,[【评语】#runs(t,q.reason)],size:14.4,fill:rgb("888888"),lh:21/14.4))
    ])
    align(if flipped {right}else{left},block(width:85%)[#grid(columns:if flipped {(1fr,70*t.u)}else{(70*t.u,1fr)},gutter:20*t.u,if flipped {bubble}else{avatar},if flipped {avatar}else{bubble})])
    if i < d.quotes.len()-1 {v(40*t.u)}
  }
}
#let render(d) = {
  let u=72/d.ppi*d.width/940*1pt
  let body=if d.font_language=="zh-Hant" {("Noto Serif TC","Noto Serif SC")}else{("Noto Serif SC","Noto Serif TC")}
  let t=(u:u,body:(..body,"Noto Color Emoji"))
  set page(width:940*u,height:auto,margin:0pt,fill:red)
  set text(font:t.body,size:16*u,fill:wood,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none)
  set par(leading:0pt,spacing:0pt)
  set smartquote(enabled:false)
  set page(background:layout(size=>{
    let h=size.height/u
    let texture="<svg xmlns='http://www.w3.org/2000/svg' width='940' height='"+str(h)+"'><defs><pattern id='d' width='40' height='40' patternUnits='userSpaceOnUse'><circle cx='20' cy='20' r='1' fill='#d32f2f'/></pattern><pattern id='s' width='70.710678' height='100' patternUnits='userSpaceOnUse' patternTransform='rotate(-45)'><rect width='35.355339' height='100' fill='#ffca28' fill-opacity='.05'/></pattern></defs><rect width='100%' height='100%' fill='url(#s)'/><rect width='100%' height='100%' fill='url(#d)'/></svg>"
    box(width:size.width,height:size.height)[
      #place(top+left,image(bytes(texture),format:"svg",width:size.width,height:size.height))
      #place(top+left,dx:20*u,dy:40*u,shadow(t,block(width:900*u,height:size.height - 80*u,fill:paper,stroke:15*u+red,outset:-7.5*u,radius:4*u),radius:4,blur:60,dy:30,color:black.transparentize(50%)))
      #place(top+left,dx:28.5*u,dy:48.5*u,rect(width:883*u,height:size.height - 97*u,fill:none,stroke:3*u+gold))
      #let corners="<svg xmlns='http://www.w3.org/2000/svg' width='890' height='"+str(h - 90)+"'><g fill='none' stroke='#ffca28' stroke-width='5'><path d='M2.5 80V15Q2.5 2.5 15 2.5H80'/><path transform='translate(890 0) scale(-1 1)' d='M2.5 80V15Q2.5 2.5 15 2.5H80'/><path transform='translate(0 "+str(h - 90)+") scale(1 -1)' d='M2.5 80V15Q2.5 2.5 15 2.5H80'/><path transform='translate(890 "+str(h - 90)+") scale(-1 -1)' d='M2.5 80V15Q2.5 2.5 15 2.5H80'/></g></svg>"
      #place(top+left,dx:25*u,dy:45*u,image(bytes(corners),format:"svg",width:890*u,height:(h - 90)*u))
    ]
  }))
  block(width:940*u,inset:(x:95*u,y:115*u))[
    #header(t,d)#statistics(t,d)
    #if d.review!=none {quality(t,d);v(90*u)}
    #if d.topics.len()>0 {topics(t,d);v(90*u)}
    #activity(t,d)
    #if d.portraits.len()>0 {v(90*u);portraits(t,d)}
    #if d.quotes.len()>0 {v(90*u);quotes(t,d)}
    #v(100*u)#rect(width:100%,height:2*u,fill:gold,stroke:none)#v(30*u)
    #align(center)[
      #copy(t,"宜 · 总结分析 // "+d.generated_at,font:"heading",fill:red,lh:1)#v(8*u)
      #copy(t,[Token 消耗：#d.tokens.at(0) (Prompt: #d.tokens.at(1), Completion: #d.tokens.at(2))],size:13.6,font:"heading",fill:red.transparentize(30%),lh:14/13.6)
      // 内联标签保留浏览器的基线留白，标签自身仍为原版 16px 行高。
      #v(17*u)
      #rotate(-2deg,reflow:false,box(inset:(x:20*u,y:5*u),fill:gold)[#copy(t,"SXP-Simon / astrbot_plugin_qq_group_daily_analysis",font:"heading",fill:red,lh:1)])
    ]
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

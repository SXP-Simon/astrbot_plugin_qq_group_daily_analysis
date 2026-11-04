// Miku 长图的独立布局：逐项保留原版的尺寸、层级、图标、底纹和气泡关系。
#import "common.typ": words, shadow
#let base = rgb("39c5bb")
#let dark = rgb("2a9d95")
#let light = rgb("a7e7e3")
#let pink = rgb("f8bbd0")
#let ink = rgb("2c3e50")
#let muted = rgb("7f8c8d")
#let soft = rgb("f0fafa")
#let border = rgb("39c5bb").transparentize(85%)
#let icon(t,name,size:24,color:dark) = box(width:size*t.u,height:size*t.u,baseline:25%)[#image(bytes(read("icon-"+name+".svg").replace("#2a9d95",color.to-hex()).replace("var(--miku-dark)",color.to-hex())),format:"svg",width:100%,height:100%)]
// 显式行框使多行正文的高度与 CSS line-height 一致，不依赖默认段间距。
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.45,font:none) = {
  set par(leading:0pt,spacing:0pt)
  let edge=(lh - 1)/2
  let family=if font==none {t.fonts.first()}else if type(font)==array {font.first()}else{font}
  let baseline=if family=="Outfit" {0.87}else if family=="Share Tech Mono" {0.8215}else if family=="Inter" {0.86377}else if family=="cjkFonts" {880/1024}else{0.936}
  // 全瀨體只有常规字重，描边补齐浏览器对标题粗体的合成效果。
  text(size:size*t.u,weight:weight,fill:fill,stroke:if family=="cjkFonts" and weight>=600 {0.035em+fill}else{none},top-edge:(baseline+edge)*1em,bottom-edge:-(1-baseline+edge)*1em,font:if font==none {t.fonts}else if type(font)==array {font}else{(font,..t.fonts)})[#body]
}
// 标题、统计标签和峰值标签沿用原版的半像素缩字号规则及下限。
#let fitted(t,body,width,size:24,minimum:0.78,..style) = context {
  let current=size
  while current>size*minimum and measure(copy(t,body,size:current,..style.named())).width>width*t.u {current -= 0.5}
  if measure(copy(t,body,size:current,..style.named())).width>width*t.u {current=size}
  copy(t,body,size:current,..style.named())
}
#let runs(t,parts) = {
  for part in parts {
    if part.avatar!="" {
      h(2*t.u)
      box(inset:(left:3*t.u,right:7*t.u,y:3*t.u),radius:12*t.u,fill:black.transparentize(95%),stroke:1*t.u+black.transparentize(90%),baseline:(at:bottom,shift:7*t.u))[
        #set text(top-edge:0.85em,bottom-edge:-0.15em)
        #box(width:18*t.u,height:18*t.u,radius:50%,clip:true,baseline:25%)[#image(part.avatar,width:100%,height:100%,fit:"cover")]
        #if part.text!="" {h(4*t.u);text(size:0.85em,weight:500,top-edge:0.85em,bottom-edge:-0.15em,part.text)}
      ]
      h(2*t.u)
    } else {
      for (i,line) in part.text.split("\n").enumerate(){
        if i>0 {linebreak()}
        let kana=regex("[ぁ-ゟ゠-ヿㇰ-ㇿｦ-ﾟ]+")
        if line.contains(kana) and not line.contains(regex("[的了吗呢吧这那们你我没啥呗哦啊]")) {
          text(font:"Noto Sans JP",lang:"ja",line)
        }else{
          show kana: text.with(font:"Noto Sans JP",lang:"ja")
          line
        }
      }
    }
  }
}
#let frame(t,body,inset:30,fill:white,radius:12,stroke:border,height:auto) = shadow(t,block(width:100%,height:height,fill:fill,radius:radius*t.u,inset:inset*t.u,outset:-0.5*t.u,stroke:1*t.u+stroke,breakable:false)[#body])
#let face(t,path,size:48,portrait:false,name:"") = {
  let picture=box(width:size*t.u,height:size*t.u,radius:50%,clip:true,fill:white,stroke:if portrait {none}else{4*t.u+light},inset:3*t.u)[
    #box(width:100%,height:100%,radius:50%,clip:true,fill:if portrait {rgb("e0f2f1")}else{soft})[
      #if path!="" {image(path,width:100%,height:100%,fit:"cover")}else if portrait {align(center+horizon,text(fill:white,weight:700,if name=="" {"?"}else{name.first()}))}
    ]
  ]
  if portrait {shadow(t,picture,radius:size/2,blur:10,dy:4,color:base.transparentize(80%))}else{picture}
}
#let art(t,d,index,height) = context {
  let path=d.decorations.at(index,default:"")
  if path!="" {
    let picture=image(path,height:height*t.u)
    if measure(picture).width>150*t.u {image(path,width:150*t.u)}else{picture}
  }
}
#let capsule(t,body,fill:rgb("e0f2f1"),size:13.6) = box(fill:fill,radius:20*t.u,inset:(x:16*t.u,y:8*t.u),stroke:0.7*t.u+border)[#copy(t,body,size:size,fill:dark,lh:1.4)]
#let section(t,title,name,pink-bar:false,gap:30) = {
  block(width:100%,height:48*t.u,stroke:(bottom:1*t.u+base.transparentize(90%)),inset:(bottom:12*t.u))[
    #grid(columns:(5*t.u,24*t.u,1fr),column-gutter:(15*t.u,10*t.u),align:horizon,
      rect(width:5*t.u,height:24*t.u,radius:2.5*t.u,fill:if pink-bar {pink}else{base},stroke:none),
      icon(t,name),fitted(t,text(tracking:if t.english {-0.011em}else{1*t.u},title),764,size:24,weight:800,lh:1.45))
  ]
  v(gap*t.u)
}
#let heading(t,d) = context {
  let date=copy(t,[#words(d).log #text("//") #d.date],size:17.6,weight:700,fill:dark,font:"Outfit",lh:26/17.6)
  grid(columns:(1fr,auto),align:bottom,gutter:15*t.u,
    [#let title=fitted(t,text(tracking:if t.english {-0.018em}else{0pt},words(d).title),818 - measure(date).width/t.u - 15,size:44.8,minimum:0.68,weight:800,font:t.title-font,lh:if t.english {1.26}else if t.allseto {1}else{65/44.8})
      #box(width:measure(title).width)[#place(bottom,rect(width:100%,height:8*t.u,radius:4*t.u,fill:gradient.linear(dark.transparentize(40%),base.transparentize(40%),angle:0deg),stroke:none))#title]],
    date)
  v(40*t.u)
}
#let stats(t,d) = {
  let w=words(d)
  let items=((w.messages,d.message_count,"message-square"),(w.members,d.participant_count,"users"),(w.emoji,d.emoji_count,"smile"),(w.characters,d.characters,"type"))
  grid(columns:(1fr,)*4,gutter:15*t.u,..items.map(item=>frame(t,height:107*t.u,inset:19,[
    #align(center)[#grid(columns:(auto,auto),gutter:6*t.u,align:horizon,icon(t,item.at(2),size:18,color:base),fitted(t,text(tracking:if t.english {0.045em}else{0pt},if t.english {upper(item.at(0))}else{item.at(0)}),131.25,size:13.6,weight:700,fill:muted))#v(5*t.u)#copy(t,str(item.at(1)),size:35.2,weight:800,font:"Outfit",lh:1.25)]
  ])))
  v(30*t.u)
}
#let peak(t,d) = {
  shadow(t,dy:6,blur:15,color:base.transparentize(85%),block(width:100%,height:120*t.u,fill:gradient.linear(base,light,angle:45deg),radius:12*t.u,inset:(x:35*t.u),clip:true)[
    #place(right+horizon,dx:20*t.u,dy:-6*t.u,skew(ax:-12deg,copy(t,text(tracking:-3*t.u)[MIKU],size:160,weight:900,fill:white.transparentize(80%),font:"Share Tech Mono",lh:0.73)))
    #grid(columns:(1fr,150*t.u),rows:120*t.u,align:horizon,
      [#grid(columns:(auto,1fr),gutter:8*t.u,align:horizon,icon(t,"trending-up",size:20,color:white),fitted(t,text(tracking:if t.english {0.045em}else{0pt},if t.english {upper(words(d).peak)}else{words(d).peak}),570,size:16,weight:700,fill:white))#v(4*t.u)#copy(t,text(tracking:1*t.u,d.peak),size:44.8,weight:800,fill:white,font:"Outfit",lh:1.27)],
      box(width:150*t.u,height:120*t.u,clip:true)[#if d.decorations.at(0,default:"")!="" {image(d.decorations.first(),width:100%,height:100%,fit:"cover")}])
  ])
  v(30*t.u)
}
#let activity(t,d) = {
  section(t,words(d).activity,"line-chart")
  frame(t,height:262*t.u,inset:0,[
    #block(inset:(x:11*t.u,top:45*t.u,bottom:20*t.u))[
      #place(top,dy:158*t.u,line(length:100%,stroke:2*t.u+base.transparentize(90%)))
      #let highest=calc.max(1,..d.hours)
      #let colors=("66d1c7","6fd3c6","79d5c4","85d8c3","93dac1","a3ddbf","b4e0bd","c7e2ba","dbe5b8","efe8b5","ffeab3","ffdf9e","ffd38b","ffc67a","ffb96d","ffac62","ffa059","ff9552","ff8b4d","ff834b","ff7d4d","ff7752","ff745a","ff7365")
      #grid(columns:(1fr,)*24,column-gutter:4*t.u,align:bottom,..d.hours.enumerate().map(((hour,n))=>[
        #align(center)[
          #box(width:100%,height:160*t.u)[#align(bottom)[
            #if n>0 {copy(t,str(n),size:12,weight:800,fill:rgb(colors.at(hour)),font:"Outfit",lh:1.25);v(4*t.u)}
            #let raw=if n==0 {153*0.04}else{153*n/highest}
            #let bar-height=if n>0 and raw+19>153 {153*raw/(raw+19)}else{raw}
            #rect(width:100%,height:bar-height*t.u,radius:(top:4*t.u,bottom:1*t.u),fill:if n==0 {rgb("e0f2f1").transparentize(70%)} else {rgb(colors.at(hour))},stroke:none)
            #v(7*t.u)
          ]]
          #v(12*t.u)
          #copy(t,[#((if hour < 10 {"0"}else{""})+str(hour))#if calc.rem(hour,4)==0 or hour==23 {text(font:t.fonts)[#("zh-Hans":"时","zh-Hant":"時","en":"h","ja":"時").at(d.language)]}],size:11.2,weight:700,fill:muted,font:"Outfit",lh:24/11.2)
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
    shadow(t,block(width:100%,fill:white,radius:12*t.u,stroke:(left:6*t.u+base,rest:1*t.u+border),outset:(left:-3*t.u,rest:-0.5*t.u),inset:(left:30*t.u,right:25*t.u,top:25*t.u,bottom:25*t.u),breakable:false)[
      #grid(columns:(auto,1fr),gutter:20*t.u,
        pad(top:2*t.u,copy(t,"#"+(if i < 9 {"0"}else{""})+str(i+1),size:28.8,weight:800,fill:pink.transparentize(20%),font:"Outfit",lh:1.25)),
        [#copy(t,topic.title,size:20,weight:800,lh:1.4)#v(10*t.u)
          #block(inset:12*t.u)[#copy(t,runs(t,topic.detail),lh:1.8)]
          #v(18*t.u)
          #grid(columns:(1fr,auto),rows:65*t.u,gutter:12*t.u,align:horizon,
            [#capsule(t,[#icon(t,"handheld-mic",size:16)#h(8*t.u)#text(fill:muted)[#words(d).participants:]#h(8*t.u)#text(weight:700)[#runs(t,topic.contributors)]])],
            art(t,d,1+calc.rem(i,calc.max(1,d.decorations.len()-1)),65))
        ])
    ])
    if i < d.topics.len()-1 {v(25*t.u)}
  }
  v(50*t.u)
}
#let portraits(t,d) = context {
  if d.portraits.len()==0 {return}
  section(t,words(d).portraits,"users",gap:54)
  let cards=d.portraits.map(p=>{
    let head=grid(columns:(60*t.u,1fr),gutter:15*t.u,align:horizon,face(t,p.avatar,size:60,portrait:true,name:p.name),[
      #let name=p.name
      #let letters=name.clusters()
      #while letters.len()>0 and measure(copy(t,name,size:18.4,weight:800)).width>274*t.u {
        let _=letters.pop()
        name=letters.join()+"…"
      }
      #copy(t,name,size:18.4,weight:800,lh:26/18.4)#v(6*t.u)
      #box(fill:rgb("e0f2f1"),radius:6*t.u,inset:(x:8*t.u,y:2*t.u),stroke:0.7*t.u+border)[#copy(t,p.title,size:11.2,weight:800,fill:dark)]#h(6*t.u)
      #box(fill:pink,radius:6*t.u,inset:(x:8*t.u,y:2*t.u))[#copy(t,p.profile,size:11.2,weight:800,fill:white,font:"Outfit")]
    ])
    let reason=copy(t,runs(t,p.reason),size:15.2,fill:muted,lh:1.6)
    let head-height=measure(head,width:349*t.u).height
    let height=head-height+measure(reason,width:317*t.u).height+100*t.u
    (portrait:p,head:head,reason:reason,head-height:head-height,height:height)
  })
  // CSS Grid 将同一行的画像及说明底色拉齐；正文长短不会留下参差的卡片底边。
  for (row,items) in cards.chunks(2).enumerate(){
    let height=calc.max(..items.map(x=>x.height))
    grid(columns:(1fr,1fr),gutter:20*t.u,..items.map(x=>shadow(t,block(width:100%,height:height,fill:white,radius:12*t.u,stroke:(top:4*t.u+light,rest:1*t.u+border),outset:(top:-2*t.u,rest:-0.5*t.u),inset:(x:25*t.u,top:28*t.u,bottom:25*t.u),breakable:false,clip:true)[
      #x.head
      #v(15*t.u)
      #block(width:100%,height:height - x.head-height - 68*t.u,fill:soft,inset:16*t.u,radius:12*t.u,stroke:(paint:border,thickness:1*t.u,dash:"dashed"),outset:-0.5*t.u)[
        #place(bottom+right,dx:7*t.u,dy:7*t.u,icon(t,"closing-quote",size:16,color:base.transparentize(80%)))
        #x.reason
      ]
      #if x.portrait.image!="" {
        let natural=measure(image(x.portrait.image,width:151.62*t.u))
        place(bottom+right,dx:17*t.u,dy:17*t.u,image(x.portrait.image,width:151.62*t.u,height:calc.min(natural.height,height*0.78),fit:x.portrait.at("image_fit",default:"contain")))
      }
    ])))
    if row < calc.ceil(cards.len()/2) - 1 {v(20*t.u)}
  }
  v(50*t.u)
}
#let quotes(t,d) = context {
  if d.quotes.len()==0 {return}
  section(t,words(d).quotes,"quote",pink-bar:true,gap:54)
  let review-label=("zh-Hans":"Miku 锐评","zh-Hant":"Miku 銳評","en":"Miku's Take","ja":"ミクの辛口コメント").at(d.language)
  for (i,q) in d.quotes.enumerate() {
    let reverse=calc.odd(i)
    let bubble-width=measure(copy(t,runs(t,q.content),size:16.8,weight:600,lh:1.6)).width/t.u+46
    let reason-width=calc.max(measure(copy(t,runs(t,q.reason),size:14.4,fill:muted,lh:1.6)).width/t.u,measure(copy(t,review-label,size:15.2,weight:700)).width/t.u+26)+40
    let content-width=calc.min(818*0.85-63,calc.max(bubble-width,reason-width))
    align(if reverse {right}else{left})[
      #block(width:(content-width+63)*t.u)[
        #grid(columns:if reverse {(content-width*t.u,48*t.u)}else{(48*t.u,content-width*t.u)},gutter:15*t.u,
          ..(if reverse {(true,false)}else{(false,true)}).map(content=>if not content {face(t,q.avatar)} else {[
            #align(if reverse {right}else{left})[#copy(t,q.sender,size:13.6,weight:700,fill:muted)#v(6*t.u)]
            #shadow(t,dy:4,blur:10,color:base.transparentize(95%),block(width:100%,fill:white,inset:(x:23*t.u,y:17*t.u),stroke:1*t.u+border,outset:-0.5*t.u,radius:if reverse {(top-left:18*t.u,top-right:4*t.u,bottom:18*t.u)}else{(top-left:4*t.u,top-right:18*t.u,bottom:18*t.u)})[#copy(t,runs(t,q.content),size:16.8,weight:600,lh:1.6)])
            #v(12*t.u)
            #block(width:calc.min(reason-width,content-width)*t.u,fill:soft,inset:(left:22*t.u,right:18*t.u,y:12*t.u),radius:12*t.u,stroke:(left:4*t.u+pink))[
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
  frame(t,inset:31,[
    #block(width:100%,inset:(bottom:17*t.u),stroke:(bottom:(paint:rgb("e0f2f1"),thickness:2*t.u,dash:"dashed")))[#grid(columns:(1fr,auto),align:bottom,copy(t,r.title,size:25.6,fill:dark),box(fill:rgb("e0f2f1"),radius:20*t.u,inset:(x:12*t.u,y:4*t.u))[#copy(t,r.subtitle,size:14.4,fill:muted,font:"Outfit",lh:19/14.4)])]
    #v(25*t.u)
    #block(width:100%,radius:7*t.u,clip:true)[#grid(columns:r.dimensions.map(x=>calc.max(0.1,x.percentage)*1fr),..r.dimensions.enumerate().map(((i,x))=>rect(width:100%,height:14*t.u,fill:colors.at(calc.rem(i,5)),stroke:none)))]
    #v(30*t.u)
    #grid(columns:(1fr,1fr),gutter:15*t.u,..r.dimensions.enumerate().map(((i,x))=>block(width:100%,fill:soft,inset:(x:15*t.u,y:12*t.u),radius:10*t.u)[
      #grid(columns:(10*t.u,1fr),gutter:10*t.u,pad(top:5*t.u,circle(radius:5*t.u,fill:colors.at(calc.rem(i,5)),stroke:none)),[
        #let percentage=calc.round(x.percentage,digits:1)
        #copy(t,[#x.name (#(str(percentage)+(if calc.fract(percentage)==0 {".0"}else{""}))%)],size:14.4,weight:700)#v(4*t.u)#copy(t,runs(t,x.comment),size:13.6,fill:muted,lh:1.5)
      ])
    ]))
    #v(30*t.u)
    #shadow(t,dy:4,blur:15,color:base.transparentize(80%),block(width:100%,fill:gradient.linear(dark,base,angle:45deg),inset:25*t.u,radius:12*t.u)[
      #grid(columns:(1fr,auto),gutter:20*t.u,align:bottom,
        [#grid(columns:(20*t.u,1fr),gutter:8*t.u,align:horizon,icon(t,"mic",size:20,color:white),copy(t,words(d).verdict,size:17.6,weight:700,fill:white))#v(12*t.u)#copy(t,runs(t,r.summary),fill:white.transparentize(5%),lh:1.8)],
        art(t,d,1,100))
    ])
  ])
  v(50*t.u)
}
#let footer(t,d) = {
  frame(t,height:114*t.u,inset:0,fill:rgb("ebf7f6"),stroke:base.transparentize(70%),[
    #block(inset:(x:31*t.u,y:21*t.u))[
      #grid(columns:(1fr,auto),gutter:15*t.u,align:horizon,
        copy(t,[#icon(t,"github",size:18)#h(10*t.u)SXP-Simon/astrbot_plugin_qq_group_daily_analysis],size:15.2,weight:700,fill:dark,font:"Outfit",lh:19/15.2),
        copy(t,[#icon(t,"cpu",size:14,color:muted)#h(6*t.u)Token usage: #text(weight:800)[#d.tokens.at(0)]#h(10*t.u)#text(fill:muted,size:12.8*t.u)[( P: #d.tokens.at(1) | C: #d.tokens.at(2) )]],size:14.4,font:"Outfit",lh:18/14.4))
      #v(15*t.u)#line(length:100%,stroke:(paint:base.transparentize(70%),thickness:1*t.u,dash:"dashed"))#v(15*t.u)
      #grid(columns:(1fr,auto),gutter:15*t.u,align:horizon,
        copy(t,[#icon(t,"clock",size:14,color:muted)#h(6*t.u)Generated at #d.generated_at],size:14.4,fill:muted,font:"Outfit",lh:18/14.4),
        grid(columns:(14*t.u,auto),gutter:6*t.u,align:horizon,icon(t,"heart",size:14,color:rgb("ff85a2")),skew(ax:-12deg,origin:bottom,copy(t,"Template by shiitin",size:15.2,weight:700,fill:dark))))
    ]
  ])
}
#let render(d,t) = {
  let font=if d.at("font_language",default:d.language)=="zh-Hant" {"Noto Sans TC"} else if d.language=="ja" {"Noto Sans JP"}else{"Noto Sans SC"}
  t.insert("english",d.language=="en")
  t.insert("fonts",if t.english {("Inter","Outfit",font,"Noto Sans JP")}else{(font,"Noto Sans SC","Noto Sans JP")})
  t.insert("allseto",d.language in ("zh-Hans","zh-Hant") and d.at("miku_allseto",default:false))
  // Typst 将官方 1.11 字库登记为 cjkFonts；AllSeto 是 HTML 的字体别名。
  t.insert("title-font",if t.english {("Outfit","Inter",font)}else if t.allseto {("cjkFonts",font,"Noto Sans SC")}else{(font,"Noto Sans SC")})
  set page(width:940*t.u,height:auto,margin:0pt,fill:soft)
  set text(font:t.fonts,size:16*t.u,fill:ink,cjk-latin-spacing:none,overhang:false,lang:if d.language=="ja" {"ja"}else if d.language=="en" {"en"}else{"zh"},region:if d.language=="ja" {"JP"}else if d.font_language=="zh-Hant" {"TW"}else{"CN"})
  set par(spacing:0pt,leading:0pt)
  let paper=tiling(size:(24*t.u,24*t.u))[
    #rect(width:24*t.u,height:24*t.u,fill:white,stroke:none)
    #place(top+left,dx:12.5*t.u,dy:12.5*t.u,circle(radius:1.5*t.u,fill:base.transparentize(92%),stroke:none))
  ]
  let content=block(width:940*t.u,inset:(x:20*t.u,y:40*t.u))[
    #shadow(t,dy:15,blur:40,color:dark.transparentize(90%),block(width:100%,inset:41*t.u,fill:paper,radius:12*t.u,stroke:1*t.u+border,outset:-0.5*t.u,clip:true)[
      #place(top+right,dx:60*t.u,skew(ax:-12deg,copy(t,"01",size:256,weight:900,fill:base.transparentize(96%),font:"Outfit",lh:1)))
      #place(bottom+left,dx:-80*t.u,dy:-159*t.u,skew(ax:-12deg,copy(t,"39",size:352,weight:900,fill:base.transparentize(97%),font:"Outfit",lh:1)))
      #place(top+left,dx:-10*t.u,dy:140*t.u,copy(t,text(tracking:2*t.u)[[ SYSTEM_VOCALOID_INITIALIZED ]#linebreak()HATSUNE MIKU v4X],fill:dark.transparentize(90%),font:"Outfit",lh:1.25))
      #heading(t,d)#stats(t,d)#peak(t,d)#activity(t,d)#topics(t,d)#portraits(t,d)#quotes(t,d)#quality(t,d)#footer(t,d)
    ])
  ]
  content
  // 用末尾标记取得实际高度，避免为像素预算再次测量整页。
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

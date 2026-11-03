// 独立保留复古工业版面、CRT 扫描线与原始图表配色。
#let ink=rgb("1a1a1a")
#let paper=rgb("f8f4e8")
#let orange=rgb("d35400")
#let navy=rgb("2e4053")
#let rust=rgb("a93226")
#let gold=rgb("d4ac0d")
#let grid-color=ink.transparentize(95%)
#let palette=(orange,navy,gold,rust,rgb("ffba08"),rgb("273c75"),rgb("e07a5f"),rgb("8d99ae"))
#let copy(t,body,size:18,weight:400,fill:ink,font:none,lh:none,tracking:none,italic:false) = {
  if type(body)==str and body=="" {return}
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="display" {("Oswald",..t.body)}else if font=="mono" {("JetBrains Mono",..t.mono)}else{t.body}
  let baseline=if font=="display" {.452}else if font=="mono" {.36}else{.436}
  let height=if lh!=none {lh}else if font=="display" {(calc.round(size*1.193)+calc.round(size*.289))/size}else if font=="mono" {(if size==14.4 {19}else{calc.ceil(size*1.32)})/size}else{(calc.round(size*1.16)+calc.round(size*.288))/size}
  let result=text(font:fonts,size:size*t.u,weight:weight,fill:fill,tracking:(if tracking==none {-.18}else{tracking})*t.u,style:if italic {"italic"}else{"normal"},top-edge:(height/2+baseline)*1em,bottom-edge:-(height/2-baseline)*1em,body)
  if italic {
    show regex("[（「【]?[\\p{Han}\\p{Hiragana}\\p{Katakana}\\p{Hangul}][，。！？…、）」】]*"):it=>box(height:height*size*t.u,baseline:(at:top,shift:-(height/2+baseline)*size*t.u))[#skew(ax:-12deg,origin:bottom+left,it)]
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
#let frame(t,body,padx:40,pady:40,stroke:3,left-width:none,left-color:ink,top-width:none,top-color:ink,fill:white,shade:ink,dx:12,dy:12,height:none,centered:false,watermark:none,clip:false) = layout(size=>{
  let lw=if left-width==none {stroke}else{left-width}
  let tw=if top-width==none {stroke}else{top-width}
  let inside=block(width:size.width,inset:(left:(padx+lw)*t.u,right:(padx+stroke)*t.u,top:(pady+tw)*t.u,bottom:(pady+stroke)*t.u))[#body]
  let h=measure(inside).height
  if height!=none {h=calc.max(h,height*t.u)}
  place(top+left,dx:dx*t.u,dy:dy*t.u,rect(width:size.width,height:h,fill:shade,stroke:none))
  block(width:size.width,height:h,fill:fill,stroke:(rest:stroke*t.u+ink,left:lw*t.u+left-color,top:tw*t.u+top-color),outset:(rest:-stroke/2*t.u,left:-lw/2*t.u,top:-tw/2*t.u),clip:clip)[
    #if centered {align(horizon,inside)}else{inside}
    #if watermark!=none and watermark.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(watermark.image,width:size.width*.35,height:calc.min(measure(image(watermark.image,width:size.width*.35)).height,h*.8),fit:watermark.image_fit))}
  ]
})
// SVG 直接引用任务内头像并套用 CSS 对应的色彩矩阵，不复制灰度图片文件。
#let avatar(t,path,size:120,round:false,contrast:1.1) = box(width:size*t.u,height:size*t.u,fill:if round {none}else{rgb("eeeeee")},radius:if round {50%}else{0pt},clip:true)[
  #if path!="" {
    let slope=str(contrast)
    let intercept=str(.5 - contrast*.5).replace("−","-")
    let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(size)+"' height='"+str(size)+"'><defs><filter id='g' color-interpolation-filters='sRGB'><feColorMatrix type='matrix' values='.2126 .7152 .0722 0 0 .2126 .7152 .0722 0 0 .2126 .7152 .0722 0 0 0 0 0 1 0'/><feComponentTransfer><feFuncR type='linear' slope='"+slope+"' intercept='"+intercept+"'/><feFuncG type='linear' slope='"+slope+"' intercept='"+intercept+"'/><feFuncB type='linear' slope='"+slope+"' intercept='"+intercept+"'/></feComponentTransfer></filter></defs><image href='"+path+"' width='100%' height='100%' preserveAspectRatio='xMidYMid slice' filter='url(#g)'/></svg>"
    image(bytes(svg),format:"svg",width:size*t.u,height:size*t.u)
  }else{align(center+horizon,copy(t,"DATA_ERR",size:12,font:"mono",fill:ink.transparentize(70%)))}
]
// 发光文字使用编译器已加载的字体；SVG 只生成阴影，正文仍由原生文字排版。
#let glow(t,value,size:96,font:"display",weight:400,fill:white,shade:white.transparentize(50%),blur:7.5,dx:0,dy:0,tracking:-3,lh:143/96) = {
  if value=="" {return}
  layout(size-available=>context {
  let body=copy(t,value,size:size,font:font,weight:weight,fill:fill,tracking:tracking,lh:lh)
  let m=measure(body,width:size-available.width)
  let natural=measure(body)
  box(width:m.width,height:m.height)[
    #if natural.width<=size-available.width {
      let pad=2*blur+calc.max(calc.abs(dx),calc.abs(dy))
      let w=m.width/t.u
      let h=m.height/t.u
      let baseline=if font=="display" {.452}else{.36}
      let safe=value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;").replace("'","&apos;")
      let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"'><defs><filter id='s' filterUnits='userSpaceOnUse' x='0' y='0' width='"+str(w+2*pad)+"' height='"+str(h+2*pad)+"'><feGaussianBlur stdDeviation='"+str(blur)+"'/></filter></defs><text x='"+str(pad+dx)+"' y='"+str(pad+dy+(lh/2+baseline)*size)+"' font-family='"+(if font=="display" {"Oswald"}else{"JetBrains Mono"})+"' font-size='"+str(size)+"' font-weight='"+str(weight)+"' letter-spacing='"+str(tracking).replace("−","-")+"' fill='"+shade.to-hex()+"' filter='url(#s)'>"+safe+"</text></svg>"
      place(top+left,dx:-pad*t.u,dy:-pad*t.u,image(bytes(svg),format:"svg",width:(w+2*pad)*t.u,height:(h+2*pad)*t.u))
    }
    #body
  ]
})
}
#let heading(t,title,code) = {
  grid(columns:(1fr,auto),align:horizon,gutter:20*t.u,copy(t,title,size:56,font:"display"),box(inset:(x:20*t.u,y:8*t.u),fill:ink)[#copy(t,code,size:17.6,font:"mono",fill:paper,tracking:6.4)])
  v(20*t.u);rect(width:100%,height:6*t.u,fill:ink,stroke:none);v(40*t.u)
}
#let header(t,d) = {
  v(2*t.u)
  box(inset:7*t.u,stroke:3*t.u+ink,outset:-1.5*t.u)[#grid(columns:(100*t.u,)*3,gutter:4*t.u,..(navy,rust,gold).map(c=>rect(width:100*t.u,height:12*t.u,fill:c,stroke:none)))]
  v(40*t.u);copy(t,"SYSTEM REPORT // "+upper(d.date),size:16,font:"mono",weight:700,fill:navy,tracking:6.4);v(20*t.u)
  for (i,value) in ("DAILY","ANALYSIS","EXPORT").enumerate() {
    context {
      let body=copy(t,value,size:112,font:"display",weight:700,lh:.85,tracking:-3.2)
      let width=measure(body).width
      block(width:100%,height:95.2*t.u)[
        #if i==1 {
          place(top+left,dx:6*t.u,dy:106*t.u,rect(width:width,height:20*t.u,fill:orange.transparentize(80%),stroke:none))
          place(top+left,dy:100*t.u,rect(width:width,height:20*t.u,fill:gold.transparentize(50%),stroke:none))
        }
        #glow(t,value,size:112,weight:700,fill:if i==1 {orange}else{ink},shade:orange.transparentize(60%),dx:6,dy:6,blur:0,tracking:-3.2,lh:.85)
      ]
    }
  }
  v(40*t.u)
  grid(columns:(60*t.u,)*3,gutter:20*t.u,..("check","list","document").map(name=>box(width:60*t.u,height:60*t.u)[
    #place(top+left,dx:4*t.u,dy:4*t.u,rect(width:60*t.u,height:60*t.u,fill:ink,stroke:none))
    #box(width:60*t.u,height:60*t.u,fill:white,stroke:2*t.u+ink,outset:-1*t.u)[#align(center+horizon,image(name+".svg",width:32*t.u,height:32*t.u))]
  ]))
  v(40*t.u)
  block(width:800*t.u,inset:(left:38*t.u),stroke:(left:8*t.u+orange),outset:(left:-4*t.u))[
    #copy(t,"Daily activity analysis report, generated based on message statistics and AI analysis",size:22.4,font:"mono",fill:black.transparentize(30%),lh:1.8)
  ]
  v(60*t.u)
  grid(columns:(auto,auto,1fr),gutter:80*t.u,..(("GENERATED AT",d.generated_at),("PEAK WINDOW",d.peak)).map(e=>[
    #copy(t,e.at(0),size:14.4,font:"mono",fill:rust,tracking:3.2)#v(12*t.u)
    #copy(t,e.at(1),size:22.4,font:"mono",weight:700)
  ]))
  v(60*t.u);rect(width:100%,height:2*t.u,fill:ink,stroke:none);v(100*t.u)
}
#let statistics(t,d) = {
  grid(columns:(1fr,)*4,gutter:40*t.u,..(("MESSAGES",d.message_count,"累计消息数量"),("PARTICIPANTS",d.participant_count,"参与者计数"),("CHARACTERS",d.characters,"文本总字数"),("EMOJI",d.emoji_count,"表情符号统计")).map(e=>frame(t,padx:30,pady:40,dx:8,dy:8,[
    #copy(t,e.at(0),size:14.4,font:"mono",weight:700,fill:navy,tracking:4.8)#v(20*t.u)
    #block(height:64*t.u)[#copy(t,str(e.at(1)),size:80,font:"display",fill:orange,lh:.8)]#v(15*t.u)
    #copy(t,e.at(2),size:16,font:"mono",fill:rgb("666666"))
  ])))
  v(100*t.u)
}
#let quality(t,d) = {
  if d.review==none {return}
  heading(t,"QUALITY ANALYSIS","STABILITY_METRICS")
  let r=d.review
  frame(t,padx:24,pady:24,dx:8,dy:8,shade:black.transparentize(90%),[
    #place(top+left,dx:-24*t.u,dy:-24*t.u,rect(width:100%+48*t.u,height:6*t.u,stroke:none,fill:tiling(size:(30*t.u,6*t.u))[
      #rect(width:30*t.u,height:6*t.u,fill:gold,stroke:none)
      #place(top+left,rect(width:15*t.u,height:6*t.u,fill:orange,stroke:none))
    ]))
    #v(15*t.u)
    #grid(columns:(1fr,auto),gutter:20*t.u,align:bottom,
      copy(t,upper(r.title),size:36,weight:700,font:"display",fill:navy,tracking:1),
      if r.subtitle!="" {context {
        let body=copy(t,r.subtitle,size:19.8,weight:700,font:"mono",fill:white)
        let m=measure(body)
        box(width:m.width+24*t.u,height:m.height+12*t.u)[
          #place(top+left,dx:2*t.u,dy:2*t.u,rect(width:100%,height:100%,fill:ink,stroke:none))
          #box(width:100%,height:100%,inset:(x:12*t.u,y:6*t.u),fill:gold,stroke:2*t.u+ink,outset:-1*t.u)[#body]
        ]
      }}else{none})
    #v(10*t.u)#rect(width:100%,height:2*t.u,fill:ink,stroke:none)#v(25*t.u)
    #block(width:100%,height:40*t.u,inset:2*t.u,stroke:2*t.u+ink,outset:-1*t.u,fill:rgb("eeeeee"),clip:true)[
      #layout(size=>{
        let total=calc.max(100,r.dimensions.map(x=>x.percentage).sum(default:0))
        for (i,x) in r.dimensions.enumerate() {
          if x.percentage>0 {
            let width=x.percentage/total*size.width
            let label=x.name
            let clusters=label.clusters()
            while measure(copy(t,label,size:16.2,font:"mono",weight:700,lh:1)).width>width - 10*t.u and clusters.len()>0 {
              clusters=clusters.slice(0,clusters.len()-1)
              label=clusters.join()+"…"
            }
            if width < 26.2*t.u {label=""}
            place(top+left,dx:r.dimensions.slice(0,i).map(x=>x.percentage).sum(default:0)/total*size.width,
              block(width:width,height:36*t.u,inset:(x:5*t.u),fill:palette.at(calc.rem(i,8)),stroke:if i < r.dimensions.len()-1 {(right:2*t.u+ink)}else{none},outset:-1*t.u,clip:true)[
                #align(center+horizon,copy(t,label,size:16.2,weight:700,font:"mono",fill:if calc.rem(i,8) in (2,4,6) {black}else{white},lh:1))
              ])
          }
        }
      })
    ]
    #v(25*t.u)
    #layout(size=>{
      let bodies=r.dimensions.filter(x=>x.percentage>0).map(x=>[
        #block(inset:(bottom:6*t.u),stroke:(bottom:2*t.u+grid-color),outset:(bottom:-1*t.u))[
          #copy(t,upper(x.name),size:17.1,font:"mono",weight:700,fill:navy,lh:1.5)
        ]#v(10*t.u)
        #copy(t,"PROPORTION: "+str(x.percentage)+"%",size:14.535,font:"mono",weight:700,fill:rust,lh:1.5)#v(8*t.u)
        #copy(t,runs(t,x.comment),size:17.1,font:"mono",lh:1.5)
      ])
      let width=(size.width - 20*t.u)/2
      for start in range(0,bodies.len(),step:2) {
        let row=bodies.slice(start,calc.min(start+2,bodies.len()))
        let height=calc.max(..row.map(body=>measure(body,width:width - 34*t.u).height/t.u+36))
        grid(columns:(width,width),gutter:20*t.u,..row.map(body=>frame(t,padx:15,pady:15,stroke:2,top-width:4,top-color:rust,fill:rgb("fafafa"),shade:black.transparentize(95%),dx:3,dy:3,height:height,body)))
        if start+2 < bodies.len() {v(20*t.u)}
      }
    })
    #v(25*t.u)
    #frame(t,padx:18,pady:18,fill:navy,dx:4,dy:4,[
      #copy(t,[#box(inset:(x:14*t.u,y:6*t.u),fill:orange,stroke:2*t.u+white,outset:-1*t.u)[#copy(t,"OVERVIEW",size:19.8,font:"display",weight:700,tracking:1,fill:white,lh:1.6)]#h(15*t.u)#runs(t,r.summary)],size:19.8,font:"mono",fill:white,lh:1.6)
    ])
  ])
  v(125*t.u)
}
#let topics(t,d) = {
  if d.topics.len()==0 {return}
  heading(t,"THREAD MATRIX","TOPICS_MODULE")
  for (i,x) in d.topics.enumerate() {
    frame(t,[
      #place(top+left,dx:-40*t.u,dy:-40*t.u,rect(width:16*t.u,height:100%+80*t.u,fill:tiling(size:(42.4264*t.u,42.4264*t.u))[
        #place(top+left,image(bytes("<svg xmlns='http://www.w3.org/2000/svg' width='42.4264' height='42.4264'><path d='M-21.2132 0H0L42.4264 42.4264H21.2132Z M21.2132 0H42.4264L84.8528 42.4264H63.6396Z' fill='#a93226'/></svg>"),format:"svg",width:42.4264*t.u,height:42.4264*t.u))
      ],stroke:none))
      #block(width:100%,inset:(left:30*t.u))[
        #copy(t,upper(x.title),size:48,font:"display",weight:700)#v(20*t.u)
        #box(inset:(x:15*t.u,y:8*t.u),fill:grid-color)[#copy(t,[#{"SUBJECT ID: #"+(if i < 9 {"0"}else{""})+str(i+1)+" // PARTICIPANTS: "}#runs(t,x.contributors)],size:16,font:"mono",fill:navy)]#v(20*t.u)
        #copy(t,runs(t,x.detail),size:22.4,fill:rgb("333333"),lh:1.8)
      ]
    ])
    if i < d.topics.len()-1 {v(40*t.u)}
  }
  v(100*t.u)
}
#let portraits(t,d) = {
  if d.portraits.len()==0 {return}
  heading(t,"OPERATOR REGISTRY","TITLES_MODULE")
  frame(t,padx:60,pady:60,shade:grid-color,[
    #layout(size=>{
      let width=(size.width - 50*t.u)/2
      let bodies=d.portraits.map(p=>[
        #grid(columns:(120*t.u,1fr),gutter:30*t.u,align:horizon,
          box(width:120*t.u,height:120*t.u)[
            #place(top+left,dx:6*t.u,dy:6*t.u,rect(width:120*t.u,height:120*t.u,fill:gold,stroke:none))
            #box(width:120*t.u,height:120*t.u,inset:3*t.u,fill:rgb("eeeeee"),stroke:3*t.u+ink,outset:-1.5*t.u)[#avatar(t,p.avatar,size:114)]
          ],[
            #copy(t,p.name,size:35.2,weight:700,font:"display",lh:1)#v(10*t.u)
            #box(inset:(x:12*t.u,y:5*t.u),fill:ink)[#copy(t,[#p.profile#h(10*t.u)#text(fill:gold,"//")#h(10*t.u)#p.title],size:14.4,font:"mono",fill:white)]#v(31*t.u)
            #copy(t,runs(t,p.reason),size:19.2,fill:rgb("444444"),lh:1.6)
          ])
      ])
      for start in range(0,bodies.len(),step:2) {
        let row=bodies.slice(start,calc.min(start+2,bodies.len()))
        let height=calc.max(..row.map(body=>measure(body,width:width - 84*t.u).height/t.u+84))
        grid(columns:(width,width),gutter:50*t.u,..row.enumerate().map(((i,body))=>frame(t,stroke:2,shade:grid-color,dx:8,dy:8,height:height,centered:true,watermark:d.portraits.at(start+i),clip:true,body)))
        if start+2 < bodies.len() {v(50*t.u)}
      }
    })
  ])
  v(100*t.u)
}
#let quotes(t,d) = {
  if d.quotes.len()==0 {return}
  heading(t,"GOLDEN LINES","QUOTES_MODULE")
  for (i,q) in d.quotes.enumerate() {
    frame(t,left-width:20,left-color:orange,shade:black.transparentize(95%),[
      #let body=[
        #place(top+left,dx:-20*t.u,dy:-10*t.u,copy(t,"\"",size:48,font:"mono",fill:orange.transparentize(80%),italic:true,lh:1.6))
        #copy(t,runs(t,q.content),size:25.6,font:"mono",italic:true,lh:1.6)#v(20*t.u)
        #copy(t,"ORIGIN: "+upper(q.sender),size:25.6,font:"display",weight:700,fill:navy)#v(10*t.u)
        #copy(t,[#{"ANALYSIS // "}#runs(t,q.reason)],size:16,font:"mono",fill:rgb("666666"))
      ]
      #if q.avatar!="" {
        grid(columns:(90*t.u,1fr),gutter:30*t.u,align:top,
          box(width:90*t.u,height:90*t.u,inset:2*t.u,radius:50%,stroke:2*t.u+ink,outset:-1*t.u)[#avatar(t,q.avatar,size:86,round:true,contrast:1)],body)
      }else{body}
    ])
    if i < d.quotes.len()-1 {v(30*t.u)}
  }
}
#let console(t,d) = layout(size=>{
  let body=block(width:size.width,inset:45*t.u)[
    #grid(columns:(12*t.u,)*3,gutter:15*t.u,..range(3).map(_=>rect(width:12*t.u,height:12*t.u,fill:rgb("292929"),stroke:1*t.u+rgb("414141"),outset:-.5*t.u)))#v(30*t.u)
    #copy(t,"Peak Activity Window",font:"mono",fill:rgb("00ff41"),lh:23/18)#v(15*t.u)
    #glow(t,d.peak)#v(15*t.u)
    #rect(width:100%,height:2*t.u,fill:rgb("333333"),stroke:none)#v(15*t.u)
    #copy(t,"活跃序列 SCAN // 消息流强度 "+str(d.message_count),font:"mono",size:16,fill:rgb("00cc34"))
  ]
  let height=measure(body).height
  place(top+left,dx:10*t.u,dy:10*t.u,rect(width:size.width,height:height,fill:black.transparentize(90%),stroke:none))
  block(width:size.width,height:height,fill:rgb("111111"),radius:6*t.u,stroke:5*t.u+ink,outset:-2.5*t.u,clip:true)[
    #let w=size.width/t.u - 10
    #let h=height/t.u - 10
    #let inset="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w)+"' height='"+str(h)+"'><defs><filter id='inset' filterUnits='userSpaceOnUse' x='0' y='0' width='"+str(w)+"' height='"+str(h)+"'><feGaussianBlur in='SourceAlpha' stdDeviation='30' result='b'/><feComposite in='SourceAlpha' in2='b' operator='out' result='s'/><feFlood flood-color='#000'/><feComposite in2='s' operator='in'/></filter></defs><rect width='100%' height='100%' fill='white' filter='url(#inset)'/></svg>"
    #place(top+left,dx:5*t.u,dy:5*t.u,image(bytes(inset),format:"svg",width:w*t.u,height:h*t.u))
    #body
    #place(top+left,dx:5*t.u,dy:5*t.u,rect(width:w*t.u,height:h*t.u,stroke:none,fill:tiling(size:(4*t.u,6*t.u))[
      #rect(width:4*t.u,height:6*t.u,stroke:none,fill:gradient.linear(rgb("ff0000").transparentize(95%),rgb("00ff00").transparentize(98%),rgb("0000ff").transparentize(95%),angle:0deg,space:rgb))
      #place(top+left,dy:3*t.u,rect(width:4*t.u,height:3*t.u,fill:black.transparentize(90%),stroke:none))
    ]))
  ]
  v(100*t.u)
})
#let activity(t,d) = {
  heading(t,"HOURLY BROADCAST","ACTIVITY_SPECTRUM")
  frame(t,padx:60,pady:60,shade:grid-color,[
    #block(width:100%,height:350*t.u,inset:(top:20*t.u,bottom:23*t.u),stroke:(bottom:3*t.u+ink),outset:(bottom:-1.5*t.u))[
      #let highest=calc.max(1,..d.hours)
      #grid(columns:(1fr,)*24,..d.hours.enumerate().map(((hour,count))=>align(center)[
        #box(width:100%,height:266*t.u)[#align(bottom)[
          #copy(t,str(count),size:12.8,font:"mono",weight:700,lh:17/12.8)#v(20*t.u)
          #box(width:70%,height:calc.max(4,calc.min(229,count/highest*307))*t.u)[
            #place(top+left,dx:4*t.u,rect(width:100%,height:100%,fill:black.transparentize(95%),stroke:none))
            #rect(width:100%,height:100%,stroke:2*t.u+ink,outset:-1*t.u,fill:gradient.linear(rgb("d7651a"),orange,angle:0deg,space:rgb))
          ]
        ]]
        #v(25*t.u)#rotate(-45deg,reflow:false,copy(t,(if hour < 10 {"0"}else{""})+str(hour)+":00",size:12,font:"mono",weight:700,fill:navy,lh:16/12))
      ])))
    ]
    #v(40*t.u)
  ])
  v(100*t.u)
}

#let render(d) = {
  let u=72/d.ppi*d.width/1400*1pt
  let body=if d.font_language=="zh-Hant" {("Noto Sans TC","Noto Sans SC")}else{("Noto Sans SC","Noto Sans TC")}
  let t=(u:u,body:body,mono:if d.font_language=="zh-Hant" {("Noto Serif TC","Noto Serif SC")}else{("Noto Serif SC","Noto Serif TC")})
  set page(width:1400*u,height:auto,margin:0pt,fill:paper)
  set text(font:body,size:18*u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none,hyphenate:false)
  set par(leading:0pt,spacing:0pt)
  set smartquote(enabled:false)
  set page(background:layout(size=>{
    box(width:size.width,height:size.height)[
      #place(top+left,dx:20*u,dy:20*u,rect(width:1400*u,height:size.height - 13*u,fill:black.transparentize(95%),stroke:none))
      #place(top+left,dx:-15*u,dy:15*u,rect(width:1400*u,height:size.height - 17*u,stroke:1*u+ink.transparentize(70%),fill:none))
      #place(top+left,rect(width:1400*u,height:size.height - 13*u,fill:paper,stroke:(right:4*u+ink,bottom:4*u+ink),outset:(right:-2*u,bottom:-2*u)))
    ]
  }))
  // HTML 的固定扫描罩覆盖首个 900px 视口；控制台自己的扫描线另外覆盖本体。
  set page(foreground:place(top+left,rect(width:100%,height:900*u,stroke:none,fill:tiling(size:(4*u,4*u))[
    #place(top+left,dy:2*u,rect(width:4*u,height:2*u,fill:black.transparentize(95%),stroke:none))
  ])))
  block(width:1400*u,inset:(left:80*u,right:84*u,top:100*u,bottom:117*u))[
    #header(t,d)#statistics(t,d)#console(t,d)#activity(t,d)#quality(t,d)#topics(t,d)#portraits(t,d)#quotes(t,d)
    #v(100*u)#rect(width:100%,height:8*u,fill:ink,stroke:none)#v(60*u)
    #grid(columns:(1fr,auto),align:horizon,gutter:20*u,
      copy(t,"CRT_EXPORT_CHANNEL // AstrBot 群日常分析插件",size:14.4,font:"mono"),
      copy(t,"SXP-Simon / astrbot_plugin_qq_group_daily_analysis",size:14.4,font:"mono",weight:700,fill:orange))
    #v(20*u)
    #copy(t,[#{"Total Tokens // "+str(d.tokens.at(0))}#h(30*u)#{"Prompt // "+str(d.tokens.at(1))}#h(30*u)#{"Completion // "+str(d.tokens.at(2))}],size:14.4,font:"mono",fill:ink.transparentize(40%))
    #v(20*u)#copy(t,d.generated_at+" // END_OF_LINE_",size:14.4,font:"mono")#v(60*u)
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

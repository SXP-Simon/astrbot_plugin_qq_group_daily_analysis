// 手账模板独立保留贴纸、装订线、瀑布流与对话气泡；角色图使用 CDN 缓存。
#import "common.typ":shadow
#let ink=rgb("5d4037")
#let muted=rgb("8d6e63")
#let bg=rgb("fdfbf7")
#let yellow=rgb("fff9c4")
#let pink=rgb("ffccbc")
#let blue=rgb("b3e5fc")
#let green=rgb("c8e6c9")
#let purple=rgb("e1bee7")
#let orange=rgb("ff7043")
#let copy(t,body,size:16,weight:400,fill:ink,lh:1.6,font:none,tracking:0,stroke:none) = {
  set par(leading:0pt,spacing:0pt)
  let fonts=if font=="title" {("ZCOOL KuaiLe",..t.body)}else if font=="hand" {t.hand}else{t.body}
  let baseline=if font=="title" {.38}else if font=="hand" {.365}else{.436}
  text(font:fonts,size:size*t.u,weight:weight,fill:fill,stroke:stroke,tracking:tracking*t.u,top-edge:(lh/2+baseline)*1em,bottom-edge:-(lh/2-baseline)*1em,body)
}
#let icon(t,name,size:24,color:orange) = image(bytes(read(name+".svg").replace("currentColor",color.to-hex())),format:"svg",width:size*t.u,height:size*t.u)
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
#let rule(t,paint:rgb("eeeeee"),dashed:false,width:100%,height:2) = block(width:width,height:height*t.u)[
  #place(horizon,line(length:100%,stroke:(paint:paint,thickness:height*t.u,dash:if dashed {(array:(height*1.5*t.u,height*1.5*t.u))}else{"solid"})))
]
#let tape(t,width:80,height:24,fill:blue,angle:-2,masked:false,outlined:false) = {
  let body=box(width:width*t.u,height:height*t.u)[
  #if masked {
    let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(width)+"' height='"+str(height)+"'><defs><mask id='holes'><rect width='100%' height='100%' fill='white'/>"+range(0,width,step:10).map(x=>"<circle cx='"+str(x+5)+"' cy='"+str(height/2)+"' r='4.5' fill='black'/>").join("")+"</mask></defs><rect width='100%' height='100%' fill='"+fill.to-hex()+"'"+(if outlined {" stroke='#00000026' stroke-width='1'"}else{""})+" mask='url(#holes)'/></svg>"
    image(bytes(svg),format:"svg",width:100%,height:100%)
  }else{rect(width:100%,height:100%,fill:fill,stroke:if outlined {1*t.u+black.transparentize(85%)}else{none})}
  ]
  rotate(angle*1deg,if outlined and not masked {shadow(t,body,radius:0,blur:4,dy:1,color:black.transparentize(85%))}else{body})
}
#let paper(t,body,padx:20,pady:20,radius:12,fill:white,stroke:2,color:ink,dashed:false,dx:4,dy:4,shadow-fill:black.transparentize(90%),blur:0,clip:false,angle:0,height:none,coil:false,holes:false,stamp:false,thick-shadow:false,watermark:none) = layout(size=>{
  let inner=block(width:size.width,inset:(x:(padx+stroke)*t.u,y:(pady+stroke)*t.u))[#body]
  let m=measure(inner)
  if height!=none {m.height=calc.max(m.height,height*t.u)}
  let r=radius
  if type(radius)==dictionary {for (key,value) in radius {r.insert(key,value*t.u)}}else{r=radius*t.u}
  let panel=block(width:size.width,height:m.height,radius:r,clip:clip)[
    #place(top+left,block(width:m.width,height:m.height,fill:fill,radius:r,stroke:(paint:color,thickness:stroke*t.u,dash:if dashed {(array:(stroke*1.5*t.u,stroke*1.5*t.u))}else{"solid"}),outset:-stroke/2*t.u)[])
    #inner
    #if watermark!=none and watermark.image!="" {place(bottom+right,dx:-8*t.u,dy:-8*t.u,image(watermark.image,width:m.width*.38,height:calc.min(measure(image(watermark.image,width:m.width*.38)).height,m.height*.8),fit:watermark.image_fit))}
    #if stamp {place(top+left,dx:7*t.u,dy:7*t.u,rect(width:m.width - 14*t.u,height:m.height - 14*t.u,radius:8*t.u,fill:none,stroke:(paint:rgb("e0e0e0"),thickness:1*t.u,dash:"dotted")))}
    #if coil {
      let pattern=tiling(size:(10*t.u,15*t.u))[#rect(width:10*t.u,height:2*t.u,fill:rgb("cccccc"),stroke:none)]
      place(top+left,dx:12*t.u,dy:20*t.u,block(width:10*t.u,height:m.height - 40*t.u,fill:pattern,stroke:(left:2*t.u+rgb("999999")),outset:(left:-1*t.u))[])
    }
    #if holes {
      let gap=(m.height/t.u - 36)/4
      for i in range(3) {place(top+left,dx:16*t.u,dy:(gap*(i+1)+i*12)*t.u,circle(radius:6*t.u,fill:bg,stroke:.8*t.u+black.transparentize(94%)))}
    }
  ]
  let result=if blur>0 {shadow(t,panel,radius:if type(radius)==dictionary {12}else{radius},blur:blur,dy:dy,color:shadow-fill)}else{block(width:m.width,height:m.height)[
    #if thick-shadow {place(top+left,dx:2*t.u,dy:2*t.u,rect(width:m.width+2*t.u,height:m.height+2*t.u,radius:r,fill:ink,stroke:none))}
    #place(top+left,dx:dx*t.u,dy:dy*t.u,rect(width:m.width,height:m.height,radius:r,fill:shadow-fill,stroke:none))
    #panel
  ]}
  rotate(angle*1deg,result)
})
#let heading(t,name,title,centered:false,gap:15) = {
  align(if centered {center}else{left},grid(columns:(auto,auto),gutter:8*t.u,align:horizon,icon(t,name,size:31.2),copy(t,title,size:24,font:"title")))
  v(gap*t.u)
}
#let face(t,path,size:60,stroke:2,color:ink) = box(width:size*t.u,height:size*t.u,radius:50%,fill:rgb("eeeeee"),stroke:stroke*t.u+color,outset:-stroke/2*t.u,inset:stroke*t.u,clip:true)[
  #if path!="" {box(width:100%,height:100%,radius:50%,clip:true)[#image(path,width:100%,height:100%,fit:"cover")]}else{align(center+horizon,icon(t,"user",size:32,color:rgb("aaaaaa")))}
]
#let header(t,d) = {
  v(20*t.u)
  rotate(-2deg,block(width:816*t.u)[
    #paper(t,padx:60,pady:20,radius:15,stroke:3,dashed:true,dx:5,dy:5,shadow-fill:blue,[
      #align(center,copy(t,"五彩斑斓的一天，来看看群里发生了什么吧！",size:51.2,weight:700,fill:orange,font:"title",stroke:2*t.u+ink))
      #place(top+center,dy:-(if d.review!=none {32}else{35})*t.u,tape(t,width:if d.review!=none {100}else{120},height:if d.review!=none {30}else{25},fill:if d.review!=none {white.transparentize(40%)}else{rgb("ffab91").transparentize(44%)},masked:true,outlined:d.review!=none))
      #place(bottom+right,dx:83*t.u,dy:38*t.u,rotate(5deg,box(inset:(x:16*t.u,y:6*t.u),fill:yellow,stroke:1*t.u+ink)[#copy(t,d.date,size:19.2,font:"hand")]))
    ])
  ])
  v(50*t.u)
}
#let statistics(t,d) = context {
  let stripes=tiling(size:(28.284*t.u,28.284*t.u))[
    #rect(width:28.284*t.u,height:28.284*t.u,fill:yellow,stroke:none)
    #place(top+left,polygon((0pt,0pt),(14.142*t.u,0pt),(28.284*t.u,14.142*t.u),(28.284*t.u,28.284*t.u),fill:white.transparentize(80%),stroke:none))
    #place(top+left,polygon((0pt,14.142*t.u),(14.142*t.u,28.284*t.u),(0pt,28.284*t.u),fill:white.transparentize(80%),stroke:none))
  ]
  let peak=[
    #align(center)[
      #copy(t,[#text(font:"Noto Color Emoji")[✨]#h(6*t.u)Highlight Time],size:24,fill:muted,font:"hand")#v(5*t.u)
      #v(10*t.u)#copy(t,d.peak,size:40,font:"title")#v(10*t.u)
      #copy(t,[（此刻，世界色彩斑#linebreak()斓）],size:24,fill:muted,font:"hand")
    ]
  ]
  let height=measure(peak,width:249*t.u).height/t.u+44
  let entries=(("消息总数",d.message_count,"message",orange),("参与人数",d.participant_count,"users",green),("表情统计",d.emoji_count,"smile",blue),("总字符数",d.characters,"document",purple))
  grid(columns:(498*t.u,293*t.u),gutter:25*t.u,
    grid(columns:(1fr,1fr),gutter:20*t.u,..entries.map(e=>paper(t,padx:15,pady:15,height:(height - 20)/2,stamp:true,align(center+horizon)[
      #icon(t,e.at(2),size:35.2,color:e.at(3))#v(5*t.u)
      #copy(t,str(e.at(1)),size:28.8,fill:orange,font:"title",lh:1)#v(5*t.u)
      #copy(t,e.at(0),size:16,fill:muted,font:"hand")
    ]))),
    paper(t,height:height,radius:20,fill:stripes,dx:6,dy:6,shadow-fill:pink,[
      #place(top+center,dy:-32*t.u,tape(t,width:60,height:20,fill:white.transparentize(40%),angle:0))
      #peak
    ]))
  v(40*t.u)
}
#let activity(t,d) = paper(t,padx:20,pady:20,radius:(top-left:5,top-right:20,bottom-right:20,bottom-left:5),dx:5,dy:5,shadow-fill:black.transparentize(95%),coil:true,[
  #block(inset:(left:20*t.u))[
    #heading(t,"chart","24H 活跃轨迹")#v((15+25.6)*t.u)
    #block(width:100%,height:218*t.u,inset:(x:10*t.u,top:20*t.u,bottom:5*t.u))[
      #let highest=calc.max(1,..d.hours)
      #grid(columns:(1fr,)*24,gutter:0pt,..d.hours.enumerate().map(((i,n))=>block(width:100%,height:193*t.u,inset:(x:2*t.u))[
        #if n>0 {place(top+center,dy:-20*t.u,copy(t,str(n),size:11.2,weight:700,fill:muted,font:"hand"))}
        #let height=calc.min(165.8,calc.max(4,n/highest*193))
        #let fill=if n==0 {muted.transparentize(80%)}else if n/highest>=.7 {orange}else if n/highest>=.3 {green}else{blue}
        #block(width:100%,height:165.8*t.u)[
          #place(bottom+left,dx:2*t.u,dy:2*t.u,rect(width:100%,height:height*t.u,radius:(top-left:5*t.u,top-right:5*t.u),fill:black.transparentize(if n==0 {98%}else{90%}),stroke:none))
          #place(bottom+left,rect(width:100%,height:height*t.u,radius:(top-left:5*t.u,top-right:5*t.u),fill:fill,stroke:none))
        ]
        #v(8*t.u)#align(center,copy(t,(if i < 10 {"0"}else{""})+str(i),size:12,fill:muted,font:"hand"))
      ]))
    ]
    #rule(t,paint:muted)
  ]
])
#let topics(t,d) = {
  let lines=tiling(size:(40*t.u,40*t.u))[
    #rect(width:40*t.u,height:40*t.u,fill:white,stroke:none)
    #place(top+left,dy:39*t.u,rect(width:40*t.u,height:1*t.u,fill:rgb("b2ebf2"),stroke:none))
  ]
  paper(t,padx:30,pady:30,radius:0,stroke:1,color:rgb("dddddd"),fill:lines,dy:5,blur:15,shadow-fill:black.transparentize(97%),holes:true,[
    #block(inset:(left:20*t.u))[
      #heading(t,"topics","今日话题 Topics")
      #for (i,x) in d.topics.enumerate() {
        block(width:100%,inset:(top:4*t.u))[
          #grid(columns:(20*t.u,1fr),gutter:15*t.u,align:top,
            box(width:20*t.u,height:20*t.u,fill:white,stroke:2*t.u+ink,inset:3*t.u,outset:-1*t.u)[
              #place(top+left,dy:8*t.u,polygon((1.96*t.u,6.16*t.u),(0pt,9.1*t.u),(7*t.u,14*t.u),(14*t.u,2.24*t.u),(11.2*t.u,0pt),(6.02*t.u,8.68*t.u),fill:orange,stroke:none))
            ],block(inset:(top:6*t.u))[
              #grid(columns:(auto,1fr),gutter:10*t.u,align:horizon,
                box(fill:gradient.linear((white,0%),(white,60%),(if calc.rem(i+3,3)==0 {green}else if calc.even(i+3) {blue}else{pink},60%),(if calc.rem(i+3,3)==0 {green}else if calc.even(i+3) {blue}else{pink},100%),angle:90deg,space:rgb))[#copy(t,x.title,size:24,font:"title",lh:1.5)],
                copy(t,[#("#")#(if i+1 < 10 {"0"}else{""})#(i+1)],size:13.6,fill:rgb("999999"),lh:1.5))
              #v(8*t.u)#copy(t,[#text(font:"Noto Color Emoji")[🙋‍♀️] 参与者： #runs(t,x.contributors)],size:16.8,fill:muted,font:"hand",lh:1.5)
              #v(8*t.u)#copy(t,runs(t,x.detail),size:19.2,fill:rgb("666666"),font:"hand",lh:1.5)
            ])
        ]
        v(20*t.u)
      }
    ]
  ])
}
#let portraits(t,d) = context {
  heading(t,"user","群友画像 Portraits",centered:true)
  let cards=d.portraits.enumerate().map(((i,p))=>{
    let body=[
      #grid(columns:(60*t.u,1fr),gutter:15*t.u,align:top,face(t,p.avatar),[
        #copy(t,if p.name=="" {"匿名群友"}else{p.name},size:20,font:"title",lh:1.2)#v(6*t.u)
        #par(leading:8*t.u)[
          #box(inset:(x:9*t.u,y:3*t.u),radius:6*t.u,fill:rgb("fffde7"),stroke:1*t.u+rgb("ffb74d"))[#copy(t,p.title,size:13.6,fill:rgb("bf360c"),font:"hand")]#h(8*t.u)#box(inset:(x:9*t.u,y:3*t.u),radius:6*t.u,fill:rgb("ede7f6"),stroke:1*t.u+rgb("9575cd"))[#copy(t,p.profile,size:13.6,weight:700,fill:rgb("512da8"),font:"hand",tracking:.5)]
        ]
      ])
      #v(15*t.u)#rule(t,paint:rgb("f0f0f0"),dashed:true)#v(30*t.u)
      #block(width:100%,inset:(left:19*t.u,right:15*t.u,y:12*t.u),fill:rgb("f8fbff"),stroke:(left:4*t.u+blue),outset:(left:-2*t.u),radius:4*t.u)[#copy(t,runs(t,p.reason),size:16.8,fill:rgb("444444"),font:"hand")]
    ]
    let panel=paper(t,padx:20,pady:20,fill:rgb("fffbf0"),color:if calc.rem(i+1,5)==0 {green}else if calc.rem(i+1,3)==0 {pink}else if calc.even(i+1) {blue}else{ink},thick-shadow:true,shadow-fill:rgb("465064").transparentize(90%),angle:if calc.rem(i+1,5)==0 {.5}else if calc.rem(i+1,3)==0 {-1.5}else if calc.even(i+1) {1}else{0},clip:true,watermark:p,[
      #place(top+center,dy:-32*t.u,tape(t,fill:(if calc.rem(i+1,3)==0 {green}else if calc.even(i+1) {pink}else{blue}).transparentize(20%),angle:if calc.rem(i+1,3)==0 {-1}else if calc.even(i+1) {3}else{-2}))
      #body
    ])
    (body:panel,height:measure(body,width:351.5*t.u).height/t.u+44+30)
  })
  // 按 CSS 多栏的源顺序连续分列，并选择总高度最接近的分割点；最后一张卡也保留底部间距。
  let cut=cards.len();let best=1e9
  for n in range(1,cards.len()+1) {
    let h=calc.max(cards.slice(0,n).map(c=>c.height).sum(default:0),cards.slice(n).map(c=>c.height).sum(default:0))
    if h < best {best=h;cut=n}
  }
  grid(columns:(1fr,1fr),gutter:25*t.u,..(cards.slice(0,cut),cards.slice(cut)).map(column=>[
    #for c in column {c.body;v(30*t.u)}
  ]))
}
#let quotes(t,d) = context {
  heading(t,"quote","群贤毕至 Bible Quotes",centered:true,gap:50)
  for (i,q) in d.quotes.enumerate() {
    let reverse=calc.even(i)
    let width=calc.min(816*.9 - 85,measure(copy(t,runs(t,q.content),size:20.8,font:"title",lh:1.4)).width/t.u+54)
    let reason-width=calc.min(816*.9 - 85,calc.max(measure(copy(t,runs(t,q.reason),size:14.4,fill:rgb("666666"),lh:1.5)).width/t.u,measure(copy(t,"AI 锐评：",size:14.4,weight:700,font:"title",lh:1.5)).width/t.u+36)+32)
    let column-width=calc.max(width,reason-width)
    align(if reverse {right}else{left},block(width:(column-width+85)*t.u)[
      #grid(columns:if reverse {(column-width*t.u,70*t.u)}else{(70*t.u,column-width*t.u)},gutter:15*t.u,align:top,..(if reverse {(true,false)}else{(false,true)}).map(content=>if not content {
        align(center,box(width:60*t.u,height:60*t.u,radius:50%,fill:white,stroke:2*t.u+(if reverse {orange}else{blue}),outset:1*t.u,inset:3*t.u,clip:true)[#if q.avatar!="" {box(width:100%,height:100%,radius:50%,clip:true)[#image(q.avatar,width:100%,height:100%,fit:"cover")]}])
      }else{align(if reverse {right}else{left})[
        #box(inset:if reverse {(right:15*t.u)}else{(left:10*t.u)})[
          #let sender=copy(t,if q.sender=="" {"匿名群友"}else{q.sender},size:20,font:"hand",lh:1.2)
          #place(bottom+left,dx:if reverse {0pt}else{10*t.u},dy:-2*t.u,rect(width:measure(sender).width,height:4*t.u,fill:(if reverse {orange}else{blue}).transparentize(60%),stroke:none))
          #sender
        ]
        #block(width:width*t.u)[
          #paper(t,padx:25,pady:15,radius:if reverse {(top-left:20,top-right:4,bottom:20)}else{(top-left:4,top-right:20,bottom:20)},fill:if reverse {yellow}else{white},dx:if reverse {-4}else{4},dy:4,shadow-fill:if reverse {pink}else{blue})[
            #copy(t,runs(t,q.content),size:20.8,font:"title",lh:1.4)#v(5*t.u)
          ]
        ]
        #v(-5*t.u)
        #block(width:reason-width*t.u)[
          #move(dx:if reverse {-10*t.u}else{10*t.u},rotate(if reverse {1deg}else{-1deg},paper(t,padx:15,pady:10,radius:(top:0,bottom:10),stroke:1,color:rgb("dddddd"),fill:if reverse {rgb("f3e5f5")}else{rgb("fffde7")},blur:5,dy:2)[
            #align(left)[
              #copy(t,[#text(font:"Noto Color Emoji")[🤣👉] AI 锐评：],size:14.4,weight:700,fill:orange,font:"title",lh:1.5)#v(4*t.u)
              #copy(t,runs(t,q.reason),size:14.4,fill:rgb("666666"),lh:1.5)
            ]
          ]))
        ]
      ]}))
    ])
    if i < d.quotes.len() - 1 {v(35*t.u)}
  }
  v(30*t.u)
}
#let quality(t,d) = {
  let r=d.review
  let colors=(rgb("ffb74d"),rgb("ff8a65"),rgb("ba68c8"),rgb("4db6ac"),rgb("4dd0e1"),rgb("64b5f6"),rgb("81c784"),rgb("e57373"))
  paper(t,padx:30,pady:30,radius:(top-left:20,top-right:5,bottom-right:5,bottom-left:20),dx:6,dy:6,shadow-fill:black.transparentize(95%),[
    #place(top+center,dy:-42*t.u,tape(t,width:100,height:25,fill:blue.transparentize(40%),angle:0))
    #heading(t,"quality","群聊质量锐评",gap:20)
    // 原 HTML 组件的开头空行也参与普通块排版，保留实际输出的段前高度。
    #v(25.6*t.u)
    #paper(t,padx:24,pady:24,radius:12,fill:yellow,stroke:2,color:muted,dashed:true,shadow-fill:muted,[
      #place(top+center,dy:-36*t.u,tape(t,width:100,height:30,fill:white.transparentize(40%),masked:true,outlined:true))
      #grid(columns:(1fr,auto),gutter:15*t.u,align:horizon,
        rotate(-2deg,box(inset:(x:18*t.u,y:8*t.u),fill:orange,stroke:2*t.u+ink,radius:6*t.u)[#copy(t,r.title,size:25.6,weight:700,fill:white,font:"title")]),
        rotate(-2deg,box(inset:(x:17*t.u,y:6*t.u),fill:pink,stroke:2*t.u+muted,radius:8*t.u)[#copy(t,r.subtitle,size:24,fill:rgb("bf360c"),font:"title")]))
      #v(10*t.u)#rule(t,paint:muted)#v(25*t.u)
      #block(width:100%,inset:2*t.u,stroke:2*t.u+muted,outset:-1*t.u,radius:12*t.u,fill:white,clip:true)[
        #let active=r.dimensions.enumerate().filter(((i,x))=>x.percentage>0)
        #let total=calc.max(100,r.dimensions.map(x=>x.percentage).sum(default:0))
        #grid(columns:active.map(((i,x))=>x.percentage/total*100%),gutter:0pt,..active.map(((i,x))=>block(width:100%,height:35*t.u,inset:(x:4*t.u),fill:colors.at(calc.rem(i,8)),stroke:(right:1*t.u+black.transparentize(85%)),clip:true)[
          #align(center+horizon,copy(t,x.name,size:13.6,weight:700,fill:white))
        ]))
        #if active.len()==0 {v(35*t.u)}
      ]
      #v(25*t.u)
      #block(width:100%,inset:(x:5*t.u))[
        #grid(columns:(1fr,1fr),gutter:15*t.u,..r.dimensions.enumerate().filter(((i,x))=>x.percentage>0).map(((i,x))=>paper(t,padx:14,pady:12,radius:6,fill:rgb("fffaf0"),stroke:2,color:colors.at(calc.rem(i,8)),dashed:true,dx:2,dy:2,shadow-fill:black.transparentize(94%),angle:(-1,1.5,-.5,1,-1.5,.5).at(calc.rem(i,6)),[
          #place(top+center,dy:-22*t.u,tape(t,width:30,height:14,fill:white.transparentize(50%),angle:(2,-1,3,-2,1,-3).at(calc.rem(i,6))))
          #let color=colors.at(calc.rem(i,8))
          #copy(t,x.name,size:14.08,weight:700,fill:color,lh:1.5)#v(2*t.u)#rule(t,paint:color)#v(2*t.u)
          #let tenth=calc.round(x.percentage*10)
          #copy(t,str(calc.quo(tenth,10))+"."+str(calc.rem(tenth,10))+"%",size:12.1088,weight:700,fill:color,lh:1.5)#v(8*t.u)
          #copy(t,runs(t,x.comment),size:14.08,fill:rgb("444444"),lh:1.5)
        ])))
      ]
      #v(25*t.u)
      #grid(columns:(110*t.u,1fr),gutter:20*t.u,align:top,box(width:110*t.u,height:110*t.u,radius:50%,stroke:3*t.u+muted,outset:-1.5*t.u,inset:3*t.u,clip:true)[#if d.decorations.at(0,default:"")!="" {box(width:100%,height:100%,radius:50%,clip:true)[#image(d.decorations.at(0),width:100%,height:100%,fit:"cover")]}else{align(center+horizon,icon(t,"user",size:48,color:muted))}],layout(size=>{
        let body=block(width:size.width,inset:(x:31*t.u,y:25*t.u))[#copy(t,runs(t,r.summary),size:19.2,weight:400,lh:1.8)]
        let m=measure(body);let w=m.width/t.u;let h=calc.max(80,m.height/t.u)
        let f=calc.min(1,w/270,h/270);let a=255*f;let b=15*f;let c=225*f
        let path="M"+str(a)+" 1.5H"+str(w - b)+"A"+str(b)+" "+str(c)+" 0 0 1 "+str(w - 1.5)+" "+str(c)+"V"+str(h - b)+"A"+str(c)+" "+str(b)+" 0 0 1 "+str(w - c)+" "+str(h - 1.5)+"H"+str(b)+"A"+str(b)+" "+str(a)+" 0 0 1 1.5 "+str(h - a)+"V"+str(b)+"A"+str(a)+" "+str(b)+" 0 0 1 "+str(a)+" 1.5Z"
        let svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+str(w)+"' height='"+str(h)+"'><path d='"+path+"' fill='#fcfcfc' stroke='#8d6e63' stroke-width='3'/></svg>"
        block(width:size.width,height:h*t.u)[
          #place(top+left,dx:4*t.u,dy:4*t.u,image(bytes(svg.replace("#fcfcfc","#00000026").replace("#8d6e63","#00000026")),format:"svg",width:100%,height:100%))
          #place(top+left,image(bytes(svg),format:"svg",width:100%,height:100%))
          #place(top+left,dx:-14*t.u,dy:30*t.u,polygon((0pt,14*t.u),(14*t.u,0pt),(14*t.u,28*t.u),fill:muted,stroke:none))
          #place(top+left,dx:-8*t.u,dy:30*t.u,polygon((0pt,14*t.u),(14*t.u,0pt),(14*t.u,28*t.u),fill:rgb("fcfcfc"),stroke:none))
          #body
        ]
      }))
    ])
    #v(25*t.u)
  ])
}
#let footer(t,d) = context {
  let cells=(("star","Irotoridori no Sekai",rgb("ff9800"),rgb("ffb74d"),rgb("fffdf0"),-1,[
    #copy(t,d.generated_at,size:15.2,fill:rgb("666666"),font:"hand",lh:1.4)
    #copy(t,"AstrBot 群分析总结插件",size:12.92,fill:rgb("666666").transparentize(30%),font:"hand",lh:1.4)
  ]),("github","Github Repo",rgb("2196f3"),rgb("64b5f6"),rgb("f0f7ff"),1.5,[
    #copy(t,"SXP-Simon/astrbot_plugin_qq_group_daily_analysis".clusters().join(sym.zws),size:12.8,fill:rgb("666666"),lh:1.4)
  ]),("tokens","LLM Token 消耗",rgb("673ab7"),rgb("9575cd"),rgb("f5f0ff"),-.5,[
    #copy(t,[Total: #d.tokens.at(0) Tokens],size:15.2,fill:rgb("666666"),font:"hand",lh:1.4)
    #copy(t,[Prompt/Compl: #d.tokens.at(1)/#d.tokens.at(2)],size:15.2,fill:rgb("666666"),font:"hand",lh:1.4)
  ]))
  let bodies=cells.map(c=>align(center)[
    #grid(columns:(auto,auto),gutter:8*t.u,align:horizon,icon(t,c.at(0),size:18.4,color:c.at(2)),copy(t,c.at(1),size:18.4,weight:700,font:"hand"))
    #v(5*t.u)#c.at(6)
  ])
  let height=calc.max(..bodies.map(body=>measure(body,width:207.333*t.u).height/t.u+34))
  paper(t,padx:25,pady:35,radius:15,stroke:2,color:rgb("eeeeee"),dashed:true,fill:black.transparentize(98%),dx:0,dy:0,shadow-fill:none,[
    #grid(columns:(1fr,)*3,gutter:20*t.u,..bodies.enumerate().map(((i,body))=>paper(t,padx:15,pady:15,radius:0,height:height,fill:cells.at(i).at(4),color:cells.at(i).at(3),angle:cells.at(i).at(5),dx:4,dy:4,shadow-fill:black.transparentize(92%),[
      #place(top+center,dy:-27*t.u,tape(t,width:60,height:20,fill:cells.at(i).at(3).transparentize(60%),angle:0))
      #body
    ])))
  ])
}
#let render(d) = {
  let u=.5pt
  let body=if d.font_language=="zh-Hant" {("Noto Sans TC","Noto Sans SC","Noto Color Emoji")}else{("Noto Sans SC","Noto Sans TC","Noto Color Emoji")}
  let t=(u:u,body:body,hand:("Patrick Hand","KaiTi","STKaiti","LXGW WenKai",..body))
  set page(width:940*u,height:auto,margin:0pt,fill:bg)
  set text(font:body,size:16*u,fill:ink,lang:"zh",region:if d.font_language=="zh-Hant" {"TW"}else{"CN"},cjk-latin-spacing:none,overhang:false)
  set par(leading:0pt,spacing:0pt)
  let dots=tiling(size:(20*u,20*u))[#place(top+left,dx:8*u,dy:8*u,circle(radius:2*u,fill:rgb("dddddd"),stroke:none))]
  set page(background:layout(size=>box(width:size.width,height:size.height)[
    #place(top+left,rect(width:size.width,height:size.height,fill:dots,stroke:none))
    #place(top+left,dx:20*u,dy:40*u,shadow(t,block(width:900*u,height:size.height - 80*u),radius:20,blur:40,dy:20,color:black.transparentize(90%)))
    #place(top+left,dx:36*u,dy:56*u,rect(width:900*u,height:size.height - 80*u,radius:20*u,fill:pink,stroke:none))
    #place(top+left,dx:28*u,dy:48*u,rect(width:900*u,height:size.height - 80*u,radius:20*u,fill:blue,stroke:none))
    #place(top+left,dx:20*u,dy:40*u,block(width:900*u,height:size.height - 80*u,radius:20*u,fill:white,stroke:2*u+ink,outset:-1*u)[
      #place(top+left,dx:14*u,dy:14*u,rect(width:872*u,height:size.height - 108*u,radius:15*u,fill:none,stroke:(paint:muted.transparentize(50%),thickness:2*u,dash:(array:(6*u,6*u)))))
    ])
  ]))
  block(width:940*u,inset:(x:62*u,y:82*u))[
    #header(t,d)#statistics(t,d)#activity(t,d)
    // 原组件开头的 BOM 在 CSS 网格中占一行，保留同数据 HTML 的模块间距。
    #if d.topics.len()>0 {v((30+25.6+30)*u);topics(t,d)}
    #if d.portraits.len()>0 {v((30+25.6+30+20)*u);portraits(t,d)}
    #if d.quotes.len()>0 {v((30+25.6+30+20)*u);quotes(t,d)}
    #if d.review!=none {v((30+40)*u);quality(t,d)}
    #v(50*u)#footer(t,d)
  ]
  context [#metadata((height:here().position().y/1pt))<report-size>]
}

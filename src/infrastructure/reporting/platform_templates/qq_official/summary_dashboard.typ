#let d = json("data.json")
#let u = .5pt
#set page(width:940*u,height:423*u,margin:0pt,fill:none)
#set text(font:("Noto Sans SC","Noto Sans CJK SC"),fill:black)
#set par(spacing:0pt)
#place(top+left,dx:26*u,dy:21*u)[
  #block(width:888*u)[
    #grid(columns:(1fr,auto),column-gutter:16*u,
      text(size:29*u,weight:"bold")[群聊日常分析],
      text(size:20*u,weight:"bold",d.date))
  ]
]
#place(top+left,dx:26*u,dy:70*u)[
  #block(width:888*u,height:92*u,stroke:(top:.6pt,bottom:.6pt))[
    #grid(columns:(1fr,)*5,..d.metrics.enumerate().map(pair => {
      let (i,m) = pair
      block(width:100%,height:70*u,inset:8*u,stroke:(left:if i>0 {.5pt}else{none}))[
        #align(center)[
          #text(size:33*u,weight:"bold",m.value)
          #linebreak()
          #text(size:16*u,weight:"bold",m.label)
        ]
      ]
    }))
  ]
]
#place(top+left,dx:26*u,dy:170*u)[
  #block(width:888*u)[
    #grid(columns:(1fr,)*24,column-gutter:6*u,..d.chart.map(item => [
      #stack(dir:ttb,spacing:4*u,
        block(width:100%,height:211*u,stroke:(bottom:.5pt))[
          #align(bottom+center)[#rect(width:18*u,height:item.height*2.11*u,fill:black,stroke:none,radius:(top:3*u))]
        ],
        align(center,text(size:14*u,weight:"bold",item.hour)))
    ]))
  ]
]
#metadata((height:423*u/1pt))<report-size>

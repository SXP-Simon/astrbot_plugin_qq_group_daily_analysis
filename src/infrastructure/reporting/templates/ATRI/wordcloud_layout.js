(() => {
  'use strict';
  const root = document.documentElement;
  const payload = JSON.parse(document.getElementById('wordcloud-data').textContent);
  const options = payload.options;
  const words = payload.words;
  const region = document.getElementById('wc-region');
  const svg = document.getElementById('wc-svg');
  const empty = document.getElementById('wc-empty');
  const family = '"WordCloud Font"';
  let finished = false;

  function finish(state, shown, error = '') {
    if (finished) return;
    finished = true;
    root.dataset.t2iState = state;
    root.dataset.layoutState = state;
    root.dataset.t2iError = error;
    root.dataset.wordcloudShown = String(shown);
    root.dataset.wordcloudTotal = String(words.length);
    if (state === 'ready') {
      root.dataset.t2iReady = 'true';
      window.__ATRI_T2I_READY__ = true;
    } else {
      empty.hidden = false;
      empty.textContent = error;
    }
    if (window.parent !== window) {
      window.parent.postMessage({type:'wordcloud-render-state',state,shown,total:words.length,error}, '*');
    }
  }

  const timeout = setTimeout(() => finish('error', 0, '词云资源加载超时，请检查模板 CDN；字体也可改为上传字体'), 4000);

  async function initialize() {
    // 只有真实字体加载成功后才测量字形；禁止加载失败时悄悄截图回退字体。
    let font;
    if (payload.font_uri) {
      font = new FontFace('WordCloud Font', `url("${payload.font_uri}")`, {weight:'400'});
      try {
        await font.load();
      } catch {
        throw new Error('词云字体加载失败，请检查模板 CDN 或重新上传有效字体');
      }
      document.fonts.add(font);
    } else {
      // 系统字体没有延迟下载；字体选项名称明确保留“系统”语义。
      const system = options.font === 'serif'
        ? '"Noto Serif CJK SC","SimSun","Songti SC",serif'
        : '"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",sans-serif';
      document.body.style.setProperty('--cloud-font', system);
      payload.system_family = system;
      await document.fonts.load(`34px ${system}`, words.map(word => word.text).join(''));
    }
    await Promise.all(Array.from(region.querySelectorAll('.portrait')).map(async (picture, index) => {
      try {
        await picture.decode();
      } catch {
        throw new Error(`立绘 ${index + 1} 加载失败，请检查模板 CDN 或图片资源`);
      }
      if (!picture.naturalWidth || !picture.naturalHeight) throw new Error(`立绘 ${index + 1} 加载失败`);
    }));
    await document.fonts.ready;
    if (font && font.status !== 'loaded') throw new Error('词云字体加载失败');
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (finished) return;
    const shown = layout();
    // 完成 DOM 布局与绘制帧后才允许 T2I 截图。
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    clearTimeout(timeout);
    finish('ready', shown);
  }

  function layout() {
    const width = region.clientWidth;
    const height = region.clientHeight;
    if (!width || !height) throw new Error('词云画布尺寸无效');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (!words.length) {
      empty.hidden = false;
      empty.textContent = '没有可展示的词语，请调整过滤设置。';
      document.getElementById('wc-shown').textContent = '展示 0 个词';
      return 0;
    }
    const context = document.createElement('canvas').getContext('2d');
    if (!context) throw new Error('浏览器无法测量词云字体');
    const fontFamily = payload.system_family || family;
    const metric = options.weight_mode;
    const minWeight = Math.sqrt(words[words.length - 1][metric]);
    const maxWeight = Math.sqrt(words[0][metric]);
    const palette = options.palette.length ? options.palette : ['#315d78','#46748d','#a45f7c','#726293'];
    const gap = Math.max(1, options.word_spacing);
    const padding = 22;
    const topPadding = 55;
    const origin = svg.getBoundingClientRect();
    const reserved = Array.from(region.querySelectorAll('.portrait,#wc-paper-kicker,#wc-signature')).map(node => {
      const rect = node.getBoundingClientRect();
      return {left:rect.left-origin.left-3,right:rect.right-origin.left+3,top:rect.top-origin.top-3,bottom:rect.bottom-origin.top+3};
    });

    // 二像素候选网格与积分占位图：保持密集排版，同时让碰撞查询不随已放置词数增长。
    const cell = 2;
    const columns = Math.ceil(width / cell);
    const rows = Math.ceil(height / cell);
    const stride = columns + 1;
    const occupied = new Uint8Array(columns * rows);
    const integral = new Uint32Array(stride * (rows + 1));
    const bounds = box => ({
      x0:Math.max(0,Math.floor(box.left/cell)), y0:Math.max(0,Math.floor(box.top/cell)),
      x1:Math.min(columns,Math.ceil(box.right/cell)), y1:Math.min(rows,Math.ceil(box.bottom/cell))
    });
    function occupy(box) {
      const {x0,y0,x1,y1} = bounds(box);
      for (let y = y0; y < y1; y++) occupied.fill(1, y*columns+x0, y*columns+x1);
    }
    function rebuild() {
      for (let y = 1; y <= rows; y++) {
        let sum = 0;
        for (let x = 1; x <= columns; x++) {
          sum += occupied[(y-1)*columns+x-1];
          integral[y*stride+x] = integral[(y-1)*stride+x] + sum;
        }
      }
    }
    function collides(left,top,right,bottom) {
      const x0=Math.floor(left/cell), y0=Math.floor(top/cell);
      const x1=Math.ceil(right/cell), y1=Math.ceil(bottom/cell);
      return integral[y1*stride+x1] - integral[y0*stride+x1] - integral[y1*stride+x0] + integral[y0*stride+x0] > 0;
    }
    reserved.forEach(occupy);
    rebuild();
    const candidates = [];
    const centerX = width / 2;
    const centerY = height * .44;
    for (let y = topPadding; y < height-padding; y += cell) {
      for (let x = padding; x < width-padding; x += cell) {
        const dx = (x-centerX)/1.35;
        const dy = (y-centerY)/.85;
        candidates.push({x,y,index:Math.floor(y/cell)*columns+Math.floor(x/cell),score:dx*dx+dy*dy+Math.sin(x*.13+y*.11)*18});
      }
    }
    candidates.sort((a,b) => a.score-b.score);
    context.textAlign = 'left';
    context.textBaseline = 'alphabetic';
    const fragment = document.createDocumentFragment();
    let shown = 0;
    words.forEach((word,index) => {
      const weight = maxWeight === minWeight ? .5 : (Math.sqrt(word[metric])-minWeight)/(maxWeight-minWeight);
      const preferred = options.min_font_size+(options.max_font_size-options.min_font_size)*weight;
      const rotation = options.rotation === 'mixed' && index > 2 && index % 5 === 0 ? 90 : 0;
      let found = null;
      for (let pass = 0; pass < 2 && !found; pass++) {
        const size = pass === 0 ? preferred : Math.max(options.min_font_size,preferred*.82);
        context.font = `400 ${size}px ${fontFamily}`;
        const ink = context.measureText(word.text);
        const inkWidth = ink.actualBoundingBoxLeft+ink.actualBoundingBoxRight;
        const inkHeight = ink.actualBoundingBoxAscent+ink.actualBoundingBoxDescent;
        const boxWidth = (rotation ? inkHeight : inkWidth)+gap;
        const boxHeight = (rotation ? inkWidth : inkHeight)+gap;
        for (const {x,y,index:candidateIndex} of candidates) {
          if (occupied[candidateIndex]) continue;
          const left=x-boxWidth/2, right=x+boxWidth/2, top=y-boxHeight/2, bottom=y+boxHeight/2;
          if (left<padding || top<topPadding || right>width-padding || bottom>height-padding || collides(left,top,right,bottom)) continue;
          const box = {left,right,top,bottom};
          found = {x,y,size,box,offsetX:(ink.actualBoundingBoxLeft-ink.actualBoundingBoxRight)/2,offsetY:(ink.actualBoundingBoxAscent-ink.actualBoundingBoxDescent)/2};
          break;
        }
      }
      if (!found) return;
      occupy(found.box);
      rebuild();
      const text = document.createElementNS('http://www.w3.org/2000/svg','text');
      text.setAttribute('transform', `translate(${found.x} ${found.y}) rotate(${rotation})`);
      text.setAttribute('text-anchor','start');
      text.setAttribute('dominant-baseline','alphabetic');
      text.setAttribute('x',String(found.offsetX));
      text.setAttribute('y',String(found.offsetY));
      text.setAttribute('font-size',String(found.size));
      text.setAttribute('font-family',fontFamily);
      text.setAttribute('font-weight','400');
      text.setAttribute('fill',palette[index%palette.length]);
      text.setAttribute('data-word',word.text);
      text.setAttribute('data-box',JSON.stringify(found.box));
      text.textContent = word.text;
      fragment.appendChild(text);
      shown++;
    });
    svg.appendChild(fragment);
    svg.setAttribute('aria-label', `群聊热词，展示 ${shown} 个词`);
    document.getElementById('wc-shown').textContent = `展示 ${shown} / ${words.length} 个词`;
    return shown;
  }

  initialize().catch(error => {
    clearTimeout(timeout);
    finish('error', 0, error instanceof Error ? error.message : '词云排版失败');
  });
})();

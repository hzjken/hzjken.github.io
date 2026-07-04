/*
  <world-globe> — a dependency-free interactive dotted globe web component.
  Drop this file into any site and use:

    <script src="globe.js"></script>
    <world-globe theme="dark" style="width:100%;height:360px;display:block"></world-globe>

  Attributes:
    theme   "light" | "dark"   (default "dark")
    network "on" | "off"       (default "on")  — draws the path between cities

  Configure cities/path in JS (optional):
    const g = document.querySelector('world-globe');
    g.cities = [
      { name:'SINGAPORE', lon:103.82, lat:1.35, tier:'primary'  },
      { name:'SHANGHAI',  lon:121.47, lat:31.23, tier:'secondary' },
      { name:'SHENZHEN',  lon:114.06, lat:22.54, tier:'secondary' },
    ];
    g.path = [2,1,0];   // indices into cities: Shenzhen -> Shanghai -> Singapore
    g.refresh();

  Drag to rotate. No external libraries, no build step.
*/
(function () {
  const DEG = Math.PI / 180;

  const POLYS = {
    NAmerica:[[-168,65],[-165,60],[-153,58],[-135,58],[-130,54],[-124,48],[-124,40],[-117,33],[-110,23],[-105,22],[-97,16],[-88,15],[-83,9],[-81,20],[-80,31],[-75,35],[-70,42],[-64,46],[-60,50],[-70,58],[-80,62],[-95,60],[-95,68],[-110,68],[-125,70],[-140,70],[-156,71],[-168,65]],
    Greenland:[[-45,60],[-20,70],[-22,80],[-45,83],[-58,76],[-55,68],[-45,60]],
    SAmerica:[[-80,9],[-77,2],[-81,-5],[-72,-17],[-70,-24],[-73,-38],[-75,-48],[-68,-55],[-63,-51],[-58,-40],[-48,-25],[-40,-22],[-35,-8],[-48,-1],[-60,5],[-72,11],[-80,9]],
    Africa:[[-17,15],[-16,22],[-8,32],[0,36],[11,37],[24,32],[33,31],[43,12],[51,12],[42,-2],[40,-15],[32,-26],[20,-35],[16,-29],[12,-17],[9,0],[-8,5],[-17,15]],
    Europe:[[-10,36],[-9,44],[-2,49],[2,51],[-4,58],[5,62],[12,66],[24,66],[30,60],[28,46],[22,41],[13,40],[3,43],[-10,36]],
    Asia:[[30,60],[38,66],[55,70],[75,73],[100,76],[130,73],[150,70],[165,68],[180,66],[180,60],[162,60],[150,52],[140,45],[131,43],[127,40],[122,31],[120,27],[117,24],[113,22],[110,21],[108,21],[106,10],[100,6],[95,8],[92,22],[88,22],[80,8],[77,8],[70,22],[60,25],[52,27],[45,38],[38,45],[33,50],[30,60]],
    India:[[70,22],[73,18],[77,8],[80,13],[85,20],[88,22],[80,25],[74,24],[70,22]],
    Sumatra:[[95,6],[104,-5],[114,-8],[106,-2],[98,4],[95,6]],
    Borneo:[[109,7],[118,6],[117,-4],[110,-3],[109,7]],
    Australia:[[113,-22],[123,-17],[132,-12],[142,-11],[146,-18],[151,-24],[153,-32],[149,-38],[141,-38],[132,-32],[121,-34],[114,-28],[113,-22]],
    Japan:[[130,31],[138,35],[142,40],[141,45],[135,41],[132,34],[130,31]],
    Taiwan:[[119.9,21.9],[120.4,25.4],[122.1,25.6],[122.6,23.6],[121.6,21.8],[119.9,21.9]],
    UK:[[-6,50],[-2,54],[-2,58],[-7,58],[-8,53],[-6,50]],
    NZ:[[166,-46],[172,-41],[178,-38],[174,-44],[168,-47],[166,-46]],
    Madagascar:[[43,-13],[50,-16],[50,-25],[45,-25],[43,-13]]
  };

  function inPoly(x, y, vs) { let inside = false; for (let i=0,j=vs.length-1;i<vs.length;j=i++){const xi=vs[i][0],yi=vs[i][1],xj=vs[j][0],yj=vs[j][1];const hit=((yi>y)!=(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi);if(hit)inside=!inside;}return inside; }
  function isLand(lon, lat) { for (const k in POLYS) if (inPoly(lon, lat, POLYS[k])) return true; return false; }
  function buildPoints(step) { const p=[]; for (let lat=80;lat>=-58;lat-=step) for (let lon=-180;lon<=180;lon+=step) if (isLand(lon,lat)) p.push([lon,lat]); return p; }
  function baseVec(lon, lat) { const la=lat*DEG, lo=lon*DEG; return [Math.cos(la)*Math.sin(lo), Math.sin(la), Math.cos(la)*Math.cos(lo)]; }

  class WorldGlobe extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      this.cities = this.cities || [
        { name:'SINGAPORE', lon:103.82, lat:1.35, co:'1.35°N 103.82°E', tier:'primary' },
        { name:'SHANGHAI',  lon:121.47, lat:31.23, co:'31.23°N 121.47°E', tier:'secondary' },
        { name:'SHENZHEN',  lon:114.06, lat:22.54, co:'22.54°N 114.06°E', tier:'secondary' }
      ];
      this.path = this.path || [2, 1, 0];
      this.style.display = this.style.display || 'block';
      this.canvas = document.createElement('canvas');
      this.canvas.style.cssText = 'width:100%;height:100%;display:block;cursor:default';
      this.appendChild(this.canvas);
      this.pts = buildPoints(1.8);
      this._rotY = -this.cities[0].lon*DEG - 0.12;
      this._tilt = 0.1;
      this._bindDrag();
      this._ro = new ResizeObserver(() => this._resize());
      this._ro.observe(this);
      this._resize();
      this._t0 = performance.now();
      const loop = () => { this._draw(); this._raf = requestAnimationFrame(loop); };
      loop();
    }
    disconnectedCallback() { if (this._raf) cancelAnimationFrame(this._raf); if (this._ro) this._ro.disconnect(); }
    refresh() { this._resize(); }

    _resize() {
      const dpr = Math.min(window.devicePixelRatio||1, 2);
      const w = this.clientWidth||740, h = this.clientHeight||360;
      this.canvas.width = Math.round(w*dpr); this.canvas.height = Math.round(h*dpr);
      this._dpr = dpr;
    }
    _hit(clientX, clientY) {
      const cv = this.canvas, rect = cv.getBoundingClientRect();
      if (!rect.width) return false;
      const sx = (clientX-rect.left)*(cv.width/rect.width), sy = (clientY-rect.top)*(cv.height/rect.height);
      const dx = sx-this._cx, dy = sy-this._cy;
      return dx*dx + dy*dy <= this._R*this._R*1.12;
    }
    _bindDrag() {
      const cv = this.canvas;
      const down = e => { const p=e.touches?e.touches[0]:e; if(!this._hit(p.clientX,p.clientY))return; this._drag=true; cv.style.cursor='grabbing'; this._lx=p.clientX; this._ly=p.clientY; if(cv.setPointerCapture&&e.pointerId!=null){try{cv.setPointerCapture(e.pointerId);}catch(_){}} };
      const move = e => { const p=e.touches?e.touches[0]:e; if(!this._drag){ if(e.pointerType!=='touch') cv.style.cursor=this._hit(p.clientX,p.clientY)?'grab':'default'; return; } const dx=p.clientX-this._lx, dy=p.clientY-this._ly; this._lx=p.clientX; this._ly=p.clientY; this._rotY+=dx*0.006; this._tilt+=dy*0.006; if(this._tilt>1.3)this._tilt=1.3; if(this._tilt<-1.3)this._tilt=-1.3; if(e.cancelable)e.preventDefault(); };
      const up = () => { this._drag=false; cv.style.cursor='default'; };
      cv.addEventListener('pointerdown', down); window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
      cv.addEventListener('touchstart', down, {passive:true}); cv.addEventListener('touchmove', move, {passive:false}); cv.addEventListener('touchend', up);
    }
    _projVec(v) {
      const ct=Math.cos(this._tilt), st=Math.sin(this._tilt), ca=Math.cos(this._rotY), sa=Math.sin(this._rotY);
      const x1=v[0]*ca+v[2]*sa, z1=-v[0]*sa+v[2]*ca, y1=v[1];
      const y2=y1*ct-z1*st, z2=y1*st+z1*ct;
      return [this._cx + x1*this._R, this._cy - y2*this._R, z2];
    }
    _proj(lon, lat) { return this._projVec(baseVec(lon, lat)); }

    _draw() {
      const cv = this.canvas, ctx = cv.getContext('2d'), W = cv.width, H = cv.height, dpr = this._dpr;
      const dark = (this.getAttribute('theme')||'dark') !== 'light';
      const network = (this.getAttribute('network')||'on') !== 'off';
      this._cx = W*0.44; this._cy = H*0.45; this._R = Math.min(W*0.42, H*0.44);
      const cx=this._cx, cy=this._cy, R=this._R;
      const accentP = dark ? '#8ab4ff' : '#2563eb', accentS = dark ? '#6f8fc4' : '#7096d8';
      const t = (performance.now()-this._t0)/1000;
      ctx.clearRect(0,0,W,H);
      // sphere
      ctx.fillStyle = dark?'rgba(30,50,90,0.16)':'rgba(37,99,235,0.05)'; ctx.beginPath(); ctx.arc(cx,cy,R,0,6.2832); ctx.fill();
      ctx.strokeStyle = dark?'rgba(120,150,210,0.16)':'rgba(37,99,235,0.14)'; ctx.lineWidth=1*dpr; ctx.beginPath(); ctx.arc(cx,cy,R,0,6.2832); ctx.stroke();
      // land dots
      for (let i=0;i<this.pts.length;i++){ const p=this._proj(this.pts[i][0],this.pts[i][1]); if(p[2]<=0)continue; const a=(dark?0.20:0.18)+p[2]*(dark?0.48:0.42); ctx.fillStyle=(dark?'rgba(130,165,230,':'rgba(37,99,235,')+a.toFixed(2)+')'; ctx.beginPath(); ctx.arc(p[0],p[1],(0.8+p[2]*1.05)*dpr,0,6.2832); ctx.fill(); }
      // network path
      if (network && this.path.length>1) for (let k=0;k<this.path.length-1;k++) this._arc(ctx, this.cities[this.path[k]], this.cities[this.path[k+1]], t, k, dark, accentP, dpr, W);
      // markers (secondary first, primary last)
      const order = this.cities.map((c,i)=>i).sort((a,b)=> (this.cities[a].tier==='primary'?1:0)-(this.cities[b].tier==='primary'?1:0));
      order.forEach(i => this._marker(ctx, this.cities[i], t, dark, accentP, accentS, dpr, W));
      // hint
      ctx.font=(9.5*dpr)+"px 'IBM Plex Mono', ui-monospace, monospace"; ctx.textBaseline='alphabetic'; ctx.textAlign='left';
      ctx.fillStyle=dark?'rgba(140,166,200,0.6)':'rgba(122,134,156,0.7)'; ctx.fillText('⟲ DRAG TO ROTATE', cx-R, cy+R+16*dpr);
    }
    _marker(ctx, city, t, dark, accentP, accentS, dpr, W) {
      const sp=this._proj(city.lon,city.lat); if(sp[2]<=0)return;
      const primary=city.tier==='primary', col=primary?accentP:accentS, rad=(primary?4.2:2.5)*dpr, ph=(t%2)/2;
      ctx.strokeStyle=col; ctx.globalAlpha=(1-ph)*(primary?0.7:0.4); ctx.lineWidth=(primary?1.6:1.1)*dpr; ctx.beginPath(); ctx.arc(sp[0],sp[1],rad+ph*(primary?18:10)*dpr,0,6.2832); ctx.stroke();
      if(primary){ const ph2=((t+1)%2)/2; ctx.globalAlpha=(1-ph2)*0.5; ctx.beginPath(); ctx.arc(sp[0],sp[1],rad+ph2*18*dpr,0,6.2832); ctx.stroke(); }
      ctx.globalAlpha=1;
      if(primary){ ctx.fillStyle=col; ctx.shadowColor=col; ctx.shadowBlur=12*dpr; ctx.beginPath(); ctx.arc(sp[0],sp[1],rad,0,6.2832); ctx.fill(); ctx.shadowBlur=0; ctx.strokeStyle=dark?'rgba(255,255,255,0.65)':'rgba(255,255,255,0.95)'; ctx.lineWidth=1.2*dpr; ctx.beginPath(); ctx.arc(sp[0],sp[1],rad,0,6.2832); ctx.stroke(); }
      else { ctx.fillStyle=col; ctx.beginPath(); ctx.arc(sp[0],sp[1],rad,0,6.2832); ctx.fill(); }
      ctx.font=((primary?11:9.8)*dpr)+"px 'IBM Plex Mono', ui-monospace, monospace"; ctx.textBaseline='middle';
      const wname=ctx.measureText(city.name).width, wco=city.co?ctx.measureText(city.co).width:0, wMax=Math.max(wname,wco);
      const flip = sp[0]+10*dpr+wMax > W-8*dpr; ctx.textAlign=flip?'right':'left';
      const lx = flip? sp[0]-10*dpr : sp[0]+10*dpr;
      ctx.fillStyle = primary?(dark?'#dbe6fb':'#1e2a44'):(dark?'#93a6c6':'#5f6f8c'); ctx.fillText(city.name, lx, sp[1]+(primary&&city.co?-2*dpr:0));
      if(primary&&city.co){ ctx.fillStyle=dark?'#8fa6c8':'#7a869c'; ctx.font=(9.8*dpr)+"px 'IBM Plex Mono', ui-monospace, monospace"; ctx.fillText(city.co, lx, sp[1]+11*dpr); }
      ctx.textAlign='left';
    }
    _arc(ctx, a, b, t, order, dark, accentP, dpr) {
      const va=baseVec(a.lon,a.lat), vb=baseVec(b.lon,b.lat);
      let dot=va[0]*vb[0]+va[1]*vb[1]+va[2]*vb[2]; dot=Math.max(-1,Math.min(1,dot));
      const ang=Math.acos(dot), n=48, so=Math.sin(ang)||1, pathPts=[];
      for(let i=0;i<=n;i++){ const f=i/n, s1=Math.sin((1-f)*ang)/so, s2=Math.sin(f*ang)/so; const x=s1*va[0]+s2*vb[0], y=s1*va[1]+s2*vb[1], z=s1*va[2]+s2*vb[2], lift=1+0.16*Math.sin(Math.PI*f); pathPts.push(this._projVec([x*lift,y*lift,z*lift])); }
      ctx.lineWidth=1.4*dpr; ctx.strokeStyle=dark?'rgba(138,180,255,0.5)':'rgba(37,99,235,0.45)';
      for(let i=0;i<n;i++){ const p=pathPts[i], q=pathPts[i+1]; if(p[2]>0&&q[2]>0){ ctx.beginPath(); ctx.moveTo(p[0],p[1]); ctx.lineTo(q[0],q[1]); ctx.stroke(); } }
      const prog=((t*0.4+order*0.5)%1), idx=Math.min(n,Math.floor(prog*n)), pp=pathPts[idx];
      if(pp&&pp[2]>0){ ctx.fillStyle=dark?'#bcd4ff':'#2563eb'; ctx.shadowColor=accentP; ctx.shadowBlur=10*dpr; ctx.beginPath(); ctx.arc(pp[0],pp[1],2.6*dpr,0,6.2832); ctx.fill(); ctx.shadowBlur=0; }
    }
  }
  if (!customElements.get('world-globe')) customElements.define('world-globe', WorldGlobe);
})();

// Generates the Stock app PNG icons with no external deps (uses node zlib).
// Draws a falabella-green icon with a barcode + magnifier "scan stock" motif.
const zlib = require('zlib');
const fs = require('fs');
const path = require('path');

function hex(h){ h=h.replace('#',''); return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]; }

function makeIcon(S){
  const buf = Buffer.alloc(S*S*4);
  const set=(x,y,[r,g,b],a=255)=>{
    x=Math.round(x); y=Math.round(y);
    if(x<0||y<0||x>=S||y>=S) return;
    const i=(y*S+x)*4;
    const ba=buf[i+3]/255, fa=a/255, oa=fa+ba*(1-fa);
    if(oa===0){buf[i]=buf[i+1]=buf[i+2]=buf[i+3]=0;return;}
    buf[i]  =Math.round((r*fa+buf[i]  *ba*(1-fa))/oa);
    buf[i+1]=Math.round((g*fa+buf[i+1]*ba*(1-fa))/oa);
    buf[i+2]=Math.round((b*fa+buf[i+2]*ba*(1-fa))/oa);
    buf[i+3]=Math.round(oa*255);
  };
  const fillRect=(x0,y0,w,h,c,a=255)=>{ for(let y=y0;y<y0+h;y++) for(let x=x0;x<x0+w;x++) set(x,y,c,a); };
  const disc=(cx,cy,r,c,a=255)=>{ for(let y=cy-r;y<=cy+r;y++) for(let x=cx-r;x<=cx+r;x++){ const d=Math.hypot(x-cx,y-cy); if(d<=r) set(x,y,c, d>r-1.5?a*(r-d)/1.5:a); } };
  const ring=(cx,cy,r,w,c,a=255)=>{ for(let y=cy-r-w;y<=cy+r+w;y++) for(let x=cx-r-w;x<=cx+r+w;x++){ const d=Math.hypot(x-cx,y-cy); if(d<=r+w/2&&d>=r-w/2){ const edge=Math.min(r+w/2-d,d-(r-w/2)); set(x,y,c, edge<1.5?a*edge/1.5:a);} } };
  const seg=(x1,y1,x2,y2,w,c,a=255)=>{ const minx=Math.min(x1,x2)-w,maxx=Math.max(x1,x2)+w,miny=Math.min(y1,y2)-w,maxy=Math.max(y1,y2)+w;
    for(let y=miny;y<=maxy;y++) for(let x=minx;x<=maxx;x++){ const dx=x2-x1,dy=y2-y1,L2=dx*dx+dy*dy; let t=L2?((x-x1)*dx+(y-y1)*dy)/L2:0; t=Math.max(0,Math.min(1,t)); const px=x1+t*dx,py=y1+t*dy,d=Math.hypot(x-px,y-py); if(d<=w/2) set(x,y,c, d>w/2-1.5?a*(w/2-d)/1.5:a);} };

  const GREEN=hex('#aad503'), DARK=hex('#20320a'), WHITE=hex('#ffffff');
  // background
  fillRect(0,0,S,S,GREEN);
  // subtle top glow
  for(let y=0;y<S;y++){ const a=Math.max(0,40-y*80/S); if(a>0) fillRect(0,y,S,1,WHITE,a); }
  // barcode bars (dark) inside a safe central band
  const bx=S*0.24, by=S*0.30, bw=S*0.52, bh=S*0.40;
  const widths=[3,1,2,4,1,2,1,3,2,1,4,1,2,3,1,2];
  let x=bx; const unit=bw/ widths.reduce((a,b)=>a+b,0)/1.0; const gap=unit*0.55;
  let total=widths.reduce((a,b)=>a+b+0,0);
  const step=bw/(total+ widths.length*0.6);
  x=bx;
  for(const wgt of widths){ const barW=step*wgt; fillRect(Math.round(x),Math.round(by),Math.max(2,Math.round(barW)),Math.round(bh),DARK); x+=barW+step*0.6; }
  // magnifier over lower-right of barcode
  const cx=S*0.66, cy=S*0.66, r=S*0.15, w=Math.max(4,S*0.045);
  disc(cx,cy,r+w/2, GREEN); // clear behind glass so it reads
  ring(cx,cy,r,w, WHITE);
  disc(cx,cy,r-w/2, WHITE, 60);
  seg(cx+r*0.72, cy+r*0.72, cx+r*1.5, cy+r*1.5, w*1.15, WHITE);
  return buf;
}

function encodePNG(S, rgba){
  const raw=Buffer.alloc((S*4+1)*S);
  for(let y=0;y<S;y++){ raw[y*(S*4+1)]=0; rgba.copy(raw, y*(S*4+1)+1, y*S*4, y*S*4+S*4); }
  const comp=zlib.deflateSync(raw,{level:9});
  const crcTable=(()=>{const t=[];for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;t[n]=c>>>0;}return t;})();
  const crc=b=>{let c=0xffffffff;for(const x of b)c=crcTable[(c^x)&0xff]^(c>>>8);return (c^0xffffffff)>>>0;};
  const chunk=(type,data)=>{ const len=Buffer.alloc(4); len.writeUInt32BE(data.length); const t=Buffer.from(type); const cd=Buffer.concat([t,data]); const cr=Buffer.alloc(4); cr.writeUInt32BE(crc(cd)); return Buffer.concat([len,cd,cr]); };
  const sig=Buffer.from([137,80,78,71,13,10,26,10]);
  const ihdr=Buffer.alloc(13); ihdr.writeUInt32BE(S,0); ihdr.writeUInt32BE(S,4); ihdr[8]=8; ihdr[9]=6; ihdr[10]=0; ihdr[11]=0; ihdr[12]=0;
  return Buffer.concat([sig, chunk('IHDR',ihdr), chunk('IDAT',comp), chunk('IEND',Buffer.alloc(0))]);
}

const outDir=path.join(__dirname,'..','stock','icons');
for(const S of [32,180,192,512]){
  const png=encodePNG(S, makeIcon(S));
  fs.writeFileSync(path.join(outDir,`icon-${S}.png`), png);
  console.log('wrote icon-'+S+'.png', png.length, 'bytes');
}

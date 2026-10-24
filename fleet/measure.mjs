const port = process.argv[2];
const t = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = t.find(x => x.type === "page") || t[0];
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id=0; const pend=new Map();
ws.addEventListener("message", e => { const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);} });
await new Promise(r=>ws.addEventListener("open",r));
const send=(m,pr={})=>{const i=++id;return new Promise(res=>{pend.set(i,res);ws.send(JSON.stringify({id:i,method:m,params:pr}))})};
await send("Page.navigate",{url:"about:blank"});
await new Promise(r=>setTimeout(r,600));
const expr = `(async () => {
  function h(s){let a=0xdeadbeef,b=0x41c6ce57;for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);a=Math.imul(a^c,2654435761);b=Math.imul(b^c,1597334677);}a=Math.imul(a^(a>>>16),2246822507)^Math.imul(b^(b>>>13),3266489909);b=Math.imul(b^(b>>>16),2246822507)^Math.imul(a^(a>>>13),3266489909);return (b>>>0).toString(16)+(a>>>0).toString(16);}
  const c=document.createElement("canvas");c.width=300;c.height=80;const x=c.getContext("2d");
  x.fillStyle="#f60";x.fillRect(0,0,300,80);x.fillStyle="#069";x.font="18px Arial";x.fillText("Fingerprint 中文 😀 éè",6,30);
  x.fillStyle="rgba(102,204,0,0.7)";x.font="16px Helvetica";x.fillText("abcdefghijklmnop",8,55);
  const g=document.createElement("canvas").getContext("webgl");const q=g.getExtension("WEBGL_debug_renderer_info");
  const ctx=new OfflineAudioContext(1,44100,44100);const osc=ctx.createOscillator();osc.type="triangle";osc.frequency.value=10000;
  const comp=ctx.createDynamicsCompressor();comp.threshold.value=-50;comp.knee.value=40;comp.ratio.value=12;
  osc.connect(comp);comp.connect(ctx.destination);osc.start(0);const buf=await ctx.startRendering();const d=buf.getChannelData(0);
  let sum=0;for(let i=4500;i<5000;i++)sum+=Math.abs(d[i]);
  const m=document.createElement("canvas").getContext("2d");
  const w=(f,t)=>{m.font='40px "'+f+'"';return +m.measureText(t).width.toFixed(2)};
  const tofu=w("NoSuchFontXYZ","\\uE000");
  const fonts={};
  for (const f of ["PingFang SC","Songti SC","Apple Color Emoji","Helvetica"]) fonts[f]=+(w(f,"\\u4F60\\u597D").toFixed(2)/2);
  return JSON.stringify({tz:Intl.DateTimeFormat().resolvedOptions().timeZone,lang:navigator.language,langs:navigator.languages,off:new Date().getTimezoneOffset(),hc:navigator.hardwareConcurrency,sw:screen.width,sh:screen.height,dpr:devicePixelRatio,gpu:q?g.getParameter(q.UNMASKED_RENDERER_WEBGL):null,shim:!!window.__donutNoise,canvas:h(c.toDataURL()),audio:+sum.toFixed(12),tofu,fonts});
})()`;
const r = await send("Runtime.evaluate",{expression:expr,awaitPromise:true,returnByValue:true});
console.log(r.result?.result?.value ?? JSON.stringify(r).slice(0,200)); ws.close();

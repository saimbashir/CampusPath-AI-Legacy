/* CampusPath AI · CP3D — a tiny real-time 3D renderer for the app's characters (v0.9.0).
   Characters are signed-distance-field models ray-marched on the GPU (WebGL 1):
   soft-vinyl bodies with smoothly blended arms and legs (they can never detach), real eyeballs
   that rotate to follow the 3D objects orbiting around them, painted expressions, accessories
   and props. One shared WebGL context in a worker renders each character, then sends a bitmap to its
   character's own <canvas>, so any number of characters can be on a page.
   No libraries, no network, CSP-safe. Falls back to a plain emoji if WebGL is unavailable. */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ shader */
  const VS = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}';
  const FS = `
precision highp float;
uniform vec2 uRes; uniform float uTime;
uniform vec3 uPos; uniform mat3 uRot;
uniform int uBody; uniform vec3 uBC; uniform vec3 uBR;
uniform vec3 uCol; uniform vec3 uFoot; uniform vec3 uIris; uniform vec3 uAccA; uniform vec3 uAccB;
uniform vec3 uSL; uniform vec3 uSR; uniform vec3 uEL; uniform vec3 uER; uniform vec3 uHL; uniform vec3 uHR;
uniform vec3 uHipL; uniform vec3 uHipR; uniform vec3 uKL; uniform vec3 uKR; uniform vec3 uFL; uniform vec3 uFR;
uniform vec3 uEyeL; uniform vec3 uEyeR; uniform float uEyeRad; uniform vec3 uLook; uniform vec3 uLid;
uniform int uEyeStyle; uniform int uMouth; uniform int uBrow; uniform float uTalk; uniform float uBlush; uniform float uTears;
uniform vec3 uFace; uniform vec3 uTop; uniform int uAcc1; uniform int uAcc2;
uniform int uProp; uniform vec3 uPP; uniform mat3 uPR; uniform vec3 uPA; uniform vec3 uPB; uniform vec3 uPC;
uniform vec4 uOrb[4]; uniform vec3 uOC0; uniform vec3 uOC1; uniform vec3 uOC2; uniform vec3 uOC3;
uniform vec3 uCamPos; uniform vec3 uCamTgt; uniform float uTanF; uniform float uShadow;

vec2 res;
#define U(dd,mm) { float d_=(dd); if(d_<res.x) res=vec2(d_,mm); }

float smin(float a,float b,float k){float h=clamp(.5+.5*(b-a)/k,0.,1.);return mix(b,a,h)-k*h*(1.-h);}
float sdEll(vec3 p,vec3 r){float k0=length(p/r);float k1=length(p/(r*r));return k0*(k0-1.)/max(k1,1e-4);}
float sdCap(vec3 p,vec3 a,vec3 b,float r){vec3 pa=p-a,ba=b-a;float h=clamp(dot(pa,ba)/dot(ba,ba),0.,1.);return length(pa-ba*h)-r;}
float sdRBox(vec3 p,vec3 b,float r){vec3 q=abs(p)-b;return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.)-r;}
float sdTor(vec3 p,vec2 t){return length(vec2(length(p.xz)-t.x,p.y))-t.y;}
float sdCyl(vec3 p,float h,float r){vec2 d=abs(vec2(length(p.xz),p.y))-vec2(r,h);return min(max(d.x,d.y),0.)+length(max(d,0.));}
float sdRCone(vec3 p,vec3 a,vec3 b,float r1,float r2){
  vec3 ba=b-a;float l2=dot(ba,ba);float rr=r1-r2;float a2=l2-rr*rr;float il2=1./l2;
  vec3 pa=p-a;float y=dot(pa,ba);float z=y-l2;vec3 xv=pa*l2-ba*y;float x2=dot(xv,xv);float y2=y*y*l2;float z2=z*z*l2;
  float k=sign(rr)*rr*rr*x2;
  if(sign(z)*a2*z2>k) return sqrt(x2+z2)*il2-r2;
  if(sign(y)*a2*y2<k) return sqrt(x2+y2)*il2-r1;
  return (sqrt(x2*a2*il2)+y*rr)*il2-r1;}
float seg2(vec2 p,vec2 a,vec2 b){vec2 pa=p-a,ba=b-a;float h=clamp(dot(pa,ba)/dot(ba,ba),0.,1.);return length(pa-ba*h);}
float dot2(vec2 v){return dot(v,v);}
float sdStar5(vec2 p,float r,float rf){
  vec2 k1=vec2(0.809016994375,-0.587785252292);vec2 k2=vec2(-k1.x,k1.y);
  p.x=abs(p.x);p-=2.*max(dot(k1,p),0.)*k1;p-=2.*max(dot(k2,p),0.)*k2;p.x=abs(p.x);p.y-=r;
  vec2 ba=rf*vec2(-k1.y,k1.x)-vec2(0.,1.);float h=clamp(dot(p,ba)/dot(ba,ba),0.,r);
  return length(p-ba*h)*sign(p.y*ba.x-p.x*ba.y);}
float sdHeart(vec2 p){p.x=abs(p.x);if(p.y+p.x>1.)return sqrt(dot2(p-vec2(.25,.75)))-.353553;
  return sqrt(min(dot2(p-vec2(0.,1.)),dot2(p-.5*max(p.x+p.y,0.))))*sign(p.x-p.y);}
float ext(float d,float z,float h){vec2 w=vec2(d,abs(z)-h);return min(max(w.x,w.y),0.)+length(max(w,0.));}
mat2 r2(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}

float bodySD(vec3 q){
  if(uBody==1) return sdCap(q,uBC-vec3(0.,uBR.y,0.),uBC+vec3(0.,uBR.y,0.),uBR.x);
  if(uBody==2) return sdRBox(q-uBC,uBR,.27);
  if(uBody==3) return sdRCone(q,uBC,uBC+vec3(0.,uBR.y,0.),uBR.x,uBR.z);
  return sdEll(q-uBC,uBR);
}

void acc(int id,vec3 q){
  vec3 t=q-uTop;
  if(id==1){ /* sprout */
    U(sdCap(t,vec3(0.,-.06,0.),vec3(0.,.2,0.),.028),18.);
    vec3 a=t-vec3(-.11,.23,0.);a.xy=r2(-.5)*a.xy;U(sdEll(a,vec3(.13,.045,.08)),18.);
    vec3 b=t-vec3(.11,.25,0.);b.xy=r2(.55)*b.xy;U(sdEll(b,vec3(.12,.045,.075)),18.);
  } else if(id==2){ /* graduation cap */
    U(sdCyl(t-vec3(0.,-.04,0.),.09,.4),9.);
    vec3 b=t-vec3(0.,.07,0.);b.xz=r2(.785)*b.xz;b.xy=r2(.06)*b.xy;U(sdRBox(b,vec3(.5,.012,.5),.012),9.);
    U(length(t-vec3(0.,.1,0.))-.035,7.);
    U(sdCap(t,vec3(0.,.1,0.),vec3(.46,.08,.18),.012),7.);
    U(sdCap(t,vec3(.46,.08,.18),vec3(.47,-.12+.02*sin(uTime*3.),.2),.016),7.);
    U(sdEll(t-vec3(.47,-.17+.02*sin(uTime*3.),.2),vec3(.04,.07,.04)),7.);
  } else if(id==3){ /* round glasses */
    for(int i=0;i<2;i++){ vec3 e=(i==0?uEyeL:uEyeR)+vec3(0.,0.,uEyeRad*.85); vec3 g=q-e; U(length(vec2(length(g.xy)-uEyeRad*1.38,g.z))-.022,9.); }
    U(sdCap(q,uEyeL+vec3(uEyeRad*1.3,.04,uEyeRad*.85),uEyeR+vec3(-uEyeRad*1.3,.04,uEyeRad*.85),.02),9.);
  } else if(id==4){ /* headphones */
    vec3 h=q-vec3(uBC.x,uBC.y+.05,uBC.z); float R=uBR.x+.05;
    float band=length(vec2(length(h.xy)-R,h.z))-.045; band=max(band,-(h.y-.05)); U(band,19.);
    U(sdEll(h-vec3(-R,.0,0.),vec3(.1,.19,.16)),5.); U(sdEll(h-vec3(R,.0,0.),vec3(.1,.19,.16)),5.);
    U(sdCap(q,vec3(uBC.x-R+.02,uBC.y-.05,.12),uFace+vec3(-.2,.02,.1),.022),9.);
    U(length(q-(uFace+vec3(-.2,.02,.12)))-.055,6.);
  } else if(id==5){ /* crown */
    vec3 c=t-vec3(0.,.02,0.); float ring=sdCyl(c,.07,.3); ring=max(ring,-sdCyl(c,.2,.25)); U(ring,7.);
    float a=atan(c.z,c.x); float sec=1.2566; a=mod(a+sec*.5,sec)-sec*.5; float L=length(c.xz); vec3 s=vec3(cos(a)*L,c.y,sin(a)*L);
    U(sdRCone(s,vec3(.28,.05,0.),vec3(.28,.2,0.),.06,.015),7.);
    U(length(c-vec3(0.,.02,.31))-.045,17.);
  } else if(id==6){ /* halo */
    U(sdTor(t-vec3(0.,.3+.035*sin(uTime*2.),0.),vec2(.34,.038)),10.);
  } else if(id==7){ /* antenna */
    U(sdCap(t,vec3(0.,-.05,0.),vec3(.04,.32,0.),.028),23.);
    U(length(t-vec3(.04,.36,0.))-.085,19.);
  } else if(id==8){ /* party hat */
    vec3 c=t-vec3(-.05,-.06,0.); c.xy=r2(.18)*c.xy;
    U(sdRCone(c,vec3(0.,0.,0.),vec3(0.,.58,0.),.26,.02),20.);
    U(length(c-vec3(0.,.6,0.))-.075,6.);
  } else if(id==9){ /* baseball cap */
    vec3 c=t-vec3(0.,-.16,0.); float dome=max(sdEll(c,vec3(.56,.32,.56)),-c.y+.02); U(dome,5.);
    U(sdEll(t-vec3(0.,-.14,.5),vec3(.34,.03,.26)),6.);
    U(length(t-vec3(0.,.15,0.))-.04,6.);
  } else if(id==10){ /* beanie */
    vec3 c=t-vec3(0.,-.18,0.); float dome=max(sdEll(c,vec3(.6,.4,.58)),-c.y+.06); U(dome,5.);
    U(sdTor(c-vec3(0.,.08,0.),vec2(.56,.07)),6.);
    U(length(t-vec3(0.,.24,0.))-.1,6.);
  } else if(id==11){ /* bow */
    vec3 c=t-vec3(.3,-.12,.12); c.xy=r2(-.5)*c.xy;
    U(sdEll(c-vec3(-.13,0.,0.),vec3(.14,.09,.06)),5.); U(sdEll(c-vec3(.13,0.,0.),vec3(.14,.09,.06)),5.);
    U(length(c)-.06,6.);
  } else if(id==12){ /* beret */
    vec3 c=t-vec3(-.08,.0,0.); c.xy=r2(.2)*c.xy; U(sdEll(c,vec3(.46,.11,.42)),5.); U(length(c-vec3(0.,.12,0.))-.04,5.);
  } else if(id==13){ /* rain cloud */
    vec3 c=t-vec3(0.,.34+.03*sin(uTime*2.),0.);
    float cl=length(c-vec3(-.15,0.,0.))-.15; cl=smin(cl,length(c-vec3(.12,.02,0.))-.17,.08); cl=smin(cl,length(c-vec3(0.,.1,0.))-.16,.08); U(cl,22.);
    for(int i=0;i<3;i++){ float fi=float(i); float y=fract(uTime*1.3+fi*.33); U(length(c-vec3(-.14+fi*.14,-.2-y*.45,0.))-.03*(1.-y*.5),11.); }
  }
}

void prop(vec3 q){
  if(uProp==0) return;
  vec3 p=uPR*(q-uPP);
  if(uProp==1){ U(length(p-vec3(0.,.17,0.))-.15,10.); U(sdCyl(p-vec3(0.,-.0,0.),.06,.075),23.); U(sdTor(p-vec3(0.,.02,0.),vec2(.075,.015)),9.); }
  else if(uProp==2){ vec3 r=p-vec3(0.,.14,0.); U(length(vec2(length(r.xy)-.07,r.z))-.026,7.); U(sdCap(p,vec3(0.,.07,0.),vec3(0.,-.2,0.),.025),7.); U(sdRBox(p-vec3(.04,-.15,0.),vec3(.03,.012,.012),.004),7.); U(sdRBox(p-vec3(.035,-.2,0.),vec3(.025,.012,.012),.004),7.); }
  else if(uProp==3){ vec3 c=p.xzy; U(sdCyl(c,.03,.16)-.01,7.); U(sdCyl(c-vec3(0.,.03,0.),.008,.13),8.); vec3 n=p-vec3(0.,0.,.045); n.xy=r2(sin(uTime*1.7)*.8)*n.xy; U(sdRBox(n,vec3(.012,.1,.006),.003),17.); }
  else if(uProp==4){ for(int i=0;i<2;i++){ float s=i==0?-1.:1.; vec3 c=p-vec3(s*.18,0.,0.); c.xz=r2(s*.35)*c.xz; U(sdRBox(c,vec3(.17,.24,.008),.008),12.); U(sdRBox(c-vec3(0.,0.,.016),vec3(.155,.225,.008),.004),8.); } }
  else if(uProp==5){ U(sdCap(p,vec3(0.,-.2,0.),vec3(0.,.18,0.),.045),12.); U(sdRCone(p,vec3(0.,-.2,0.),vec3(0.,-.31,0.),.045,.008),24.); U(sdCyl(p-vec3(0.,.22,0.),.04,.046),15.); }
  else if(uProp==6){ vec3 r=p-vec3(0.,.12,0.); U(length(vec2(length(r.xy)-.13,r.z))-.03,9.); U(sdCyl(r.xzy,.01,.11),16.); U(sdCap(p,vec3(.07,.01,0.),vec3(.18,-.18,0.),.03),12.); }
  else if(uProp==7){ U(length(p-vec3(0.,.12,0.))-.1,23.); U(sdRCone(p,vec3(0.,.04,0.),vec3(0.,-.22,0.),.05,.035),9.); U(sdTor(p-vec3(0.,.05,0.),vec2(.07,.018)),12.); }
  else if(uProp==8){ vec3 c=p.xzy; U(sdCyl(c,.045,.19)-.01,12.); U(sdCyl(c-vec3(0.,.05,0.),.005,.16),8.);
    vec3 h=p-vec3(0.,0.,.06); vec3 m=h; m.xy=r2(-uTime*2.)*m.xy; U(sdRBox(m-vec3(0.,.06,0.),vec3(.01,.065,.005),.003),9.); vec3 hh=h; hh.xy=r2(-uTime*.2)*hh.xy; U(sdRBox(hh-vec3(0.,.04,0.),vec3(.012,.045,.005),.003),9.);
    U(length(p-vec3(-.13,.17,0.))-.06,7.); U(length(p-vec3(.13,.17,0.))-.06,7.); }
  else if(uProp==9){ U(sdRBox(p,vec3(.3,.018,.2),.012),23.); vec3 s=p-vec3(0.,.02,-.2); s.yz=r2(-.25)*s.yz; s-=vec3(0.,.21,0.); U(sdRBox(s,vec3(.3,.21,.012),.012),23.); U(sdRBox(s-vec3(0.,0.,.015),vec3(.27,.18,.004),.002),25.); }
  else if(uProp==10){ U(sdRBox(p,vec3(.24,.015,.08),.01),8.); for(int i=0;i<3;i++){ float fi=float(i); float h=.08+.07*fi+.03*sin(uTime*2.+fi); U(sdRBox(p-vec3(-.15+fi*.15,h+.02,0.),vec3(.05,h,.05),.012),12.+fi); } }
  else if(uProp==11){ vec3 b=p; b.xy=r2(sin(uTime*7.)*.35)*b.xy; float d=max(sdEll(b-vec3(0.,.02,0.),vec3(.15,.17,.15)),-(b.y+.02)); U(d,7.); U(sdTor(b-vec3(0.,-.02,0.),vec2(.15,.022)),7.); U(length(b-vec3(0.,-.06,0.))-.04,9.); U(sdTor((b-vec3(0.,.2,0.)).xzy,vec2(.04,.012)),7.); }
  else if(uProp==12){ U(sdEll(p,vec3(.22,.27,.05)),12.); U(ext(sdStar5(p.xy,.1,.45),p.z-.05,.012)-.006,7.); }
  else if(uProp==13){ U(sdRBox(p,vec3(.22,.15,.012),.012),8.); vec3 f=p-vec3(0.,.03,.02); U(ext(min(seg2(f.xy,vec2(-.2,.1),vec2(0.,-.04)),seg2(f.xy,vec2(.2,.1),vec2(0.,-.04)))-.012,f.z,.004),24.); U(length(p-vec3(0.,-.03,.03))-.035,17.); }
  else if(uProp==14){ U(sdCap(p,vec3(0.,-.1,0.),vec3(0.,.75,0.),.02),24.); U(length(p-vec3(0.,.77,0.))-.04,17.); }
  else if(uProp==15){ vec3 h=p; h.y+=.12; float s=.28; U(ext(sdHeart(h.xy/s)*s,h.z,.05)-.03,17.); }
  else if(uProp==16){ float cup=sdRCone(p,vec3(0.,.06,0.),vec3(0.,.26,0.),.07,.17); cup=max(cup,-sdRCone(p,vec3(0.,.1,0.),vec3(0.,.3,0.),.05,.15)); U(cup,7.);
    U(sdTor((p-vec3(-.18,.18,0.)).xzy,vec2(.06,.015)),7.); U(sdTor((p-vec3(.18,.18,0.)).xzy,vec2(.06,.015)),7.);
    U(sdCyl(p-vec3(0.,0.,0.),.06,.025),7.); U(sdRBox(p-vec3(0.,-.07,0.),vec3(.1,.025,.08),.01),9.); U(ext(sdStar5((p-vec3(0.,.17,.15)).xy,.04,.45),p.z-.15,.008),10.); }
  else if(uProp==17){ U(sdRBox(p,vec3(.19,.26,.012),.012),24.); U(sdRBox(p-vec3(0.,-.02,.016),vec3(.16,.21,.004),.002),8.); U(sdRBox(p-vec3(0.,.25,.02),vec3(.07,.03,.015),.008),23.);
    for(int i=0;i<3;i++){ float fi=float(i); U(sdRBox(p-vec3(.02,.1-fi*.09,.022),vec3(.1,.008,.002),.002),9.); U(ext(min(seg2((p-vec3(-.11,.1-fi*.09,0.)).xy,vec2(-.02,0.),vec2(0.,-.02)),seg2((p-vec3(-.11,.1-fi*.09,0.)).xy,vec2(0.,-.02),vec2(.035,.025)))-.008,p.z-.024,.003),18.); } }
  else if(uProp==18){ U(length(p-vec3(0.,.0,0.))-.15,26.); U(sdCyl(p-vec3(0.,.17,0.),.08,.045),16.); U(sdTor(p-vec3(0.,.25,0.),vec2(.05,.012)),16.); }
}

void orbs(vec3 p){
  for(int i=0;i<4;i++){
    vec4 o=uOrb[i]; if(o.w<-.5) continue;
    vec3 c=p-o.xyz; float m=30.+float(i); float sp=uTime*1.4+float(i);
    c.xz=r2(sp)*c.xz; c.xy=r2(.4)*c.xy;
    float t=o.w; float s=.13;
    if(t<.5) U(length(c)-s,m)
    else if(t<1.5) U(ext(sdStar5(c.xy,s*1.25,.45),c.z,.035)-.025,m)
    else if(t<2.5) U(sdTor(c.xzy,vec2(s*.9,.035)),m)
    else if(t<3.5) U(sdRBox(c,vec3(s*.62),.04),m)
    else if(t<4.5){ vec3 h=c; h.y+=s*.5; U(ext(sdHeart(h.xy/(s*1.1))*s*1.1,h.z,.03)-.03,m); }
    else if(t<5.5) U(ext(min(seg2(c.xy,vec2(-.11,0.),vec2(-.03,-.08)),seg2(c.xy,vec2(-.03,-.08),vec2(.12,.1)))-.035,c.z,.02)-.01,m)
    else U((abs(c.x)+abs(c.y)+abs(c.z)-s*1.2)*.577,m)
  }
}

vec2 map(vec3 p){
  res=vec2(1e5,0.);
  vec3 q=uRot*(p-uPos)+vec3(0.,1.,0.);
  float d=bodySD(q);
  d=smin(d,sdCap(q,uSL,uEL,.105),.1); d=smin(d,sdCap(q,uEL,uHL,.095),.04); d=smin(d,length(q-uHL)-.13,.04);
  d=smin(d,sdCap(q,uSR,uER,.105),.1); d=smin(d,sdCap(q,uER,uHR,.095),.04); d=smin(d,length(q-uHR)-.13,.04);
  d=smin(d,sdCap(q,uHipL,uKL,.115),.08); d=smin(d,sdCap(q,uKL,uFL,.1),.03);
  d=smin(d,sdCap(q,uHipR,uKR,.115),.08); d=smin(d,sdCap(q,uKR,uFR,.1),.03);
  res=vec2(d,1.);
  U(sdEll(q-uFL-vec3(0.,-.01,.07),vec3(.15,.085,.21)),4.);
  U(sdEll(q-uFR-vec3(0.,-.01,.07),vec3(.15,.085,.21)),4.);
  if(uEyeStyle==0){ U(length(q-uEyeL)-uEyeRad,2.); U(length(q-uEyeR)-uEyeRad,3.); }
  else if(uEyeStyle==2){ for(int i=0;i<2;i++){ vec3 e=q-(i==0?uEyeL:uEyeR); e.xy=r2(uTime*1.6+float(i))*e.xy; U(ext(sdStar5(e.xy,uEyeRad*1.35,.45),e.z,.04)-.02,7.); } }
  if(uTears>.5){ for(int i=0;i<2;i++){ vec3 e=i==0?uEyeL:uEyeR; float y=fract(uTime*1.1+float(i)*.5); U(length(q-e-vec3((i==0?-.06:.06),-.3-y*.55,.05-y*.1))-.045*(1.-y*.6),11.); } }
  if(uAcc1>0) acc(uAcc1,q);
  if(uAcc2>0) acc(uAcc2,q);
  prop(q);
  orbs(p);
  return res;
}

vec3 calcN(vec3 p){vec2 e=vec2(.0015,-.0015);return normalize(e.xyy*map(p+e.xyy).x+e.yyx*map(p+e.yyx).x+e.yxy*map(p+e.yxy).x+e.xxx*map(p+e.xxx).x);}
float calcAO(vec3 p,vec3 n){float o=0.,s=1.;for(int i=0;i<4;i++){float h=.02+.07*float(i);o+=(h-map(p+n*h).x)*s;s*=.75;}return clamp(1.-1.6*o,0.,1.);}

vec3 paintFace(vec3 q,vec3 c){
  if(q.z<0.) return c;
  float aa=.007;
  vec3 dark=vec3(.16,.05,.07); vec3 tongue=vec3(.96,.38,.46);
  /* blush */
  if(uBlush>0.){ for(int i=0;i<2;i++){ vec3 e=i==0?uEyeL:uEyeR; vec2 b=(q.xy-vec2(e.x*1.55,e.y-.2))/vec2(.11,.065); c=mix(c,vec3(1.,.45,.55),uBlush*.5*(1.-smoothstep(.4,1.,length(b)))); } }
  /* painted eyes */
  for(int i=0;i<2;i++){
    vec3 e=i==0?uEyeL:uEyeR; vec2 f=q.xy-e.xy; float d=1.;
    if(uEyeStyle==1){ vec2 o=f-vec2(0.,-.05); d=abs(length(o)-.1)-.024; d=max(d,-(o.y-.035)); }
    else if(uEyeStyle==4){ vec2 o=f-vec2(0.,.08); d=abs(length(o)-.1)-.024; d=max(d,o.y+.035); }
    c=mix(dark,c,smoothstep(0.,aa,d));
    /* brows */
    float s=i==0?-1.:1.; vec2 a=vec2(-.09,0.),b=vec2(.09,0.); float by=uEyeRad+.11;
    if(uBrow==1){ a=vec2(-.09,by); b=vec2(.09,by+.03); }
    else if(uBrow==2){ a=vec2(-.09,by); b=vec2(.09,by+.06); }
    else if(uBrow==3){ a=vec2(-.09,by+(i==0?.07:0.)); b=vec2(.09,by+(i==0?.09:.0)); }
    if(uBrow>0){ a.x*=-s; b.x*=-s; float bd=seg2(f,a,b)-.022; c=mix(dark,c,smoothstep(0.,aa,bd)); }
    /* tears */
    if(uTears>.5){ float td=seg2(f,vec2(s*.03,-.1),vec2(s*.08,-.5))-.035; c=mix(vec3(.55,.82,1.),c,smoothstep(0.,aa,td)); }
  }
  /* mouth */
  vec2 f=q.xy-uFace.xy; float d=1.; vec3 m=dark;
  if(uMouth==0){ vec2 o=f-vec2(0.,.13); d=abs(length(o)-.16)-.024; d=max(d,o.y+.085); }
  else if(uMouth==1){ vec2 o=f-vec2(0.,.03); d=max(length(o*vec2(1.,1.1))-.17,o.y);
    float tg=length((f-vec2(0.,-.12))*vec2(1.,1.5))-.09; m=mix(tongue,dark,smoothstep(0.,aa,tg)); m=mix(vec3(1.),m,smoothstep(0.,aa,-(o.y+.04))); }
  else if(uMouth==2){ d=length((f-vec2(0.,-.03))*vec2(1.,.78))-.065; }
  else if(uMouth==3){ vec2 o=f-vec2(0.,-.17); d=abs(length(o)-.15)-.024; d=max(d,-(o.y-.09)); }
  else if(uMouth==4){ vec2 o=f-vec2(0.,-.12); d=max(length(o*vec2(1.,1.15))-.15,-o.y); float tg=length((f-vec2(0.,-.08))*vec2(1.,1.8))-.07; m=mix(tongue,dark,smoothstep(0.,aa,tg)); }
  else if(uMouth==5){ d=seg2(f,vec2(-.08,-.02),vec2(.08,-.02))-.022; }
  else if(uMouth==6){ float h=.025+.075*uTalk; vec2 o=(f-vec2(0.,-.02))/vec2(.09,h); d=(length(o)-1.)*min(.09,h); float tg=length((f-vec2(0.,-.02-h*.55))*vec2(1.,2.))-.06; m=mix(tongue,dark,smoothstep(0.,aa,tg)); }
  else if(uMouth==7){ vec2 g=r2(-.3)*(f-vec2(.03,0.)); vec2 o=g-vec2(0.,.13); d=abs(length(o)-.15)-.022; d=max(d,o.y+.1); }
  return mix(m,c,smoothstep(0.,aa,d));
}

vec3 matCol(float id,vec3 p,vec3 q,vec3 n,out float gl,out vec3 em){
  gl=.55; em=vec3(0.);
  if(id<1.5){ vec3 c=uCol*mix(.9,1.06,smoothstep(uBC.y-.9,uBC.y+.9,q.y)); return paintFace(q,c); }
  if(id<3.5){ vec3 e=id<2.5?uEyeL:uEyeR; vec3 o=normalize(q-e); vec3 lk=normalize(uLook-e); float k=dot(o,lk);
    vec3 c=vec3(.98,.98,1.); c=mix(c,uIris*.35,smoothstep(.46,.48,k)); c=mix(c,uIris,smoothstep(.5,.7,k)*.85); c=mix(c,vec3(.015,.01,.02),smoothstep(.74,.76,k));
    em=vec3(1.)*smoothstep(.962,.972,dot(o,normalize(vec3(-.35,.45,.85))))*1.3+vec3(.7)*smoothstep(.992,.995,dot(o,normalize(vec3(.25,-.2,1.))));
    float side=id<2.5?1.:-1.; float cl=id<2.5?uLid.x:uLid.y; float line=e.y+uEyeRad*(1.-2.*cl)+uLid.z*(q.x-e.x)*side;
    float lid=smoothstep(line-.004,line+.004,q.y); c=mix(c,uCol*.95,lid); em*=1.-lid; c=mix(c,vec3(.12,.06,.06),(1.-lid)*smoothstep(.02,0.,abs(q.y-line))*step(.02,cl+.02));
    gl=lid>.5?.55:.98; return c; }
  if(id<4.5) return uFoot;
  if(id<5.5) return uAccA;
  if(id<6.5) return uAccB;
  if(id<7.5){ gl=1.; return vec3(1.,.72,.2); }
  if(id<8.5) return vec3(.97,.96,.94);
  if(id<9.5){ gl=.8; return vec3(.12,.12,.16); }
  if(id<10.5){ em=vec3(1.,.82,.3)*.9; return vec3(1.,.85,.4); }
  if(id<11.5){ gl=1.; em=vec3(.1,.2,.35); return vec3(.5,.78,1.); }
  if(id<12.5) return uPA;
  if(id<13.5) return uPB;
  if(id<14.5) return uPC;
  if(id<15.5) return vec3(1.,.55,.7);
  if(id<16.5){ gl=1.; em=vec3(.08,.12,.16); return vec3(.75,.9,1.); }
  if(id<17.5){ gl=.85; return vec3(.95,.22,.3); }
  if(id<18.5) return vec3(.35,.8,.38);
  if(id<19.5){ em=uAccA*.6; return uAccA; }
  if(id<20.5){ float a=atan(q.z,q.x); return mix(uAccA,uAccB,step(.5,fract(q.y*6.+a*.5))); }
  if(id<22.5) return vec3(.72,.77,.86);
  if(id<23.5){ gl=.95; return vec3(.72,.74,.8); }
  if(id<24.5) return vec3(.86,.6,.36);
  if(id<25.5){ em=vec3(.25,.7,1.)*.8; return vec3(.3,.7,1.); }
  if(id<26.5){ gl=1.; em=vec3(.2,.8,.4)*.5; return vec3(.35,.95,.55); }
  vec3 oc=id<30.5?uOC0:id<31.5?uOC1:id<32.5?uOC2:uOC3; gl=.95; em=oc*.18; return oc;
}

void main(){
  vec2 uv=(gl_FragCoord.xy-.5*uRes)/uRes.y*2.;
  vec3 ro=uCamPos; vec3 fw=normalize(uCamTgt-ro); vec3 rt=normalize(cross(fw,vec3(0.,1.,0.))); vec3 up=cross(rt,fw);
  vec3 rd=normalize(fw+uv.x*uTanF*rt+uv.y*uTanF*up);
  /* bounding sphere */
  vec3 bc=vec3(0.,1.25,0.); float br=2.3; vec3 oc=ro-bc; float b=dot(oc,rd); float c=dot(oc,oc)-br*br; float h=b*b-c;
  vec4 outc=vec4(0.);
  float pix=2.*uTanF/uRes.y;
  float tg=-ro.y/rd.y;
  if(h>0.){
    h=sqrt(h); float t=max(-b-h,0.); float tmax=-b+h; float best=1e5; float tb=t; bool hit=false;
    for(int i=0;i<110;i++){ vec3 p=ro+rd*t; float d=map(p).x; float ratio=d/t; if(ratio<best){best=ratio;tb=t;} if(d<.0007*t){hit=true;break;} t+=d*.92; if(t>tmax) break; }
    float cov=hit?1.:1.-clamp(best/pix,0.,1.);
    if(cov>0.){
      float tt=hit?t:tb; vec3 p=ro+rd*tt; vec2 mm=map(p); vec3 n=calcN(p); vec3 q=uRot*(p-uPos)+vec3(0.,1.,0.);
      float gl; vec3 em; vec3 alb=matCol(mm.y,p,q,n,gl,em);
      alb=pow(alb,vec3(2.2));
      float ao=calcAO(p,n);
      vec3 L=normalize(vec3(-.55,.78,.62)); vec3 L2=normalize(vec3(.8,.25,.35)); vec3 L3=normalize(vec3(.4,.6,-.8));
      float dif=clamp(dot(n,L)*.8+.2,0.,1.); float dif2=clamp(dot(n,L2),0.,1.); float rim=pow(clamp(dot(n,L3),0.,1.),2.);
      vec3 sky=mix(vec3(.55,.48,.52),vec3(1.,.99,1.04),n.y*.5+.5);
      vec3 col=alb*(sky*.42*ao+dif*vec3(1.06,1.,.94)*1.05+dif2*vec3(.55,.65,.85)*.28);
      col+=alb*.25*smoothstep(0.,.35,dif)*(1.-dif)*vec3(1.,.55,.45);
      col+=alb*rim*.55*ao;
      vec3 hv=normalize(L-rd); float sp=pow(clamp(dot(n,hv),0.,1.),20.+gl*90.)*gl*.85*ao;
      float fr=pow(1.-clamp(dot(n,-rd),0.,1.),4.)*.28*ao;
      col+=sp*mix(vec3(1.),alb*2.,step(6.5,mm.y)*step(mm.y,7.5))+fr*vec3(1.,.96,1.);
      col+=pow(em,vec3(2.2))*1.6+em*.25;
      col=col/(1.+col*.12);
      col=pow(col,vec3(1./2.2));
      outc=vec4(col*cov,cov);
    }
  }
  if(outc.a<.999&&tg>0.){
    vec3 g=ro+rd*tg; vec2 s=(g.xz-vec2(uPos.x,0.))/vec2(.95,.55);
    float sh=uShadow*exp(-dot(s,s)*2.2)*.42;
    outc=outc+vec4(vec3(0.),sh)*(1.-outc.a);
  }
  gl_FragColor=outc;
}`;

  /* ------------------------------------------------------------------ math */
  const V = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    len: a => Math.hypot(a[0], a[1], a[2]),
    norm: a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
    lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
  };
  function rotMat(yaw, roll, pitch) { // char -> world rotation, row-major 3x3
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cr = Math.cos(roll), sr = Math.sin(roll), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], Rz = [[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], Rx = [[1, 0, 0], [0, cp, -sp], [0, sp, cp]];
    const m = (A, B) => A.map((r, i) => [0, 1, 2].map(j => r[0] * B[0][j] + r[1] * B[1][j] + r[2] * B[2][j]));
    return m(m(Ry, Rz), Rx);
  }
  const apply = (M, v) => [M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2], M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2], M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2]];
  const transpose = M => [[M[0][0], M[1][0], M[2][0]], [M[0][1], M[1][1], M[2][1]], [M[0][2], M[1][2], M[2][2]]];
  // GLSL mat3 is column-major: q = uRot * v  must equal Minv · v (row-major Minv) -> upload Minv's columns = rows of transpose(Minv) = M (char->world) rows.
  const colMajor = M => new Float32Array([M[0][0], M[1][0], M[2][0], M[0][1], M[1][1], M[2][1], M[0][2], M[1][2], M[2][2]]);
  function hex(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
  function ik(S, T, a, b, pole) {
    let D = V.sub(T, S); let d = V.len(D);
    const dc = Math.min(Math.max(d, Math.abs(a - b) + 1e-3), a + b - 1e-3);
    const dir = V.mul(D, 1 / (d || 1));
    const x = (a * a - b * b + dc * dc) / (2 * dc);
    const h = Math.sqrt(Math.max(a * a - x * x, 0));
    let perp = V.sub(pole, V.mul(dir, V.dot(pole, dir)));
    perp = V.norm(perp);
    const E = V.add(V.add(S, V.mul(dir, x)), V.mul(perp, h));
    const H = V.add(S, V.mul(dir, dc));
    return [E, H];
  }
  const smooth = t => t * t * (3 - 2 * t);

  /* ------------------------------------------------------------------ bodies */
  const BODIES = [
    { c: [0, 1.13, 0], r: [0.78, 0.8, 0.74], sh: [0.6, 0.98], ey: 1.25, ex: 0.27, fy: 0.97, top: 1.92, hip: 0.27, bot: 0.33 },
    { c: [0, 1.22, 0], r: [0.64, 0.22, 0.64], sh: [0.54, 1.02], ey: 1.34, ex: 0.25, fy: 1.08, top: 2.06, hip: 0.26, bot: 0.36 },
    { c: [0, 1.14, 0], r: [0.5, 0.5, 0.44], sh: [0.62, 0.98], ey: 1.24, ex: 0.27, fy: 0.98, top: 1.9, hip: 0.28, bot: 0.37 },
    { c: [0, 1.02, 0], r: [0.74, 0.88, 0.1], sh: [0.58, 0.94], ey: 1.12, ex: 0.26, fy: 0.87, top: 1.98, hip: 0.26, bot: 0.28 },
    { c: [0, 1.0, 0], r: [0.92, 0.66, 0.78], sh: [0.74, 0.9], ey: 1.1, ex: 0.3, fy: 0.86, top: 1.65, hip: 0.3, bot: 0.34 }
  ];
  function bodyZ(type, B, x, y) { // front surface z (approximate, ellipsoid-like fit)
    const b = BODIES[type];
    if (type === 1) { const dy = Math.max(0, Math.abs(y - B.c[1]) - B.r[1]); const r2 = B.r[0] * B.r[0] - dy * dy - x * x; return Math.sqrt(Math.max(r2, 0.01)); }
    if (type === 2) { const ex = B.r[0] + 0.27, ey = B.r[1] + 0.27, ez = B.r[2] + 0.27; const k = 1 - Math.pow(Math.abs(x) / ex, 4) - Math.pow(Math.abs(y - B.c[1]) / ey, 4); return ez * Math.pow(Math.max(k, 0.01), 0.25); }
    if (type === 3) { const r = B.r[0] * (1 - Math.max(0, y - B.c[1]) / (B.r[1] * 1.15)); const r2 = r * r - x * x - Math.pow(Math.min(0, y - B.c[1]), 2); return Math.sqrt(Math.max(r2, 0.01)); }
    const k = 1 - Math.pow(x / B.r[0], 2) - Math.pow((y - B.c[1]) / B.r[1], 2); return B.r[2] * Math.sqrt(Math.max(k, 0.01));
  }

  /* ------------------------------------------------------------------ motions
     Each returns hand targets (char space), feet, and body motion. Character space: feet on y=0,
     +z faces the viewer, +x is the character's left on screen (viewer's right). */
  const P = {
    rest: s => [s * 0.92, 0.5, 0.16],
  };
  const MOTIONS = {
    idle(t) { return { L: [-0.92, 0.5 + 0.02 * Math.sin(t * 1.4), 0.16 + 0.05 * Math.sin(t)], R: [0.92, 0.5 + 0.02 * Math.sin(t * 1.4 + 1), 0.16 - 0.05 * Math.sin(t)], hop: 0.025 * (1 - Math.cos(t * 2.4)), yaw: 0.38 * Math.sin(t * 0.55) }; },
    wave(t) { return { L: [-0.92, 0.52, 0.16], R: [0.98 + 0.16 * Math.sin(t * 7), 1.72, 0.3], hop: 0.03 * (1 - Math.cos(t * 3.5)), yaw: 0.3 * Math.sin(t * 0.6) - 0.1, roll: -0.05 }; },
    point(t) { return { L: [-0.9, 0.52, 0.2], R: [0.62, 1.98 + 0.06 * Math.sin(t * 4), 0.35], hop: Math.abs(Math.sin(t * 2.2)) * 0.08, yaw: 0.25 * Math.sin(t * 0.7), look: 'prop', prop: 'R' }; },
    cheer(t) { const b = Math.abs(Math.sin(t * 4.6)); return { L: [-0.86, 1.82 + 0.12 * Math.sin(t * 9.2), 0.22], R: [0.86, 1.82 + 0.12 * Math.sin(t * 9.2 + 1.5), 0.22], hop: b * 0.3, squash: 1 - b, yaw: 0.25 * Math.sin(t * 1.2) }; },
    champion(t) {
      const c = t % 3.6; const flip = c > 1.6 && c < 2.6 ? smooth((c - 1.6) / 1) : c >= 2.6 ? 1 : 0;
      const b = Math.abs(Math.sin(t * 4.6));
      return { L: [-0.86, 1.8 + 0.1 * Math.sin(t * 9), 0.22], R: [0.86, 1.8 + 0.1 * Math.sin(t * 9 + 1.5), 0.25], hop: c > 1.6 && c < 2.6 ? Math.sin(flip * Math.PI) * 0.45 : b * 0.2, pitch: -flip * Math.PI * 2, squash: c > 1.6 && c < 2.6 ? 0 : 1 - b, yaw: 0.3 * Math.sin(t * 0.9), prop: 'R' };
    },
    cry(t) { const j = 0.025 * Math.sin(t * 22); return { L: [-0.27 + j, 1.13, 0.86], R: [0.27 - j, 1.13, 0.86], hop: 0, yaw: 0.12 * Math.sin(t * 0.8), roll: 0.03 * Math.sin(t * 11), squash: 0.25 + 0.1 * Math.sin(t * 11) }; },
    think(t) { return { L: [-0.32, 0.62, 0.82], R: [0.2, 0.74 + 0.02 * Math.sin(t * 3), 0.88], hop: 0.02 * (1 - Math.cos(t * 2)), yaw: -0.25 + 0.12 * Math.sin(t * 0.6), roll: 0.12, look: 'up' }; },
    read(t) { return { L: [-0.34, 0.6, 0.9], R: [0.34, 0.6, 0.9], prop: 'C', propAt: [0, 0.66, 1.02], hop: 0.02 * (1 - Math.cos(t * 2)), yaw: 0.22 * Math.sin(t * 0.5), look: 'prop' }; },
    write(t) { return { L: [-0.3, 0.68, 0.88], R: [0.1 + 0.06 * Math.sin(t * 9), 0.72 + 0.04 * Math.cos(t * 9), 1.0], prop: 'R', hop: 0, yaw: 0.18 * Math.sin(t * 0.5), roll: 0.04, look: 'prop' }; },
    type(t) { return { L: [-0.28, 0.52 + 0.04 * Math.max(0, Math.sin(t * 13)), 0.9], R: [0.28, 0.52 + 0.04 * Math.max(0, Math.sin(t * 13 + 2)), 0.9], prop: 'C', propAt: [0, 0.42, 0.95], hop: 0, yaw: 0.15 * Math.sin(t * 0.5), look: 'prop' }; },
    present(t) { return { L: [-0.72, 0.58, 0.32], R: [1.18, 1.22 + 0.06 * Math.sin(t * 2.4), 0.36], prop: 'R', hop: 0.02 * (1 - Math.cos(t * 2.4)), yaw: -0.2 + 0.18 * Math.sin(t * 0.6), roll: 0.04 }; },
    listen(t) { return { L: [-0.92, 0.52, 0.2], R: [0.84, 1.28, 0.26], hop: 0.02 * (1 - Math.cos(t * 2)), yaw: 0.3 * Math.sin(t * 0.6), roll: 0.16 + 0.05 * Math.sin(t * 2.6) }; },
    talk(t) { return { L: [-0.98, 0.9 + 0.18 * Math.sin(t * 3), 0.4], R: [0.2, 0.74, 0.92], prop: 'R', talk: 1, hop: 0.02 * (1 - Math.cos(t * 3)), yaw: 0.25 * Math.sin(t * 0.7), roll: 0.05 * Math.sin(t * 1.6) }; },
    shrug(t) { const k = Math.sin(t * 3) * 0.5 + 0.5; return { L: [-1.0, 0.82 + 0.1 * k, 0.4], R: [1.0, 0.82 + 0.1 * k, 0.4], hop: 0.04 * k, yaw: 0.2 * Math.sin(t * 0.8), roll: 0.08 * Math.sin(t * 1.5) }; },
    hug(t) { const k = smooth(Math.sin(t * 1.6) * 0.5 + 0.5); return { L: V.lerp([-1.12, 1.05, 0.4], [-0.34, 0.9, 0.9], k), R: V.lerp([1.12, 1.05, 0.4], [0.34, 0.9, 0.9], k), prop: 'C', propAt: [0, 0.95, 1.05], hop: 0.03 * k, yaw: 0.2 * Math.sin(t * 0.6) }; },
    walk(t) { const s = Math.sin(t * 5.2); return { L: [-0.9, 0.55, 0.16 - s * 0.3], R: [0.82, 0.72, 0.48 + s * 0.15], prop: 'R', FL: [-0.29, 0.08 + Math.max(0, s) * 0.12, 0.08 + s * 0.2], FR: [0.29, 0.08 + Math.max(0, -s) * 0.12, 0.08 - s * 0.2], hop: Math.abs(Math.sin(t * 5.2)) * 0.06, yaw: 0.35 * Math.sin(t * 0.5), roll: 0.04 * s }; },
    float(t) { return { L: [-1.05, 0.95 + 0.08 * Math.sin(t * 1.5), 0.1], R: [1.05, 0.95 + 0.08 * Math.sin(t * 1.5 + 1), 0.1], hop: 0.2 + 0.12 * Math.sin(t * 1.5), yaw: 0.45 * Math.sin(t * 0.4), roll: 0.06 * Math.sin(t * 0.8), FL: [-0.25, 0.14, 0.15], FR: [0.25, 0.1, 0.18] }; },
    dance(t) { const s = Math.sin(t * 4); return { L: [-0.86, s > 0 ? 1.8 : 0.7, 0.3], R: [0.86, s > 0 ? 0.7 : 1.8, 0.3], hop: Math.abs(Math.sin(t * 8)) * 0.14, yaw: 0.5 * Math.sin(t * 2), roll: 0.12 * s, prop: 'R' }; },
    strut(t) { const s = Math.sin(t * 5); return { L: [-0.9, 0.5, 0.2], R: [0.72, 1.0 + 0.04 * s, 0.6], prop: 'R', hop: Math.abs(s) * 0.05, yaw: 0.3 * Math.sin(t * 0.8), roll: 0.08 * s }; },
    ring(t) { return { L: [-0.9, 0.52, 0.2], R: [0.82, 1.28, 0.42], prop: 'R', hop: Math.abs(Math.sin(t * 3)) * 0.05, yaw: 0.3 * Math.sin(t * 0.7) }; },
    guard(t) { return { L: [-0.92, 0.55, 0.2], R: [0.3, 0.82, 0.98], prop: 'R', hop: 0.08 + 0.06 * Math.sin(t * 1.6), yaw: 0.25 * Math.sin(t * 0.5) }; },
    flip(t) { const k = Math.min(1, (t % 1.2) / 0.9); const f = smooth(k); return { L: [-0.85, 1.75, 0.2], R: [0.85, 1.75, 0.2], hop: Math.sin(f * Math.PI) * 0.42, pitch: -f * Math.PI * 2, yaw: 0 }; }
  };

  /* ------------------------------------------------------------------ registry */
  const PROPS = { none: 0, bulb: 1, key: 2, compass: 3, book: 4, pencil: 5, magnifier: 6, mic: 7, clock: 8, laptop: 9, chart: 10, bell: 11, shield: 12, envelope: 13, pointer: 14, heart: 15, trophy: 16, clipboard: 17, flask: 18 };
  const ACCS = { none: 0, sprout: 1, gradcap: 2, glasses: 3, headphones: 4, crown: 5, halo: 6, antenna: 7, partyhat: 8, cap: 9, beanie: 10, bow: 11, beret: 12, raincloud: 13 };
  const ORBS = { orb: 0, star: 1, ring: 2, cube: 3, heart: 4, check: 5, gem: 6 };
  const PROP_ROT = { pencil: [0, 0.6, 0.5], pointer: [0, -0.25, -0.9], mic: [0, 0, 0.35], magnifier: [0, -0.2, -0.3], key: [0, 0, -0.4], bulb: [0, 0, 0], compass: [0.25, 0, 0], clock: [0, 0, 0], bell: [0, 0, 0], shield: [0, 0, 0], envelope: [0, 0, 0.1], heart: [0, 0, 0], trophy: [0, 0, 0], clipboard: [0, 0, 0], flask: [0, 0, 0], chart: [0.2, 0, 0], book: [-0.35, 0, 0], laptop: [0, 0, 0] };
  const PROP_OFF = { pencil: [0.02, 0.02, 0.06], pointer: [0, 0.02, 0.05], mic: [0, 0.18, 0.06], magnifier: [0.02, 0.15, 0.08], key: [0, 0.15, 0.08], bulb: [0, 0.16, 0.05], compass: [0, 0.12, 0.12], clock: [0, 0.18, 0.1], bell: [0, 0.16, 0.1], shield: [0, 0.12, 0.14], envelope: [0, 0.14, 0.12], heart: [0, 0.12, 0.12], trophy: [0, 0.14, 0.1], clipboard: [-0.02, 0.18, 0.1], flask: [0, 0.18, 0.08], chart: [0, 0.12, 0.12], book: [0, 0, 0], laptop: [0, 0, 0] };

  /* ------------------------------------------------------------------ GL */
  let gl = null, glCanvas = null, loc = {}, generation = 0;

  async function setupRenderer() {
    const started = generation;
    try {
      const context = glCanvas.getContext('webgl', { failIfMajorPerformanceCaveat: true, premultipliedAlpha: true, alpha: true, antialias: false, preserveDrawingBuffer: false });
      if (!context) throw new Error('no webgl');
      const hp = context.getShaderPrecisionFormat(context.FRAGMENT_SHADER, context.HIGH_FLOAT);
      const fs = hp && hp.precision > 0 ? FS : FS.replace('precision highp float;', 'precision mediump float;');
      const parallel = context.getExtension('KHR_parallel_shader_compile');
      const sh = (type, src) => { const s = context.createShader(type); context.shaderSource(s, src); context.compileShader(s); return s; };
      const prog = context.createProgram();
      context.attachShader(prog, sh(context.VERTEX_SHADER, VS)); context.attachShader(prog, sh(context.FRAGMENT_SHADER, fs));
      context.linkProgram(prog);
      const deadline = performance.now() + 8000;
      while (parallel && !context.getProgramParameter(prog, parallel.COMPLETION_STATUS_KHR)) {
        await new Promise(resolve => setTimeout(resolve, 50));
        if (started !== generation) return null;
        if (context.isContextLost()) return false;
        if (performance.now() >= deadline) throw new Error('shader compilation timed out');
      }
      if (context.isContextLost()) return false;
      if (!context.getProgramParameter(prog, context.LINK_STATUS)) throw new Error(context.getProgramInfoLog(prog));
      gl = context;
      loc = {};
      gl.useProgram(prog);
      const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      const a = gl.getAttribLocation(prog, 'a'); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
      const n = gl.getProgramParameter(prog, gl.ACTIVE_UNIFORMS);
      for (let i = 0; i < n; i++) { const u = gl.getActiveUniform(prog, i); const name = u.name.replace(/\[0\]$/, ''); loc[name] = gl.getUniformLocation(prog, u.name); }
      return true;
    } catch (err) {
      gl = null;
      console.warn('CP3D: WebGL unavailable, using emoji fallback.', err && err.message);
      return false;
    }
  }
  const u3 = (n, v) => { if (loc[n]) gl.uniform3f(loc[n], v[0], v[1], v[2]); };
  const u1 = (n, v) => { if (loc[n]) gl.uniform1f(loc[n], v); };
  const ui = (n, v) => { if (loc[n]) gl.uniform1i(loc[n], v); };

  /* ------------------------------------------------------------------ one character frame */
  const CAM = { pos: [0, 1.2, 5.6], tgt: [0, 1.16, 0], tan: 0.245 };
  function frameCharacter(ch, now) {
    const spec = ch.spec, face = ch.face;
    const t = now * (ch.speed || 1) + ch.seed;
    const mot = (MOTIONS[ch.motion] || MOTIONS.idle)(t);
    const type = spec.body || 0;
    const base = BODIES[type];
    // boxy / wide bodies stick out further in front: push front-of-body hand poses forward
    const zf = type === 2 ? 0.16 : type === 4 ? 0.07 : type === 1 ? 0.03 : 0;
    if (zf) ['L', 'R', 'propAt'].forEach(function (k) { if (mot[k] && mot[k][2] > 0.55) mot[k] = [mot[k][0], mot[k][1], mot[k][2] + zf]; });
    // squash & stretch
    const sq = mot.squash ? mot.squash * 0.07 : 0;
    const sy = 1 - sq, sx = 1 + sq * 0.6;
    const B = { c: [0, base.bot + (base.c[1] - base.bot) * sy, 0], r: type === 1 ? [base.r[0] * sx, base.r[1] * sy, base.r[2]] : type === 3 ? [base.r[0] * sx, base.r[1] * sy, base.r[2]] : [base.r[0] * sx, base.r[1] * sy, base.r[2] * sx] };
    const yOf = y => base.bot + (y - base.bot) * sy;
    const shz = type === 2 ? 0.3 : type === 4 ? 0.12 : 0;
    const SL = [-base.sh[0] * sx, yOf(base.sh[1]), shz], SR = [base.sh[0] * sx, yOf(base.sh[1]), shz];
    const ey = yOf(base.ey), ex = (base.ex + 0.02) * sx, er = spec.eye || 0.165;
    const eyeL = [-ex, ey, bodyZ(type, B, ex, ey) - er * 0.42], eyeR = [ex, ey, eyeL[2]];
    const fy = yOf(base.fy);
    const faceP = [0, fy, bodyZ(type, B, 0, fy)];
    const top = [0, yOf(base.top) - 0.03, 0];
    // arms (IK). Poles keep elbows out and slightly back.
    const [EL, HL] = ik(SL, mot.L, 0.32, 0.31, [-0.7, -0.5, -0.5]);
    const [ER, HR] = ik(SR, mot.R, 0.32, 0.31, [0.7, -0.5, -0.5]);
    const hipY = base.bot + 0.12;
    const HipL = [-base.hip, hipY, 0.02], HipR = [base.hip, hipY, 0.02];
    const [KL, FL] = ik(HipL, mot.FL || [-base.hip - 0.02, 0.09, 0.06], 0.19, 0.19, [0, 0.2, 1]);
    const [KR, FR] = ik(HipR, mot.FR || [base.hip + 0.02, 0.09, 0.06], 0.19, 0.19, [0, 0.2, 1]);
    // whole-body transform (pivot at body centre)
    const yaw = (mot.yaw || 0) + (ch.yawBias || 0), roll = mot.roll || 0, pitch = mot.pitch || 0;
    const M = rotMat(yaw, roll, pitch); const Mi = transpose(M);
    const pivotW = [ch.x || 0, 1 + (mot.hop || 0), 0];
    const toChar = w => V.add(apply(Mi, V.sub(w, pivotW)), [0, 1, 0]);
    const toWorld = c => V.add(apply(M, V.sub(c, [0, 1, 0])), pivotW);
    // prop
    let propPos = HR, propId = PROPS[ch.prop || 'none'] || 0, prot = [0, 0, 0];
    if (propId) {
      const off = PROP_OFF[ch.prop] || [0, 0.1, 0.08];
      prot = PROP_ROT[ch.prop] || [0, 0, 0];
      if (mot.prop === 'C' || ch.prop === 'book' || ch.prop === 'laptop') propPos = mot.propAt || V.lerp(HL, HR, 0.5);
      else propPos = V.add(HR, off);
      if (ch.prop === 'book' && mot.prop !== 'C') propPos = V.add(HR, [-0.1, 0.12, 0.12]);
      if (ch.prop === 'laptop' && mot.prop !== 'C') propPos = [0, 0.42, 0.95];
    }
    // orbiters (world space; ellipse sized to stay inside the frame)
    const orbs = ch.orbs || [];
    const ow = [];
    let front = null, frontZ = -9;
    for (let i = 0; i < 4; i++) {
      if (i >= orbs.length) { ow.push([0, 0, 0, -1]); continue; }
      const a = now * 0.62 * (ch.orbSpeed || 1) + i * Math.PI * 2 / orbs.length + ch.seed;
      const p = [1.18 * Math.cos(a), 1.12 + 0.16 * Math.sin(a * 2 + i), 0.7 * Math.sin(a)];
      ow.push([p[0], p[1], p[2], ORBS[orbs[i].t] || 0]);
      if (p[2] > frontZ) { frontZ = p[2]; front = p; }
    }
    // eyes: follow the nearest orbiter, the prop, the pointer, or look up while thinking
    let target;
    if (ch.pointer) target = ch.pointer;
    else if (mot.look === 'up') target = toWorld([-0.7, 2.6, 2.2]);
    else if (mot.look === 'prop' && propId) target = toWorld(propPos);
    else if (front) target = front;
    else target = [0, 1.2, 4];
    ch.lookW = ch.lookW ? V.lerp(ch.lookW, target, 0.12) : target;
    const look = toChar(V.lerp(ch.lookW, CAM.pos, 0.38));
    // blink
    if (!ch.nextBlink || now > ch.nextBlink + 0.16) ch.nextBlink = now + 1.8 + Math.random() * 3.2;
    const blink = now > ch.nextBlink && now < ch.nextBlink + 0.16 ? Math.sin((now - ch.nextBlink) / 0.16 * Math.PI) : 0;
    const lid = face.lid || [0, 0, 0];

    u1('uTime', t);
    u3('uPos', pivotW);
    gl.uniformMatrix3fv(loc.uRot, false, colMajor(Mi));
    ui('uBody', type === 4 ? 0 : type);
    u3('uBC', B.c); u3('uBR', type === 4 ? B.r : B.r);
    u3('uCol', spec.rgb); u3('uFoot', spec.footRgb); u3('uIris', spec.irisRgb); u3('uAccA', spec.accARgb); u3('uAccB', spec.accBRgb);
    u3('uSL', SL); u3('uSR', SR); u3('uEL', EL); u3('uER', ER); u3('uHL', HL); u3('uHR', HR);
    u3('uHipL', HipL); u3('uHipR', HipR); u3('uKL', KL); u3('uKR', KR); u3('uFL', FL); u3('uFR', FR);
    u3('uEyeL', eyeL); u3('uEyeR', eyeR); u1('uEyeRad', er); u3('uLook', look);
    u3('uLid', [Math.max(lid[0], blink), Math.max(lid[1], blink), lid[2]]);
    ui('uEyeStyle', face.eyes || 0); ui('uMouth', mot.talk ? 6 : (face.mouth || 0)); ui('uBrow', face.brow || 0);
    u1('uTalk', 0.5 + 0.5 * Math.sin(t * 17) * Math.sin(t * 5.3)); u1('uBlush', face.blush === undefined ? (spec.blush ? 1 : 0) : face.blush); u1('uTears', face.tears ? 1 : 0);
    u3('uFace', faceP); u3('uTop', top);
    ui('uAcc1', ACCS[(ch.acc || spec.acc || [])[0]] || 0); ui('uAcc2', ACCS[(ch.acc || spec.acc || [])[1]] || 0);
    ui('uProp', propId); u3('uPP', propPos);
    gl.uniformMatrix3fv(loc.uPR, false, colMajor(transpose(rotMat(prot[1], prot[2], prot[0]))));
    const pc = ch.propColors || spec.propColors || ['#ff6b6b', '#4dabf7', '#51cf66'];
    u3('uPA', hex(pc[0])); u3('uPB', hex(pc[1])); u3('uPC', hex(pc[2]));
    if (loc.uOrb) gl.uniform4fv(loc.uOrb, new Float32Array([].concat(...ow)));
    for (let i = 0; i < 4; i++) u3('uOC' + i, hex((orbs[i] && orbs[i].c) || '#ffffff'));
    u3('uCamPos', CAM.pos); u3('uCamTgt', CAM.tgt); u1('uTanF', CAM.tan);
    u1('uShadow', 1 - Math.min(0.7, (mot.hop || 0) * 1.4));
  }

  // Run the graphics driver and bitmap creation away from the page's event loop.
  if (typeof window === 'undefined') {
    glCanvas = new OffscreenCanvas(2, 2);
    glCanvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      generation++;
      gl = null;
      postMessage({ ready: false });
    });
    glCanvas.addEventListener('webglcontextrestored', async () => {
      postMessage({ ready: await setupRenderer() === true });
    });
    onmessage = async ({ data }) => {
      if (data.init) {
        postMessage({ ready: await setupRenderer() === true });
        return;
      }
      if (!gl || gl.isContextLost()) {
        postMessage({ frame: null });
        return;
      }
      const { ch, w, h, secs } = data;
      if (glCanvas.width !== w) glCanvas.width = w;
      if (glCanvas.height !== h) glCanvas.height = h;
      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(loc.uRes, w, h);
      frameCharacter(ch, secs);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      const frame = glCanvas.transferToImageBitmap();
      postMessage({ frame, lookW: ch.lookW, nextBlink: ch.nextBlink }, [frame]);
    };
    return;
  }

  /* ------------------------------------------------------------------ public API */
  const chars = new Set();
  let raf = 0, last = 0, quality = 1, slowFrames = 0, nextCharacter = 0;
  let renderer, initialization, available = false, job;
  const rendererURL = document.currentScript?.src;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const mobile = window.matchMedia('(max-width: 900px), (pointer: coarse)');

  function init() {
    if (!rendererURL || !window.Worker || !window.OffscreenCanvas) return Promise.resolve(false);
    return new Promise(resolve => {
      function fail() {
        clearTimeout(startup);
        renderer?.terminate();
        clearTimeout(job?.timeout);
        job = null;
        available = false;
        chars.forEach(ch => ch.canvas.classList.remove('cp-rendered'));
        resolve(false);
      }
      const startup = setTimeout(fail, 10000);
      try {
        renderer = new Worker(rendererURL);
        renderer.onerror = fail;
        renderer.onmessage = ({ data }) => {
          if ('ready' in data) {
            clearTimeout(startup);
            available = data.ready;
            if (!available) chars.forEach(ch => ch.canvas.classList.remove('cp-rendered'));
            resolve(available);
          } else {
            finishFrame(data);
          }
          schedule();
        };
        renderer.postMessage({ init: true });
      } catch {
        fail();
      }
    });
  }

  function finishFrame({ frame, lookW, nextBlink }) {
    if (!job) { frame?.close(); return; }
    const { ch, w, h, started, timeout } = job;
    clearTimeout(timeout);
    job = null;
    if (!frame) return;
    if (ch.canvas.isConnected && available && !document.hidden) {
      const ctx = ch.ctx || (ch.ctx = ch.canvas.getContext('bitmaprenderer') || ch.canvas.getContext('2d'));
      if (ctx) {
        if (ch.canvas.width !== w) ch.canvas.width = w;
        if (ch.canvas.height !== h) ch.canvas.height = h;
        if (ctx.transferFromImageBitmap) ctx.transferFromImageBitmap(frame);
        else {
          ctx.clearRect(0, 0, w, h);
          ctx.drawImage(frame, 0, 0);
        }
        if (!ch.canvas.classList.contains('cp-rendered')) ch.canvas.classList.add('cp-rendered');
      }
      ch.lookW = lookW;
      ch.nextBlink = nextBlink;
    }
    frame.close();
    if (performance.now() - started > 40) {
      if (++slowFrames > 8 && quality > 0.55) { quality -= 0.15; slowFrames = 0; }
    } else {
      slowFrames = Math.max(0, slowFrames - 1);
    }
  }

  function sizeFor(ch) {
    const r = ch.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 160 / Math.max(r.width, 1), 1.25) * quality;
    return [Math.max(2, Math.round(r.width * dpr)), Math.max(2, Math.round(r.height * dpr)), r];
  }
  function draw(now) {
    raf = 0;
    if (!available || job) return;
    const fpsCap = reduce.matches ? 12 : mobile.matches ? 24 : 40;
    if (now - last < 1000 / fpsCap - 2) { schedule(); return; }
    last = now;
    const secs = now / 1000 * (reduce.matches ? 0.35 : 1);
    const visible = [];
    chars.forEach(function (ch) {
      if (!ch.canvas.isConnected) { window.CP3D.detach(ch); return; }
      if (ch.visible) visible.push(ch);
    });
    if (!visible.length) return;
    const ch = visible[nextCharacter++ % visible.length];
    const [w, h] = sizeFor(ch);
    if (w < 4 || h < 4) { schedule(); return; }
    const { canvas, ctx, box, base, ...pose } = ch;
    job = { ch, w, h, started: performance.now(), timeout: setTimeout(renderer.onerror, 4000) };
    renderer.postMessage({ ch: pose, w, h, secs });
  }
  function schedule() { if (!raf && !document.hidden) raf = requestAnimationFrame(draw); }
  function pause() {
    cancelAnimationFrame(raf);
    raf = 0;
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pause();
    else schedule();
  });
  window.addEventListener('pagehide', pause);
  window.addEventListener('pageshow', schedule);

  const io = 'IntersectionObserver' in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { const ch = e.target._cp3d; if (ch) ch.visible = e.isIntersecting; });
    schedule();
  }, { rootMargin: '80px' }) : null;

  function prep(spec) {
    if (spec.rgb) return spec;
    spec.rgb = hex(spec.color); spec.footRgb = hex(spec.foot || '#3b3f58'); spec.irisRgb = hex(spec.iris || '#4a2c1a');
    spec.accARgb = hex(spec.accA || '#ff7a59'); spec.accBRgb = hex(spec.accB || '#ffd43b');
    return spec;
  }

  window.CP3D = {
    ready: function () { return initialization || (initialization = init()); },
    /* Attach a character to a <canvas>. Returns a controller. */
    attach: function (canvas, spec, opts) {
      if (!available) return null;
      opts = opts || {};
      const ch = { canvas: canvas, spec: prep(spec), motion: opts.motion || spec.motion || 'idle', prop: opts.prop !== undefined ? opts.prop : spec.prop, acc: opts.acc, orbs: opts.orbs || [], face: opts.face || {}, seed: opts.seed || Math.random() * 20, visible: !io, x: 0, propColors: opts.propColors };
      canvas._cp3d = ch;
      chars.add(ch);
      if (io) io.observe(canvas);
      schedule();
      return ch;
    },
    detach: function (ch) { chars.delete(ch); if (io) io.unobserve(ch.canvas); },
    /* Pointer look: give client coordinates; characters near it look at it. */
    pointer: function (x, y) {
      chars.forEach(function (ch) {
        if (x === null) { ch.pointer = null; return; }
        const r = ch.canvas.getBoundingClientRect();
        const nx = ((x - r.left) / r.width - 0.5) * 2, ny = -((y - r.top) / r.height - 0.5) * 2;
        if (Math.abs(nx) > 3 || Math.abs(ny) > 3) { ch.pointer = null; return; }
        const asp = r.width / r.height;
        const d = 3.6;
        ch.pointer = [nx * CAM.tan * asp * d, CAM.tgt[1] + ny * CAM.tan * d, CAM.pos[2] - d];
      });
    },
    kick: schedule,
    PROPS: Object.keys(PROPS), ACCS: Object.keys(ACCS), ORBS: Object.keys(ORBS), MOTIONS: Object.keys(MOTIONS)
  };
})();

const fs=require('fs'),assert=require('assert');
const {JSDOM}=require('jsdom');
const fixtures=JSON.parse(fs.readFileSync(__dirname+'/fixtures.json','utf8'));
const html=fs.readFileSync(__dirname+'/../../app/templates/index.html','utf8');
const js=fs.readFileSync(__dirname+'/../../app/static/app.js','utf8')+'\n'+fs.readFileSync(__dirname+'/../../app/static/workflows.js','utf8')+'\n'+fs.readFileSync(__dirname+'/../../app/static/universal.js','utf8');
(async()=>{
let checks=0;
for(const role of ['student','teacher','admin']){
 const dom=new JSDOM(html,{url:'http://localhost',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.fetch=async url=>{const data=fixtures[role][url];if(data===undefined)throw Error('Unstubbed endpoint: '+url);return {ok:true,status:200,json:async()=>structuredClone(data)};};
 w.eval(js+"\nwindow.navigate=navigate;window.coursePage=coursePage;window.authPage=authPage;window.appState=state;");await new Promise(r=>setTimeout(r,50));
 const pages=role==='student'?['dashboard','courses','path','tutor','quiz','graph','voice','materials','assignments','planner','lab','analytics','notifications','settings']:role==='teacher'?['dashboard','courses','students','topics','materials','questions','assignments','analytics','copilot','viva-review','research','notifications','settings']:['dashboard','settings'];
 for(const page of pages){await w.navigate(page);assert(!w.document.querySelector('.error-state'),`${role}/${page}: ${w.document.querySelector('main').textContent}`);assert(w.document.querySelector('h1'),`${role}/${page} heading missing`);assert(!w.document.querySelector('script[src^="http"]'));checks++;}
 if(role==='student')assert(!w.document.querySelector('[data-nav="students"]'));
 await w.navigate('courses');
 fixtures[role]['/api/courses'][0]&&(fixtures[role]['/api/courses'][0].description='<img src=x onerror=alert(1)>');
 if(role==='student'){w.appState.courses[0].description='<img src=x onerror=alert(1)>';await w.coursePage();assert(!w.document.querySelector('img[onerror]'));checks++;}
 w.authPage('register');const select=w.document.querySelector('#role');select.value='teacher';select.dispatchEvent(new w.Event('change',{bubbles:true}));assert(!w.document.querySelector('#faculty-key').hidden);checks++;
 w.close();
}
console.log(`${checks} DOM checks passed. This does not verify visual layout, browser speech or real browser interactions.`);
})().catch(e=>{console.error(e);process.exit(1)});

const fs=require('fs'),path=require('path'),assert=require('assert');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<form id="oral-answer-form"></form><input id="oral-auto-listen" type="checkbox" checked><div id="voice-status"></div>',{runScripts:'outside-only',url:'http://localhost'});
const w=dom.window;let spoken,recorded=0,checks=0;
w.state={voiceEpoch:0,oral:{question:{question_text:'Explain the source concept.'}},health:{tts_configured:false}};
w.$=q=>w.document.querySelector(q);w.stopVoice=()=>{w.state.voiceEpoch++};w.toast=()=>{};w.record=()=>{recorded++};
w.SpeechSynthesisUtterance=function(t){this.text=t};w.speechSynthesis={speak:s=>{spoken=s}};
w.eval(fs.readFileSync(path.join(__dirname,'../../app/static/universal.js'),'utf8')+'\nwindow.speakOral=speakOral;');
(async()=>{
 await w.speakOral();assert.equal(spoken.text,'Explain the source concept.');checks++;
 assert.equal(recorded,0);checks++;spoken.onend();assert.equal(recorded,1);checks++;
 await w.speakOral();spoken.onerror();assert.equal(recorded,1);checks++;
 w.state.health.tts_configured=true;w.fetch=async()=>({ok:false});await w.speakOral();assert.equal(recorded,1);spoken.onend();assert.equal(recorded,2);checks++;
 await w.speakOral();w.stopVoice();spoken.onend();assert.equal(recorded,2);checks++;
 console.log(`${checks} viva playback lifecycle checks passed using browser/provider doubles; no hardware tested.`);dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});

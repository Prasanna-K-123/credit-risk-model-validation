"use strict";
// Execute the actual embedded explorer, then challenge every filter against
// independent counts from the frozen full prediction CSV. This is not browser QA.
const fs=require("fs"),path=require("path"),vm=require("vm"),zlib=require("zlib"),assert=require("assert");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"docs/index.html"),"utf8");
const json=html.match(/<script id="evidence" type="application\/json">([\s\S]*?)<\/script>/)[1];
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
class Node{
 constructor(tag){this.tagName=tag;this.children=[];this.textContent="";this.value="";this.style={};this.events={};}
 appendChild(child){this.children.push(child);return child;}
 replaceChildren(...children){this.children=children;}
 addEventListener(event,handler){this.events[event]=handler;}
}
const ids={};for(const m of html.matchAll(/\bid="([^"]+)"/g))ids[m[1]]=new Node("div");
ids.evidence.textContent=json;ids.cohort.value="all";
const context={document:{getElementById:(id)=>{assert(ids[id],"Unknown ID "+id);return ids[id];},createElement:tag=>new Node(tag)},window:{},console};
vm.createContext(context);vm.runInContext(scripts[0][1],context);
const app=context.window.bankExplorer;
const ref=path.join(root,"bank_monitoring/reference/fdic_temporal");
const summary=JSON.parse(fs.readFileSync(path.join(ref,"summary.json"),"utf8"));
const lines=zlib.gunzipSync(fs.readFileSync(path.join(ref,"test_predictions.csv.gz"))).toString("utf8").trimEnd().split(/\r?\n/);
const header=lines.shift().split(",");
assert(!lines.some(line=>line.includes('"')),"This strict numeric/date fixture reader does not accept quoted fields");
const rows=lines.map(line=>{const values=line.split(",");assert.equal(values.length,header.length);const row={};header.forEach((key,i)=>row[key]=key.includes("date")||key==="horizon_end"?values[i]:Number(values[i]));return row;});
let checks=0;
for(const name of Object.keys(summary.test_metrics)){
 const all=app.evidence.models[name],threshold=summary.test_metrics[name].threshold;
 const filters=["all","late",...new Set(rows.map(r=>r.prediction_date))];
 for(const filter of filters){
  const selected=rows.filter(r=>filter==="all"||(filter==="late"?r.prediction_date>="2022-04-01":r.prediction_date===filter));
  const totals=app.totals(app.selectedRows(all,filter));
  const truth=selected.reduce((s,r)=>{s.rows++;s.observed+=r.failure;s.expected+=r["p_"+name];s.monitored+=r["p_"+name]>=threshold;s.caught+=(r["p_"+name]>=threshold)&&r.failure===1;return s;},{rows:0,observed:0,expected:0,monitored:0,caught:0});
  for(const key of ["rows","observed","monitored","caught"]){assert.equal(totals[key],truth[key],name+"/"+filter+"/"+key);checks++;}
  assert(Math.abs(totals.expected-truth.expected)<=1e-10+1e-12*Math.abs(truth.expected));checks++;
  assert.equal(app.selectedCases(all,filter).length,truth.observed);checks++;
  ids.model.value=name;ids.cohort.value=filter;app.render();
  assert.equal(ids.annual.children.length,app.selectedRows(all,filter).length);checks++;
  assert.equal(ids.cases.children.length,Math.max(1,truth.observed));checks++;
  assert.equal(ids.cards.children[3].children[0].textContent,String(truth.observed-truth.caught));checks++;
  assert(ids.overall.textContent.startsWith("All-cohort ROC AUC "));checks++;
 }
 for(const row of all.annual){
  const group=rows.filter(r=>r.prediction_date===row.prediction_date);
  const top=group.sort((a,b)=>b["p_"+name]-a["p_"+name]||a.CERT-b.CERT).slice(0,Math.ceil(group.length/100));
  assert.equal(top.reduce((n,r)=>n+r.failure,0),row.captured_failures_at_capacity);checks++;
 }
}
const late=app.totals(app.selectedRows(app.evidence.models.hist_gradient_boosting_calibrated,"late"));
assert.equal(late.observed,10);assert.equal(late.caught,1);checks+=2;
assert(html.includes("post-hoc")&&html.includes("not live monitoring approval"));checks++;
assert(!html.includes("__EVIDENCE_JSON__"));checks++;
const receipt={executed_at_utc:new Date().toISOString(),checks,status:"passed",scope:"Actual generated embedded script in a minimal DOM, all models/cohort filters compared with frozen full prediction rows. No browser or screen-reader certification."};
fs.mkdirSync(path.join(root,"artifacts"),{recursive:true});
fs.writeFileSync(path.join(root,"artifacts/explorer_execution.json"),JSON.stringify(receipt,null,2)+"\n");
console.log(JSON.stringify(receipt));

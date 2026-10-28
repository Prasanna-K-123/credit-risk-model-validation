"use strict";
const evidence = JSON.parse(document.getElementById("evidence").textContent);
const labels = {constant:"Development-rate baseline",capital_only:"Capital-only logistic",logistic_raw:"Full logistic · raw",logistic_calibrated:"Full logistic · calibrated",hist_gradient_boosting_raw:"Boosting · raw",hist_gradient_boosting_calibrated:"Boosting · calibrated"};
const modelSelect = document.getElementById("model"), cohortSelect = document.getElementById("cohort");
function element(tag, text, className) { const node=document.createElement(tag); if(text!==undefined)node.textContent=text;if(className)node.className=className;return node; }
function clear(id) { const node=document.getElementById(id);node.replaceChildren();return node; }
Object.entries(labels).forEach(([key,label])=>{const option=element("option",label);option.value=key;modelSelect.appendChild(option);});
modelSelect.value="hist_gradient_boosting_calibrated";
evidence.models.constant.annual.forEach(row=>{const option=element("option",row.prediction_date.slice(0,4)+" cohort");option.value=row.prediction_date;cohortSelect.appendChild(option);});
function fmt(value,digits=0){return value===null?"Undefined":Number(value).toLocaleString("en-US",{minimumFractionDigits:digits,maximumFractionDigits:digits});}
function selectedRows(model,filter){return model.annual.filter(row=>filter==="all"||(filter==="late"?row.prediction_date>="2022-04-01":row.prediction_date===filter));}
function selectedCases(model,filter){return model.failure_cases.filter(row=>filter==="all"||(filter==="late"?row.prediction_date>="2022-04-01":row.prediction_date===filter));}
function totals(rows){return rows.reduce((s,r)=>({rows:s.rows+r.rows,observed:s.observed+r.failures,expected:s.expected+r.expected_failures,monitored:s.monitored+r.test_monitor_count,caught:s.caught+r.test_caught_failures,capacityCaught:s.capacityCaught+r.captured_failures_at_capacity}),{rows:0,observed:0,expected:0,monitored:0,caught:0,capacityCaught:0});}
function render(){
 const model=evidence.models[modelSelect.value],rows=selectedRows(model,cohortSelect.value),sum=totals(rows);
 document.getElementById("overall").textContent="All-cohort ROC AUC "+fmt(model.overall.auc,3)+" · Brier "+fmt(model.overall.brier,7)+" · Fixed threshold "+fmt(model.threshold,6)+". These pooled metrics do not change with the cohort filter.";
 const cards=clear("cards");
 [[fmt(sum.observed),"Observed failures"],[fmt(sum.expected,2),"Expected failures"],[fmt(sum.caught)+" / "+fmt(sum.observed),"Caught by fixed rule"],[fmt(sum.observed-sum.caught),"Missed by fixed rule"]].forEach(([value,label])=>{const card=element("div",undefined,"card");card.appendChild(element("span",value,"value"));card.appendChild(element("span",label,"label"));cards.appendChild(card);});
 const bars=clear("bars"),ceiling=Math.max(1,...rows.flatMap(r=>[r.failures,r.expected_failures]));
 rows.forEach(r=>{const row=element("div",undefined,"chart-row");row.appendChild(element("span",r.prediction_date.slice(0,4)));const pair=element("div",undefined,"bars");const actual=element("div",undefined,"bar actual"),expected=element("div",undefined,"bar expected");actual.style.width=(r.failures/ceiling*100)+"%";expected.style.width=(r.expected_failures/ceiling*100)+"%";pair.appendChild(actual);pair.appendChild(expected);row.appendChild(pair);row.appendChild(element("span",fmt(r.failures)+" / "+fmt(r.expected_failures,2)));bars.appendChild(row);});
 const annual=clear("annual");
 rows.forEach(r=>{const tr=element("tr");[r.prediction_date.slice(0,4),fmt(r.rows),fmt(r.failures),fmt(r.expected_failures,2),fmt(r.test_monitor_count),fmt(r.test_caught_failures),fmt(r.test_missed_failures),fmt(r.captured_failures_at_capacity)+" / "+fmt(r.review_capacity)].forEach((value,index)=>tr.appendChild(element("td",value,index?"numeric"+(index===6&&r.test_missed_failures?" fail":""):"")));annual.appendChild(tr);});
 const cases=selectedCases(model,cohortSelect.value),table=clear("cases");
 document.getElementById("case-count").textContent=cases.length+" failed-bank cases in selected cohorts";
 cases.forEach(r=>{const tr=element("tr");[String(r.certificate),r.prediction_date,r.failure_date,fmt(r.probability*100,4)+"%",r.monitored?"Caught":"Missed",r.top_one_percent?"Included":"Outside"].forEach((value,index)=>tr.appendChild(element("td",value,index===3?"numeric":(index===4?(r.monitored?"pass":"fail"):""))));table.appendChild(tr);});
 if(!cases.length){const tr=element("tr"),td=element("td","No observed failures in this cohort; that does not establish zero future risk.","empty");td.colSpan=6;tr.appendChild(td);table.appendChild(tr);}
}
modelSelect.addEventListener("change",render);cohortSelect.addEventListener("change",render);render();
document.getElementById("status").textContent=evidence.governance.status.replaceAll("_"," ");
evidence.governance.findings.forEach(f=>document.getElementById("findings").appendChild(element("div",f.message,"finding")));
["CERT","prediction_date"].forEach(unit=>{const r=evidence.paired_uncertainty[unit].metrics.weighted_cost_per_row;document.getElementById("intervals").appendChild(element("p",(unit==="CERT"?"Bank-cluster":"Annual-cohort")+" 95% interval: ["+fmt(r.percentile_95[0],5)+", "+fmt(r.percentile_95[1],5)+"] illustrative cost per bank observation, boosting minus logistic.","small"));});
window.bankExplorer={selectedRows,selectedCases,totals,render,evidence};

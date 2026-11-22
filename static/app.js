const $ = s => document.querySelector(s);
const THEMES = {
  Solo:    {t:"Your night, your pace. Calm spots, zero crowds.", e:["✦","·","✧","⋆"]},
  Friends: {t:"Squad goals. Street food, malls and loud laughs.", e:["🎉","🎈","✨","🍿"]},
  Couples: {t:"Slow walks, sunset views and a table for two.",   e:["💗","🌹","💕","✨"]},
  Family:  {t:"Easy outings for every age, budget-friendly.",     e:["🌼","☀️","🎈","🍦"]}
};
let vibe = "Friends", avoid = true, lastReq = null, lastPlans = [];

function setVibe(v){
  vibe = v; document.body.dataset.vibe = v; $("#tagline").textContent = THEMES[v].t;
  document.querySelectorAll(".vibe").forEach(b => b.classList.toggle("active", b.dataset.v === v));
  const f = $("#floaters"); f.innerHTML = "";
  for(let i=0;i<22;i++){
    const s = document.createElement("span"), solo = v==="Solo";
    s.textContent = THEMES[v].e[i % 4];
    s.style.left = Math.random()*100+"vw"; s.style.fontSize = (12+Math.random()*22)+"px";
    s.style.animationDuration = (solo? 2+Math.random()*4 : 9+Math.random()*12)+"s";
    s.style.animationDelay = (-Math.random()*12)+"s";
    if(solo) s.style.top = Math.random()*100+"vh";
    f.appendChild(s);
  }
}
document.querySelectorAll(".vibe").forEach(b => b.onclick = () => { setVibe(b.dataset.v); if(lastReq) plan(); });
document.querySelectorAll("#crowdPref button").forEach(b => b.onclick = () => {
  document.querySelectorAll("#crowdPref button").forEach(x => x.classList.remove("on"));
  b.classList.add("on"); avoid = b.dataset.a === "1";
});
function perHead(){ $("#perhead").textContent = Math.round(($("#budget").value||0)/Math.max(1,$("#people").value||1)); }
["budget","people"].forEach(i => $("#"+i).oninput = perHead);

const rupee = n => "₹" + Number(n).toLocaleString("en-IN");
const statusTxt = {green:"Free", yellow:"Moderate", red:"Busy"};
const badge = b => `<span class="badge ${b}">${statusTxt[b]}</span>`;
const srcTxt = {live:"LIVE", besttime:"BestTime", static:"estimate"};

async function plan(){
  lastReq = {city:$("#city").value, vibe, budget:+$("#budget").value, people:+$("#people").value,
             slot:$("#slot").value, avoid_crowds:avoid};
  const r = await fetch("/api/plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(lastReq)});
  const d = await r.json();
  if(d.error){ $("#plans").innerHTML = `<div class="panel empty">${d.error}</div>`; return; }
  lastPlans = d.plans;
  $("#summary").textContent = `${vibe} in ${lastReq.city}: ${rupee(d.per_head_budget)} per head, ${d.candidates} spots match.`;
  if(!d.plans.length){
    $("#plans").innerHTML = `<div class="panel empty"><h2>No plan fits yet</h2><p class="muted">Raise the budget, choose “Show everything”, or try another time slot.</p></div>`;
    return;
  }
  $("#plans").innerHTML = d.plans.map((p,i)=>`
   <article class="panel plan">
     <div class="plan-head"><h2>Plan ${"ABC"[i]}${i===0?" · best match":""}</h2>${badge(p.badge)}</div>
     <div class="stats">
       <div class="stat"><b>${rupee(p.per_head_total)}</b><small>per head</small></div>
       <div class="stat"><b>${rupee(p.group_total)}</b><small>group spend</small></div>
       <div class="stat"><b>${rupee(p.buffer)}</b><small>buffer left</small></div>
       <div class="stat"><b>${p.stops.length}</b><small>stops</small></div>
     </div>
     <div class="timeline">${p.stops.map(s=>`
       <div class="stop">
         <div class="time">${s.arrive} – ${s.leave} (${s.hours} h)</div>
         <h3>${s.name}<span class="live">${srcTxt[s.source]}</span></h3>
         ${s.hop_km?`<div class="hop">${s.hop_km} km from previous stop</div>`:''}
         <div>${badge(s.badge)} <small class="muted">${s.area} · ${s.category}</small></div>
         <div class="cost"><span>Entry ${rupee(s.entry_fee)}</span><span>Food/activity ${rupee(s.food_activity)}</span>
           <span>Transit ${rupee(s.transit_cost)}</span><span class="t">${rupee(s.per_head)} / head · ${rupee(s.group_cost)} group</span></div>
         <div class="muted">🚇 ${s.nearest_transit}</div>
       </div>`).join("")}</div>
     <button class="ghost" onclick="savePlan(${i})">Save this plan</button>
   </article>`).join("");
}
$("#planBtn").onclick = plan;
$("#city").onchange = () => { if(lastReq) plan(); };

async function savePlan(i){
  await fetch("/api/plans",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
    title:`${lastReq.vibe} · ${lastPlans[i].stops.map(s=>s.name.split(" ")[0]).join(" → ")}`,
    city:lastReq.city, vibe:lastReq.vibe, slot:lastReq.slot, budget:lastReq.budget, people:lastReq.people, plan:lastPlans[i]})});
  loadSaved();
}
async function loadSaved(){
  const d = await (await fetch("/api/plans")).json();
  $("#saved").innerHTML = d.length ? d.map(p=>`<li><span>${p.title}<br><small>${p.city} · ${p.slot.replace("_"," ")} · ${rupee(p.plan_json.group_total)} · ${p.created_at}</small></span>
    <button onclick="delPlan(${p.plan_id})">Delete</button></li>`).join("") : `<li>Nothing saved yet. Build a plan and tap “Save this plan”.</li>`;
}
async function delPlan(id){ await fetch("/api/plans/"+id,{method:"DELETE"}); loadSaved(); }

setVibe("Friends"); perHead(); loadSaved(); plan();

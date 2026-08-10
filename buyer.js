
const BuyerDemo={
 rfqs:[
  {id:"RFQ-001",item:"هامور محلي",qty:50,delivery:"دبي",status:"open"},
  {id:"RFQ-002",item:"كنعد",qty:100,delivery:"أبوظبي",status:"quoted"}
 ],
 orders:[
  {no:"B2B-001",item:"شعري 40 كجم",total:1020,status:"confirmed"}
 ]
};
function showBuyerPanel(id,el){document.querySelectorAll(".buyer-panel").forEach(x=>x.classList.remove("active"));document.getElementById(id).classList.add("active");document.querySelectorAll(".buyer-sidebar a").forEach(a=>a.classList.remove("active"));if(el)el.classList.add("active")}
function money(n){return "AED "+Number(n).toFixed(2)}
async function renderBuyer(){
 const offers=await Bahrna.getMarketOffers();
 document.getElementById("wholesaleCards").innerHTML=offers.filter(o=>o.wholesale>0).sort((a,b)=>a.wholesale-b.wholesale).map(o=>`<div class="card"><span class="badge">${o.supplier}</span><h3>${o.name}</h3><div class="price">AED ${Number(o.wholesale).toFixed(2)} <small>/كجم</small></div><p class="muted">متوفر ${o.qty} كجم • Retail ${Number(o.retail).toFixed(2)}</p><button class="btn btn-primary" onclick="prefillRFQ('${o.name}',${o.qty})">طلب كمية</button></div>`).join("");
 document.getElementById("rfqRows").innerHTML=BuyerDemo.rfqs.map(r=>`<tr><td>${r.id}</td><td>${r.item}</td><td>${r.qty} كجم</td><td>${r.delivery}</td><td>${r.status}</td></tr>`).join("");
 document.getElementById("b2bRows").innerHTML=BuyerDemo.orders.map(o=>`<tr><td>${o.no}</td><td>${o.item}</td><td>${money(o.total)}</td><td>${o.status}</td></tr>`).join("");
 document.getElementById("rfqCount").textContent=BuyerDemo.rfqs.length;document.getElementById("b2bOrderCount").textContent=BuyerDemo.orders.length;
}
function prefillRFQ(name,qty){showBuyerPanel("newRfqPanel");document.getElementById("rfqItem").value=name;document.getElementById("rfqQty").value=Math.min(qty,50)}
function submitRFQ(){const item=rfqItem.value.trim(),qty=Number(rfqQty.value),delivery=rfqDelivery.value;if(!item||!qty)return alert("أكمل المنتج والكمية");BuyerDemo.rfqs.push({id:"RFQ-"+String(BuyerDemo.rfqs.length+1).padStart(3,"0"),item,qty,delivery,status:"open"});renderBuyer();showBuyerPanel("rfqPanel")}
document.addEventListener("DOMContentLoaded",renderBuyer);

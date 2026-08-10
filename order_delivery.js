
const OrderFlow={
 cart: JSON.parse(localStorage.getItem("bahrna_cart")||"null") || [
  {id:"demo-hamour",name:"هامور محلي",price:49.90,qty:2}
 ],
 cut:{name:"كامل",fee:0},
 packaging:{name:"بدون ثلج",fee:0},
 keepHeadBones:true,
 address:{emirate:"دبي",area:"",address:""},
 slot:"",
 deliveryFee:10,
 vatRate:0.05
};
function saveCart(){localStorage.setItem("bahrna_cart",JSON.stringify(OrderFlow.cart))}
function money(n){return "AED "+Number(n).toFixed(2)}
function cartSubtotal(){return OrderFlow.cart.reduce((s,x)=>s+x.price*x.qty,0)}
function calcTotals(){
 const subtotal=cartSubtotal();
 const prep=OrderFlow.cut.fee;
 const pack=OrderFlow.packaging.fee;
 const delivery=OrderFlow.deliveryFee;
 const vat=(subtotal+prep+pack+delivery)*OrderFlow.vatRate;
 const total=subtotal+prep+pack+delivery+vat;
 return {subtotal,prep,pack,delivery,vat,total}
}
function renderCart(){
 const wrap=document.getElementById("cartRows"); if(!wrap)return;
 wrap.innerHTML=OrderFlow.cart.map((x,i)=>`<div class="cart-item"><div class="cart-thumb">🐟</div><div><strong>${x.name}</strong><div class="muted">${money(x.price)} / كجم</div><div class="stepper"><button onclick="changeQty(${i},-1)">−</button><strong>${x.qty} كجم</strong><button onclick="changeQty(${i},1)">+</button></div></div><div><strong>${money(x.price*x.qty)}</strong><br><button class="btn small" onclick="removeItem(${i})">حذف</button></div></div>`).join("");
 const t=calcTotals(); document.getElementById("cartSubtotal").textContent=money(t.subtotal);document.getElementById("cartTotal").textContent=money(t.total);
}
function changeQty(i,d){OrderFlow.cart[i].qty=Math.max(1,OrderFlow.cart[i].qty+d);saveCart();renderCart()}
function removeItem(i){OrderFlow.cart.splice(i,1);saveCart();renderCart()}
function chooseCut(el,name,fee){
 document.querySelectorAll('[data-cut]').forEach(x=>x.classList.remove("active"));el.classList.add("active");OrderFlow.cut={name,fee:Number(fee)};
 document.getElementById("cutVideoTitle").textContent="فيديو توضيحي: "+name;renderSummary();
}
function choosePack(el,name,fee){
 document.querySelectorAll('[data-pack]').forEach(x=>x.classList.remove("active"));el.classList.add("active");OrderFlow.packaging={name,fee:Number(fee)};renderSummary();
}
function setKeep(v){OrderFlow.keepHeadBones=v;renderSummary()}
function renderSummary(){
 const t=calcTotals();
 ["sumSubtotal","sumPrep","sumPack","sumDelivery","sumVat","sumTotal"].forEach(id=>{if(document.getElementById(id))document.getElementById(id).textContent=""});
 if(document.getElementById("sumSubtotal"))document.getElementById("sumSubtotal").textContent=money(t.subtotal);
 if(document.getElementById("sumPrep"))document.getElementById("sumPrep").textContent=money(t.prep);
 if(document.getElementById("sumPack"))document.getElementById("sumPack").textContent=money(t.pack);
 if(document.getElementById("sumDelivery"))document.getElementById("sumDelivery").textContent=money(t.delivery);
 if(document.getElementById("sumVat"))document.getElementById("sumVat").textContent=money(t.vat);
 if(document.getElementById("sumTotal"))document.getElementById("sumTotal").textContent=money(t.total);
 if(document.getElementById("prepText"))document.getElementById("prepText").textContent=OrderFlow.cut.name+" • "+OrderFlow.packaging.name+" • "+(OrderFlow.keepHeadBones?"مع الرأس والعظم":"بدون الرأس والعظم");
}
function continueToDelivery(){location.href="delivery.html"}
function confirmDelivery(){
 OrderFlow.address={emirate:document.getElementById("emirate").value,area:document.getElementById("area").value,address:document.getElementById("address").value};
 OrderFlow.slot=document.getElementById("slot").value;
 localStorage.setItem("bahrna_orderflow",JSON.stringify(OrderFlow));location.href="payment.html";
}
function createDemoOrder(){
 const flow=JSON.parse(localStorage.getItem("bahrna_orderflow")||"{}"); const t=calcTotals();
 const order={orderNo:"ORD-"+Date.now().toString().slice(-8),status:"confirmed",createdAt:new Date().toISOString(),items:OrderFlow.cart,cut:OrderFlow.cut,packaging:OrderFlow.packaging,keepHeadBones:OrderFlow.keepHeadBones,address:flow.address||OrderFlow.address,slot:flow.slot||OrderFlow.slot,total:t.total,history:[{status:"confirmed",time:new Date().toISOString()}]};
 localStorage.setItem("bahrna_last_order",JSON.stringify(order));location.href="confirmation.html";
}
function renderConfirmation(){
 const o=JSON.parse(localStorage.getItem("bahrna_last_order")||"null"); if(!o)return;
 document.getElementById("orderNo").textContent=o.orderNo;document.getElementById("orderTotal").textContent=money(o.total);
 document.getElementById("deliveryText").textContent=(o.address?.emirate||"")+" • "+(o.address?.area||"")+" • "+(o.slot||"موعد يحدد لاحقًا");
}
function renderTracking(){
 const o=JSON.parse(localStorage.getItem("bahrna_last_order")||"null"); if(!o)return;
 document.getElementById("trackOrderNo").textContent=o.orderNo;
 const flow=["confirmed","preparing","ready","out_for_delivery","delivered"];
 const current=flow.indexOf(o.status);
 document.querySelectorAll(".track-step").forEach((el,i)=>{if(i<current)el.classList.add("done");else if(i===current)el.classList.add("current")});
 document.getElementById("currentStatus").textContent={
  confirmed:"تم تأكيد الطلب",preparing:"جاري التجهيز",ready:"جاهز للاستلام",out_for_delivery:"خرج للتوصيل",delivered:"تم التسليم"
 }[o.status]||o.status;
}
function advanceTracking(){
 const o=JSON.parse(localStorage.getItem("bahrna_last_order")||"null"); if(!o)return;
 const flow=["confirmed","preparing","ready","out_for_delivery","delivered"];let i=flow.indexOf(o.status);if(i<flow.length-1)o.status=flow[i+1];
 o.history=o.history||[];o.history.push({status:o.status,time:new Date().toISOString()});localStorage.setItem("bahrna_last_order",JSON.stringify(o));location.reload();
}
document.addEventListener("DOMContentLoaded",()=>{renderCart();renderSummary();renderConfirmation();renderTracking()});

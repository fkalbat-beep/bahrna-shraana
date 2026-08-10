function loadSavedFlow(){try{return JSON.parse(localStorage.getItem('bahrna_orderflow')||'null')}catch(e){return null}}
const savedFlow=loadSavedFlow();
const OrderFlow={
 cart: JSON.parse(localStorage.getItem('bahrna_cart')||'null') || [{id:'demo-hamour',name:'هامور محلي',price:49.90,qty:2}],
 cut:savedFlow?.cut||{name:'كامل',fee:0},
 packaging:savedFlow?.packaging||{name:'بدون ثلج',fee:0},
 keepHeadBones:savedFlow?.keepHeadBones??true,
 address:savedFlow?.address||{emirate:'دبي',area:'',address:''},
 slot:savedFlow?.slot||'',
 deliveryFee:10,
 vatRate:0.05
};
function persistFlow(){localStorage.setItem('bahrna_orderflow',JSON.stringify(OrderFlow))}
function saveCart(){localStorage.setItem('bahrna_cart',JSON.stringify(OrderFlow.cart));persistFlow()}
function money(n){return 'AED '+Number(n).toFixed(2)}
function cartSubtotal(){return OrderFlow.cart.reduce((s,x)=>s+Number(x.price)*Number(x.qty),0)}
function calcTotals(){const subtotal=cartSubtotal(),prep=Number(OrderFlow.cut.fee||0),pack=Number(OrderFlow.packaging.fee||0),delivery=Number(OrderFlow.deliveryFee||0),vat=(subtotal+prep+pack+delivery)*OrderFlow.vatRate,total=subtotal+prep+pack+delivery+vat;return{subtotal,prep,pack,delivery,vat,total}}
function renderCart(){const wrap=document.getElementById('cartRows');if(!wrap)return;wrap.innerHTML=OrderFlow.cart.map((x,i)=>`<div class="cart-item"><div class="cart-thumb">🐟</div><div><strong>${x.name}</strong><div class="muted">${money(x.price)} / كجم</div><div class="stepper"><button onclick="changeQty(${i},-1)">−</button><strong>${x.qty} كجم</strong><button onclick="changeQty(${i},1)">+</button></div></div><div><strong>${money(x.price*x.qty)}</strong><br><button class="btn small" onclick="removeItem(${i})">حذف</button></div></div>`).join('');const t=calcTotals();if(document.getElementById('cartSubtotal'))document.getElementById('cartSubtotal').textContent=money(t.subtotal);if(document.getElementById('cartTotal'))document.getElementById('cartTotal').textContent=money(t.total)}
function changeQty(i,d){OrderFlow.cart[i].qty=Math.max(1,Number(OrderFlow.cart[i].qty)+d);saveCart();renderCart();renderSummary()}
function removeItem(i){OrderFlow.cart.splice(i,1);saveCart();renderCart();renderSummary()}
function chooseCut(el,name,fee){document.querySelectorAll('[data-cut]').forEach(x=>x.classList.remove('active'));el.classList.add('active');OrderFlow.cut={name,fee:Number(fee)};persistFlow();const v=document.getElementById('cutVideoTitle');if(v)v.textContent='فيديو توضيحي: '+name;renderSummary()}
function choosePack(el,name,fee){document.querySelectorAll('[data-pack]').forEach(x=>x.classList.remove('active'));el.classList.add('active');OrderFlow.packaging={name,fee:Number(fee)};persistFlow();renderSummary()}
function setKeep(v){OrderFlow.keepHeadBones=v;persistFlow();renderSummary()}
function renderSummary(){const t=calcTotals();const vals={sumSubtotal:t.subtotal,sumPrep:t.prep,sumPack:t.pack,sumDelivery:t.delivery,sumVat:t.vat,sumTotal:t.total};Object.entries(vals).forEach(([id,val])=>{const el=document.getElementById(id);if(el)el.textContent=money(val)});const p=document.getElementById('prepText');if(p)p.textContent=OrderFlow.cut.name+' • '+OrderFlow.packaging.name+' • '+(OrderFlow.keepHeadBones?'مع الرأس والعظم':'بدون الرأس والعظم')}
function continueToDelivery(){persistFlow();location.href='delivery.html'}
function restoreDelivery(){const em=document.getElementById('emirate'),ar=document.getElementById('area'),ad=document.getElementById('address'),sl=document.getElementById('slot');if(em&&OrderFlow.address.emirate)em.value=OrderFlow.address.emirate;if(ar)ar.value=OrderFlow.address.area||'';if(ad)ad.value=OrderFlow.address.address||'';if(sl&&OrderFlow.slot)sl.value=OrderFlow.slot}
function confirmDelivery(){OrderFlow.address={emirate:document.getElementById('emirate').value,area:document.getElementById('area').value,address:document.getElementById('address').value};OrderFlow.slot=document.getElementById('slot').value;persistFlow();location.href='payment.html'}

async function createPilotOrder(){
 const btn=document.getElementById('confirmOrderBtn');
 try{
  if(btn){btn.disabled=true;btn.textContent='جاري تسجيل الطلب...'}
  persistFlow();const t=calcTotals();
  if(!window.Bahrna?.configured){return createLocalFallback(t,'الموقع يعمل في وضع Demo لأن Supabase غير متصل.')}
  const user=await Bahrna.getCurrentUser();
  if(!user){localStorage.setItem('bahrna_return_after_login','payment.html');alert('لإنشاء طلب حقيقي محفوظ في قاعدة البيانات، يرجى تسجيل الدخول أو إنشاء حساب أولاً.');location.href='login.html';return}
  const dbOrder=await Bahrna.createOrder(OrderFlow,t);
  const order={orderNo:dbOrder.order_no,status:dbOrder.status||'pending',isReal:true,createdAt:dbOrder.created_at,items:OrderFlow.cart,cut:OrderFlow.cut,packaging:OrderFlow.packaging,keepHeadBones:OrderFlow.keepHeadBones,address:OrderFlow.address,slot:OrderFlow.slot,total:Number(dbOrder.total)};
  localStorage.setItem('bahrna_last_order',JSON.stringify(order));
  location.href='confirmation.html';
 }catch(e){
  console.error(e);if(e.message==='LOGIN_REQUIRED'){alert('يرجى تسجيل الدخول أولاً.');location.href='login.html';return}
  alert('تعذر تسجيل الطلب في قاعدة البيانات: '+(e.message||e));
  if(btn){btn.disabled=false;btn.textContent='تأكيد الطلب التجريبي'}
 }
}
function createLocalFallback(t,note){const order={orderNo:'DEMO-'+Date.now().toString().slice(-8),status:'confirmed',isReal:false,createdAt:new Date().toISOString(),items:OrderFlow.cart,cut:OrderFlow.cut,packaging:OrderFlow.packaging,keepHeadBones:OrderFlow.keepHeadBones,address:OrderFlow.address,slot:OrderFlow.slot,total:t.total,note};localStorage.setItem('bahrna_last_order',JSON.stringify(order));location.href='confirmation.html'}

function renderConfirmation(){const o=JSON.parse(localStorage.getItem('bahrna_last_order')||'null');if(!o)return;const no=document.getElementById('orderNo'),tot=document.getElementById('orderTotal'),d=document.getElementById('deliveryText'),badge=document.getElementById('orderMode');if(no)no.textContent=o.orderNo;if(tot)tot.textContent=money(o.total);if(d)d.textContent=(o.address?.emirate||'')+' • '+(o.address?.area||'')+' • '+(o.slot||'موعد يحدد لاحقًا');if(badge)badge.textContent=o.isReal?'✓ محفوظ في Supabase — الدفع غير محصل':'وضع Demo محلي'}
async function renderTracking(){const local=JSON.parse(localStorage.getItem('bahrna_last_order')||'null');if(!local)return;let o=local;if(local.isReal&&window.Bahrna?.configured){const fresh=await Bahrna.getOrderByNo(local.orderNo);if(fresh)o={...local,status:fresh.status||fresh.tracking_status||local.status}}
 const no=document.getElementById('trackOrderNo');if(no)no.textContent=o.orderNo;const flow=['pending','confirmed','preparing','out_for_delivery','delivered'];let current=flow.indexOf(o.status);if(current<0)current=0;document.querySelectorAll('.track-step').forEach((el,i)=>{el.classList.remove('done','current');if(i<current)el.classList.add('done');else if(i===current)el.classList.add('current')});const cs=document.getElementById('currentStatus');if(cs)cs.textContent={pending:'بانتظار تأكيد الطلب',confirmed:'تم تأكيد الطلب',preparing:'جاري التجهيز',out_for_delivery:'خرج للتوصيل',delivered:'تم التسليم',cancelled:'تم إلغاء الطلب'}[o.status]||o.status;const sim=document.getElementById('simulateBtn');const note=document.getElementById('trackingNote');if(local.isReal){if(sim)sim.style.display='none';if(note)note.textContent='هذه الحالة مقروءة من قاعدة بيانات بحرنا وشراعنا. عند ربط شركة التوصيل ستتحدث آليًا من المورد وشركة التوصيل.'}}
function advanceTracking(){const o=JSON.parse(localStorage.getItem('bahrna_last_order')||'null');if(!o||o.isReal)return;const flow=['confirmed','preparing','out_for_delivery','delivered'];let i=flow.indexOf(o.status);if(i<flow.length-1)o.status=flow[i+1];localStorage.setItem('bahrna_last_order',JSON.stringify(o));location.reload()}
document.addEventListener('DOMContentLoaded',()=>{renderCart();renderSummary();restoreDelivery();renderConfirmation();renderTracking()});

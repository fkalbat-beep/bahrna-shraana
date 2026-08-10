
const TrustDemo={
 stats:{completedOrders:1284,verifiedReviews:436,avgRating:4.8,activeSuppliers:37},
 productStats:{
  "هامور محلي":{purchases:126,last24h:23,best7d:46.90,history:[52.9,51.5,49.9,48.9,47.5,49.0,46.9],rating:4.9,reviews:88},
  "كنعد":{purchases:214,last24h:31,best7d:38.50,history:[43.9,42.0,41.5,40.9,39.9,39.5,38.5],rating:4.8,reviews:121},
  "شعري":{purchases:167,last24h:18,best7d:26.90,history:[30.5,29.9,29.4,28.9,28.5,27.9,26.9],rating:4.7,reviews:76},
  "روبيان كبير":{purchases:98,last24h:15,best7d:34.90,history:[38.9,38.0,37.5,36.9,36.0,35.5,34.9],rating:4.9,reviews:64}
 },
 reviews:[
  {name:"م.س",product:"هامور محلي",rating:5,comment:"المنتج طازج والتغليف ممتاز ووصل في الموعد.",verified:true},
  {name:"أ.ع",product:"كنعد",rating:5,comment:"السعر واضح والتجهيز كان مطابقًا للاختيار.",verified:true},
  {name:"مطعم تجريبي",product:"شعري",rating:4,comment:"تجربة جيدة جدًا ونحتاج نافذة توصيل أبكر للجملة.",verified:true}
 ],
 loyalty:{points:1450,tier:"بحّار ذهبي",nextTier:2000,referral:"BAHRNA-F88",coupons:[
   {code:"WELCOME10",title:"خصم ترحيبي",value:"10%",active:true},
   {code:"ICEFREE",title:"تغليف مع ثلج مجاني",value:"AED 3",active:true}
 ]}
};
function renderTrustHome(){
 if(document.getElementById("trustOrders"))document.getElementById("trustOrders").textContent=TrustDemo.stats.completedOrders.toLocaleString();
 if(document.getElementById("trustReviews"))document.getElementById("trustReviews").textContent=TrustDemo.stats.verifiedReviews.toLocaleString();
 if(document.getElementById("trustRating"))document.getElementById("trustRating").textContent=TrustDemo.stats.avgRating.toFixed(1)+"/5";
 if(document.getElementById("trustSuppliers"))document.getElementById("trustSuppliers").textContent=TrustDemo.stats.activeSuppliers;
 if(document.getElementById("reviewList"))document.getElementById("reviewList").innerHTML=TrustDemo.reviews.map(r=>`<div class="review-card"><div class="stars">${"★".repeat(r.rating)}${"☆".repeat(5-r.rating)}</div><h4>${r.product}</h4><p>${r.comment}</p><span class="verified-purchase">✓ Verified Purchase</span><p class="muted small">${r.name}</p></div>`).join("");
}
function renderLoyalty(){
 if(!document.getElementById("points"))return;
 const l=TrustDemo.loyalty;document.getElementById("points").textContent=l.points.toLocaleString();
 document.getElementById("tier").textContent=l.tier;
 document.getElementById("nextTier").textContent=(l.nextTier-l.points)+" نقطة للمستوى التالي";
 document.getElementById("refCode").value=l.referral;
 document.getElementById("couponList").innerHTML=l.coupons.map(c=>`<div class="card"><strong>${c.title}</strong><div class="price" style="font-size:20px">${c.value}</div><span class="badge">${c.code}</span></div>`).join("");
}
function copyReferral(){navigator.clipboard?.writeText(document.getElementById("refCode").value);alert("تم نسخ كود الإحالة")}
function renderProductTrust(name){
 const p=TrustDemo.productStats[name];if(!p)return;
 document.getElementById("purchaseCount").textContent=p.purchases;
 document.getElementById("last24").textContent=p.last24h;
 document.getElementById("productRating").textContent=p.rating+"/5";
 document.getElementById("best7d").textContent="AED "+p.best7d.toFixed(2);
 const max=Math.max(...p.history),min=Math.min(...p.history);
 document.getElementById("priceHistory").innerHTML=p.history.map((v,i)=>`<div class="bar ${v===min?'best':''}" style="height:${30+((v-min)/(max-min||1))*70}%"><small>${v.toFixed(1)}</small></div>`).join("");
}
document.addEventListener("DOMContentLoaded",()=>{renderTrustHome();renderLoyalty()});

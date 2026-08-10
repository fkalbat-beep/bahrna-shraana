
const AuctionDemo = {
 auction:{
  id:"AUC-001", title:"هامور محلي طازج — 20 كجم", lotKg:20,
  startPrice:1000, minIncrement:25, participationFee:25, deposit:500,
  currentPrice:1250, status:"live", secondsLeft:470
 },
 qualified:true,
 paidParticipation:true,
 depositAuthorized:true,
 autoBidMax:0,
 bids:[
  {bidder:"B***27",amount:1250,time:"20:41:18"},
  {bidder:"M***04",amount:1225,time:"20:40:53"},
  {bidder:"R***91",amount:1200,time:"20:40:09"},
  {bidder:"B***27",amount:1175,time:"20:39:42"}
 ],
 bidderCode:"F***88"
};

function money(n){return "AED "+Number(n).toFixed(2)}
function renderAuction(){
 const a=AuctionDemo.auction;
 document.getElementById("currentPrice").textContent=money(a.currentPrice);
 document.getElementById("nextBid").value=(a.currentPrice+a.minIncrement).toFixed(0);
 document.getElementById("fee").textContent=money(a.participationFee);
 document.getElementById("deposit").textContent=money(a.deposit);
 document.getElementById("q1").className="qualify "+(AuctionDemo.qualified?"ok":"no");
 document.getElementById("q2").className="qualify "+(AuctionDemo.paidParticipation?"ok":"no");
 document.getElementById("q3").className="qualify "+(AuctionDemo.depositAuthorized?"ok":"no");
 document.getElementById("q1").innerHTML=(AuctionDemo.qualified?"✓":"×")+"<br><small>حساب موثق</small>";
 document.getElementById("q2").innerHTML=(AuctionDemo.paidParticipation?"✓":"×")+"<br><small>رسوم المشاركة</small>";
 document.getElementById("q3").innerHTML=(AuctionDemo.depositAuthorized?"✓":"×")+"<br><small>ضمان المزايدة</small>";
 document.getElementById("bidRows").innerHTML=AuctionDemo.bids.map((b,i)=>`<div class="bid-item"><div style="display:flex;gap:9px;align-items:center"><span class="rank">${i+1}</span><div><strong>${b.bidder}</strong><br><small class="muted">${b.time}</small></div></div><strong>${money(b.amount)}</strong></div>`).join("");
 const leaders=[...AuctionDemo.bids].sort((x,y)=>y.amount-x.amount);
 document.getElementById("leader1").textContent=leaders[0]?leaders[0].bidder+" — "+money(leaders[0].amount):"—";
 document.getElementById("leader2").textContent=leaders[1]?leaders[1].bidder+" — "+money(leaders[1].amount):"—";
 renderTimer();
}
function renderTimer(){
 let s=AuctionDemo.auction.secondsLeft; const m=Math.floor(s/60),sec=s%60;
 document.getElementById("min").textContent=String(m).padStart(2,"0");
 document.getElementById("sec").textContent=String(sec).padStart(2,"0");
}
function tick(){
 if(AuctionDemo.auction.status!=="live") return;
 if(AuctionDemo.auction.secondsLeft>0){AuctionDemo.auction.secondsLeft--;renderTimer()}
 else closeAuction();
}
function placeBid(){
 if(!(AuctionDemo.qualified&&AuctionDemo.paidParticipation&&AuctionDemo.depositAuthorized))return alert("يجب استكمال التأهيل المالي قبل المزايدة");
 const v=Number(document.getElementById("nextBid").value);
 const min=AuctionDemo.auction.currentPrice+AuctionDemo.auction.minIncrement;
 if(!v||v<min)return alert("الحد الأدنى للمزايدة الحالية هو "+money(min));
 AuctionDemo.auction.currentPrice=v;
 AuctionDemo.bids.unshift({bidder:AuctionDemo.bidderCode,amount:v,time:new Date().toLocaleTimeString("ar-AE",{hour:"2-digit",minute:"2-digit",second:"2-digit"})});
 if(AuctionDemo.auction.secondsLeft<=30) AuctionDemo.auction.secondsLeft+=120;
 simulateAutoBid();
 renderAuction();
}
function setAutoBid(){
 const v=Number(document.getElementById("autoMax").value);
 if(v<=AuctionDemo.auction.currentPrice)return alert("ضع حدًا أعلى أكبر من السعر الحالي");
 AuctionDemo.autoBidMax=v;alert("تم حفظ Auto Bid حتى "+money(v));
}
function simulateAutoBid(){
 if(AuctionDemo.autoBidMax>0 && AuctionDemo.auction.currentPrice+AuctionDemo.auction.minIncrement<=AuctionDemo.autoBidMax){
   // Demo: competing bidder makes a bid, auto bid responds.
   const competitor=AuctionDemo.auction.currentPrice+AuctionDemo.auction.minIncrement;
   AuctionDemo.bids.unshift({bidder:"A***12",amount:competitor,time:new Date().toLocaleTimeString("ar-AE")});
   const auto=competitor+AuctionDemo.auction.minIncrement;
   AuctionDemo.auction.currentPrice=auto;
   AuctionDemo.bids.unshift({bidder:AuctionDemo.bidderCode,amount:auto,time:new Date().toLocaleTimeString("ar-AE")});
 }
}
function openQualification(){document.getElementById("qualModal").classList.add("show")}
function closeQualification(){document.getElementById("qualModal").classList.remove("show")}
function completeQualification(){
 AuctionDemo.qualified=true;AuctionDemo.paidParticipation=true;AuctionDemo.depositAuthorized=true;closeQualification();renderAuction();
}
function closeAuction(){
 AuctionDemo.auction.status="closed";
 document.getElementById("bidButton").disabled=true;document.getElementById("bidButton").textContent="المزاد مغلق";
 const sorted=[...AuctionDemo.bids].sort((a,b)=>b.amount-a.amount);
 const winner=sorted[0], second=sorted.find(x=>x.bidder!==winner.bidder);
 document.getElementById("resultBox").style.display="block";
 document.getElementById("winnerText").textContent=winner?winner.bidder+" — "+money(winner.amount):"—";
 document.getElementById("secondText").textContent=second?second.bidder+" — "+money(second.amount):"—";
}
function simulateFailedPayment(){
 const sorted=[...AuctionDemo.bids].sort((a,b)=>b.amount-a.amount);
 if(sorted.length<2)return;
 const first=sorted[0]; const next=sorted.find(x=>x.bidder!==first.bidder);
 document.getElementById("fallbackText").textContent="فشل تحصيل الفائز "+first.bidder+" → تنتقل الترسية تلقائيًا إلى "+(next?next.bidder:"البديل")+" وفق شروط المزاد.";
 document.getElementById("fallbackText").style.display="block";
}
document.addEventListener("DOMContentLoaded",()=>{renderAuction();setInterval(tick,1000)});

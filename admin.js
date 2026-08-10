
const AdminDemo = {
 suppliers:[
  {id:1,name:"Fresh Express",emirate:"دبي",verified:true,license:"CN-10458",trn:"100000001"},
  {id:2,name:"Wild Harbour",emirate:"دبي",verified:false,license:"CN-20411",trn:"100000002"},
  {id:3,name:"Mohsen & Sajwani",emirate:"دبي",verified:true,license:"CN-30117",trn:"100000003"}
 ],
 products:[
  {id:1,name:"هامور محلي",supplier:"Fresh Express",price:49.90,stock:25,active:true},
  {id:2,name:"كنعد",supplier:"Wild Harbour",price:40.90,stock:42,active:true},
  {id:3,name:"شعري",supplier:"Mohsen & Sajwani",price:28.90,stock:18,active:true},
  {id:4,name:"روبيان كبير",supplier:"Fresh Express",price:36.90,stock:30,active:true}
 ],
 orders:[
  {no:"ORD-DEMO-001",customer:"عميل تجريبي",total:149.70,status:"preparing"},
  {no:"ORD-DEMO-002",customer:"مطعم تجريبي",total:820.00,status:"confirmed"},
  {no:"ORD-DEMO-003",customer:"عميل تجريبي 2",total:98.00,status:"delivered"}
 ],
 auctions:[
  {title:"هامور 20 كجم",price:1250,status:"scheduled",bidders:8},
  {title:"كنعد 50 كجم",price:2400,status:"draft",bidders:0}
 ],
 reviews:[
  {product:"هامور محلي",rating:5,comment:"تقييم تجريبي فقط",verified:false}
 ]
};

function money(n){return "AED "+Number(n).toFixed(2)}
function showPanel(id,el){
 document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
 document.getElementById(id).classList.add("active");
 document.querySelectorAll(".sidebar a").forEach(a=>a.classList.remove("active"));
 if(el) el.classList.add("active");
}
function renderAdmin(){
 document.getElementById("supCount").textContent=AdminDemo.suppliers.length;
 document.getElementById("prodCount").textContent=AdminDemo.products.length;
 document.getElementById("ordCount").textContent=AdminDemo.orders.length;
 document.getElementById("gmv").textContent=money(AdminDemo.orders.reduce((s,o)=>s+o.total,0));
 document.getElementById("supplierRows").innerHTML=AdminDemo.suppliers.map(s=>`<tr><td>${s.name}</td><td>${s.emirate}</td><td>${s.license}</td><td>${s.trn}</td><td>${s.verified?'<span class="status ok">معتمد</span>':'<span class="status wait">قيد المراجعة</span>'}</td><td><button class="btn btn-primary small" onclick="toggleSupplier(${s.id})">${s.verified?'إيقاف':'اعتماد'}</button></td></tr>`).join("");
 document.getElementById("productRows").innerHTML=AdminDemo.products.map(p=>`<tr><td>${p.name}</td><td>${p.supplier}</td><td>${money(p.price)}</td><td>${p.stock} كجم</td><td>${p.active?'نشط':'موقوف'}</td><td><button class="btn btn-primary small" onclick="editPrice(${p.id})">تعديل السعر</button></td></tr>`).join("");
 document.getElementById("orderRows").innerHTML=AdminDemo.orders.map(o=>`<tr><td>${o.no}</td><td>${o.customer}</td><td>${money(o.total)}</td><td>${o.status}</td><td><button class="btn btn-primary small" onclick="advanceOrder('${o.no}')">تحديث الحالة</button></td></tr>`).join("");
 document.getElementById("auctionRows").innerHTML=AdminDemo.auctions.map((a,i)=>`<tr><td>${a.title}</td><td>${money(a.price)}</td><td>${a.bidders}</td><td>${a.status}</td><td><button class="btn btn-primary small" onclick="launchAuction(${i})">إدارة</button></td></tr>`).join("");
}
function toggleSupplier(id){const s=AdminDemo.suppliers.find(x=>x.id===id);s.verified=!s.verified;renderAdmin()}
function editPrice(id){const p=AdminDemo.products.find(x=>x.id===id);const v=prompt("السعر الجديد لكل كجم",p.price);if(v!==null&&!isNaN(v)){p.price=Number(v);renderAdmin()}}
function advanceOrder(no){const o=AdminDemo.orders.find(x=>x.no===no);const flow=["confirmed","preparing","out_for_delivery","delivered"];let i=flow.indexOf(o.status);o.status=flow[Math.min(i+1,flow.length-1)];renderAdmin()}
function launchAuction(i){alert("صفحة إدارة المزاد ستربط لاحقًا بقاعدة البيانات والدفع المضمون. الحالة الحالية: "+AdminDemo.auctions[i].status)}
function addProduct(){
 const name=document.getElementById("pname").value.trim(), price=Number(document.getElementById("pprice").value), stock=Number(document.getElementById("pstock").value);
 if(!name||isNaN(price)||isNaN(stock)) return alert("أكمل بيانات المنتج");
 AdminDemo.products.push({id:Date.now(),name,supplier:"مورد تجريبي",price,stock,active:true});renderAdmin();showPanel("productsPanel");
}
document.addEventListener("DOMContentLoaded",renderAdmin);

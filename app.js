
const C=window.BAHRNA_CONFIG||{};const configured=C.SUPABASE_URL&&!C.SUPABASE_URL.includes("YOUR_")&&C.SUPABASE_ANON_KEY&&!C.SUPABASE_ANON_KEY.includes("YOUR_");
let sb=null;if(configured&&window.supabase)sb=window.supabase.createClient(C.SUPABASE_URL,C.SUPABASE_ANON_KEY);
const demoProducts=[
{id:"demo-hamour",name_ar:"هامور محلي",price_per_kg:49.90,stock_kg:25,origin:"الإمارات",active:true},
{id:"demo-kingfish",name_ar:"كنعد",price_per_kg:40.90,stock_kg:42,origin:"الخليج العربي",active:true},
{id:"demo-shaari",name_ar:"شعري",price_per_kg:28.90,stock_kg:18,origin:"الإمارات",active:true},
{id:"demo-prawn",name_ar:"روبيان كبير",price_per_kg:36.90,stock_kg:30,origin:"الإمارات",active:true}];
async function getProducts(){if(!sb)return demoProducts;const {data,error}=await sb.from("products").select("*").eq("active",true).order("price_per_kg");return error?demoProducts:data}
async function signUp(email,password,full_name,role="customer"){if(!sb)throw new Error("ضع بيانات Supabase في config.js أولاً");const {data,error}=await sb.auth.signUp({email,password,options:{data:{full_name,role}}});if(error)throw error;return data}
async function signIn(email,password){if(!sb)throw new Error("ضع بيانات Supabase في config.js أولاً");const {data,error}=await sb.auth.signInWithPassword({email,password});if(error)throw error;return data}
window.Bahrna={getProducts,signUp,signIn,configured};

function getDemoSupplierOffers(){
 const saved=localStorage.getItem("bahrna_supplier_offers");
 if(saved){try{return JSON.parse(saved)}catch(e){}}
 return [
  {id:1,name:"هامور محلي",qty:25,retail:49.90,wholesale:45.00,auction:false,status:"active",arrived:"05:30",supplier:"Fresh Express",origin:"الإمارات"},
  {id:2,name:"كنعد",qty:42,retail:40.90,wholesale:37.50,auction:true,status:"active",arrived:"06:10",supplier:"Wild Harbour",origin:"الخليج العربي"},
  {id:3,name:"شعري",qty:18,retail:28.90,wholesale:25.50,auction:false,status:"paused",arrived:"05:50",supplier:"Mohsen & Sajwani",origin:"الإمارات"}
 ];
}
function saveDemoSupplierOffers(v){localStorage.setItem("bahrna_supplier_offers",JSON.stringify(v))}
async function getMarketOffers(){
 if(sb){
   const {data,error}=await sb.from("products").select("id,name_ar,origin,price_per_kg,wholesale_price_per_kg,stock_kg,active,supplier_id").eq("active",true);
   if(!error && data) return data.map(x=>({id:x.id,name:x.name_ar,qty:x.stock_kg,retail:Number(x.price_per_kg),wholesale:Number(x.wholesale_price_per_kg||0),status:"active",origin:x.origin||"",supplier:"مورد موثق"}));
 }
 return getDemoSupplierOffers().filter(x=>x.status==="active");
}
window.Bahrna.getMarketOffers=getMarketOffers;
window.Bahrna.getDemoSupplierOffers=getDemoSupplierOffers;
window.Bahrna.saveDemoSupplierOffers=saveDemoSupplierOffers;

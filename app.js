const C=window.BAHRNA_CONFIG||{};
const configured=!!(C.SUPABASE_URL&&!C.SUPABASE_URL.includes('YOUR_')&&C.SUPABASE_ANON_KEY&&!C.SUPABASE_ANON_KEY.includes('YOUR_'));
let sb=null;
if(configured&&window.supabase) sb=window.supabase.createClient(C.SUPABASE_URL,C.SUPABASE_ANON_KEY);

const demoProducts=[
 {id:'demo-hamour',name_ar:'هامور محلي',price_per_kg:49.90,stock_kg:25,origin:'الإمارات',active:true},
 {id:'demo-kingfish',name_ar:'كنعد',price_per_kg:40.90,stock_kg:42,origin:'الخليج العربي',active:true},
 {id:'demo-shaari',name_ar:'شعري',price_per_kg:28.90,stock_kg:18,origin:'الإمارات',active:true},
 {id:'demo-prawn',name_ar:'روبيان كبير',price_per_kg:36.90,stock_kg:30,origin:'الإمارات',active:true}
];

async function getProducts(){
 if(!sb) return demoProducts;
 const {data,error}=await sb.from('products').select('*').eq('active',true).order('price_per_kg');
 if(error){console.warn(error);return demoProducts}
 return data||[];
}

async function signUp(email,password,full_name,role='customer'){
 if(!sb) throw new Error('اتصال Supabase غير مفعّل');
 const {data,error}=await sb.auth.signUp({email,password,options:{data:{full_name,role}}});
 if(error) throw error;
 return data;
}
async function signIn(email,password){
 if(!sb) throw new Error('اتصال Supabase غير مفعّل');
 const {data,error}=await sb.auth.signInWithPassword({email,password});
 if(error) throw error;
 return data;
}
async function getCurrentUser(){
 if(!sb) return null;
 const {data,error}=await sb.auth.getUser();
 if(error) return null;
 return data?.user||null;
}

function getDemoSupplierOffers(){
 const saved=localStorage.getItem('bahrna_supplier_offers');
 if(saved){try{return JSON.parse(saved)}catch(e){}}
 return [
  {id:1,name:'هامور محلي',qty:25,retail:49.90,wholesale:45.00,auction:false,status:'active',arrived:'05:30',supplier:'Fresh Express',origin:'الإمارات'},
  {id:2,name:'كنعد',qty:42,retail:40.90,wholesale:37.50,auction:true,status:'active',arrived:'06:10',supplier:'Wild Harbour',origin:'الخليج العربي'},
  {id:3,name:'شعري',qty:18,retail:28.90,wholesale:25.50,auction:false,status:'paused',arrived:'05:50',supplier:'Mohsen & Sajwani',origin:'الإمارات'}
 ];
}
function saveDemoSupplierOffers(v){localStorage.setItem('bahrna_supplier_offers',JSON.stringify(v))}
async function getMarketOffers(){
 if(sb){
   const {data,error}=await sb.from('products').select('id,name_ar,origin,price_per_kg,wholesale_price_per_kg,stock_kg,active,supplier_id').eq('active',true);
   if(!error&&data) return data.map(x=>({id:x.id,name:x.name_ar,qty:Number(x.stock_kg),retail:Number(x.price_per_kg),wholesale:Number(x.wholesale_price_per_kg||0),status:'active',origin:x.origin||'',supplier:'مورد موثق',isReal:true}));
 }
 return getDemoSupplierOffers().filter(x=>x.status==='active').map(x=>({...x,isReal:false}));
}

async function createOrder(orderFlow,totals){
 if(!sb) throw new Error('قاعدة البيانات غير متصلة');
 const user=await getCurrentUser();
 if(!user) throw new Error('LOGIN_REQUIRED');
 if(!orderFlow.cart?.length) throw new Error('السلة فارغة');

 const orderPayload={
   user_id:user.id,
   status:'pending',
   subtotal:totals.subtotal,
   preparation_fee:totals.prep,
   packaging_fee:totals.pack,
   delivery_fee:totals.delivery,
   vat:totals.vat,
   total:totals.total,
   delivery_address:orderFlow.address||{},
   delivery_slot:null,
   payment_method:'pilot_no_charge',
   payment_status:'unpaid',
   preparation_summary:{cut:orderFlow.cut,packaging:orderFlow.packaging,slot:orderFlow.slot||''},
   keep_head_bones:!!orderFlow.keepHeadBones,
   tracking_status:'confirmed'
 };
 const {data:order,error:orderError}=await sb.from('orders').insert(orderPayload).select('id,order_no,status,total,delivery_address,tracking_status,created_at').single();
 if(orderError) throw orderError;

 const items=orderFlow.cart.map(x=>({
   order_id:order.id,
   product_id:(x.id&&String(x.id).startsWith('demo-'))?null:x.id,
   product_name:x.name,
   qty_kg:Number(x.qty),
   unit_price:Number(x.price),
   keep_head_bones:!!orderFlow.keepHeadBones,
   line_total:Number(x.qty)*Number(x.price)
 }));
 const {error:itemError}=await sb.from('order_items').insert(items);
 if(itemError) throw itemError;
 return order;
}

async function getOrderByNo(orderNo){
 if(!sb||!orderNo) return null;
 const {data,error}=await sb.from('orders').select('id,order_no,status,total,delivery_address,tracking_status,created_at').eq('order_no',orderNo).single();
 if(error){console.warn(error);return null}
 return data;
}

window.Bahrna={
 configured,client:sb,getProducts,getMarketOffers,getDemoSupplierOffers,saveDemoSupplierOffers,
 signUp,signIn,getCurrentUser,createOrder,getOrderByNo
};

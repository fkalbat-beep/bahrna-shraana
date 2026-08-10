# BAHRNA & SHRAANA — MVP V1 (Zero-Cost)

1. افتح home.html لتجربة Demo بدون قاعدة بيانات.
2. أنشئ مشروع Supabase مجاني.
3. نفّذ sql/001_schema.sql ثم sql/002_seed_demo.sql.
4. ضع Project URL و anon key في config.js.
5. أعد فتح home.html.

مهم: لا تضع service_role key داخل الموقع.


## لوحة الإدارة
افتح `admin.html` لتجربة إدارة الموردين والمنتجات والأسعار والطلبات والمزادات في Demo Mode.


## Supplier Dashboard
افتح `supplier.html` لتجربة إضافة صيد اليوم، الأسعار، المخزون، الجملة والمزاد.


## V4
- عروض الموردين في Demo أصبحت تتغذى إلى لوحة الأسعار والكتالوج عبر localStorage.
- `buyer.html`: لوحة الشركات والمطاعم والفنادق والجهات المؤسسية مع أسعار جملة وRFQ.


## V5 — شراعنا للمزادات
- تأهيل المزايد ورسوم المشاركة والضمان كمحاكاة.
- مزايدات مباشرة + Auto Bid.
- تمديد دقيقتين عند مزايدة آخر 30 ثانية.
- حفظ المركزين الأول والثاني.
- محاكاة انتقال الترسية للثاني عند فشل الدفع.
- `sql/003_auction_extension.sql` يضيف بنية المشاركين وحالة الدفع.


## V6 — الطلب والتوصيل
- cart.html السلة
- checkout.html التقطيع والتغليف والرأس والعظم
- delivery.html العنوان ونافذة التوصيل
- payment.html دفع تجريبي بدون بيانات بطاقة
- confirmation.html تأكيد الطلب
- tracking.html تتبع الطلب
- sql/004_order_delivery_extension.sql لبنية التتبع وحالة الطلب


## V7 — Trust & Loyalty
- Verified Purchase Reviews
- عدد مرات شراء كل منتج وآخر 24 ساعة
- أقل سعر خلال 7 أيام وسجل السعر
- Loyalty Wallet + Points + Tiers
- Referral code + coupons demo
- sql/005_trust_loyalty_extension.sql


## PILOT RELEASE V1
أضيفت صفحات الشروط والخصوصية والاسترجاع وعن المنصة، وتقرير QA للروابط، ودليل نشر Pilot بتكلفة صفرية. السياسات مسودات أولية وتحتاج مراجعة قانونية قبل الإطلاق التجاري.

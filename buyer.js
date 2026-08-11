/* =========================================================
   BAHRNA & SHRAANA
   BUSINESS BUYER DASHBOARD

   Wholesale
   RFQ
   Supplier Quotes
   B2B Orders
========================================================= */


const BuyerData = {

  rfqs: [],

  quotes: [],

  orders: []

};


/* =========================================================
   التنقل
========================================================= */

function showBuyerPanel(id, el) {

  document
    .querySelectorAll(".buyer-panel")
    .forEach(
      x => x.classList.remove("active")
    );


  const panel =
    document.getElementById(id);


  if (panel) {

    panel.classList.add("active");

  }


  document
    .querySelectorAll(".buyer-sidebar a")
    .forEach(
      a => a.classList.remove("active")
    );


  if (el) {

    el.classList.add("active");

  }

}


/* =========================================================
   أدوات عامة
========================================================= */

function money(n) {

  return "AED " +
    Number(n || 0).toFixed(2);

}


function formatDate(value) {

  if (!value) {

    return "—";

  }


  try {

    return new Date(value)
      .toLocaleDateString(
        "ar-AE",
        {
          year: "numeric",
          month: "short",
          day: "numeric"
        }
      );

  } catch (e) {

    return value;

  }

}


function rfqStatusLabel(status) {

  const labels = {

    open:
      "مفتوح",

    quoted:
      "وردت عروض",

    awarded:
      "تم اختيار المورد",

    closed:
      "تم التحويل إلى طلب",

    cancelled:
      "ملغي"

  };


  return labels[status] || status;

}


function quoteStatusLabel(status) {

  const labels = {

    submitted:
      "مقدم",

    accepted:
      "مقبول",

    rejected:
      "مرفوض",

    withdrawn:
      "مسحوب"

  };


  return labels[status] || status;

}


function orderStatusLabel(status) {

  const labels = {

    pending:
      "بانتظار التأكيد",

    confirmed:
      "تم التأكيد",

    preparing:
      "جاري التجهيز",

    out_for_delivery:
      "خرج للتوصيل",

    delivered:
      "تم التسليم",

    cancelled:
      "ملغي"

  };


  return labels[status] || status;

}


function quoteStatusClass(status) {

  if (status === "accepted") {

    return "status ok";

  }


  if (
    status === "rejected" ||
    status === "withdrawn"
  ) {

    return "status wait";

  }


  return "status ok";

}


/* =========================================================
   المستخدم الحالي
========================================================= */

async function getBuyerUser() {

  if (
    !window.Bahrna ||
    !Bahrna.client
  ) {

    throw new Error(
      "قاعدة البيانات غير متصلة"
    );

  }


  const user =
    await Bahrna.getCurrentUser();


  if (!user) {

    localStorage.setItem(
      "bahrna_return_after_login",
      "buyer.html"
    );


    alert(
      "يرجى تسجيل الدخول لاستخدام حساب المشتري المؤسسي"
    );


    location.href =
      "login.html";


    return null;

  }


  return user;

}


/* =========================================================
   تحميل RFQ
========================================================= */

async function loadBuyerRFQs(user) {

  const sb =
    Bahrna.client;


  const {
    data,
    error
  } = await sb

    .from("rfqs")

    .select(`
      id,
      rfq_no,
      buyer_id,
      company_id,
      item_name,
      quantity_kg,
      delivery_emirate,
      delivery_date,
      notes,
      status,
      created_at,
      updated_at
    `)

    .eq(
      "buyer_id",
      user.id
    )

    .order(
      "created_at",
      {
        ascending: false
      }
    );


  if (error) {

    console.error(
      "خطأ تحميل RFQ:",
      error
    );


    throw error;

  }


  BuyerData.rfqs =
    data || [];

}


/* =========================================================
   تحميل عروض الموردين
========================================================= */

async function loadBuyerQuotes() {

  const sb =
    Bahrna.client;


  const {
    data,
    error
  } = await sb

    .from("rfq_quotes")

    .select(`
      id,
      rfq_id,
      supplier_id,
      price_per_kg,
      available_qty_kg,
      delivery_days,
      notes,
      status,
      created_at,
      updated_at,
      supplier:suppliers (
        id,
        display_name,
        emirate,
        verified
      )
    `)

    .order(
      "created_at",
      {
        ascending: false
      }
    );


  if (error) {

    console.error(
      "خطأ تحميل عروض الموردين:",
      error
    );


    throw error;

  }


  BuyerData.quotes =
    data || [];

}


/* =========================================================
   تحميل طلبات المشتري
========================================================= */

async function loadBuyerOrders(user) {

  const sb =
    Bahrna.client;


  const {
    data,
    error
  } = await sb

    .from("orders")

    .select(`
      id,
      order_no,
      buyer_id,
      status,
      tracking_status,
      subtotal,
      delivery_fee,
      vat,
      total,
      created_at,
      order_items (
        product_id,
        product_name,
        qty_kg,
        unit_price,
        line_total
      )
    `)

    .eq(
      "buyer_id",
      user.id
    )

    .order(
      "created_at",
      {
        ascending: false
      }
    );


  if (error) {

    console.error(
      "خطأ تحميل طلبات المشتري:",
      error
    );


    /*
      في حال كان بعض الحقول الاختيارية
      غير موجود في نسخة الجدول الحالية،
      نعيد المحاولة بالحقول الأساسية.
    */

    const fallback =
      await sb

        .from("orders")

        .select(`
          id,
          order_no,
          status,
          tracking_status,
          total,
          created_at,
          order_items (
            product_name,
            qty_kg,
            unit_price,
            line_total
          )
        `)

        .order(
          "created_at",
          {
            ascending: false
          }
        );


    if (fallback.error) {

      console.error(
        "تعذر تحميل الطلبات:",
        fallback.error
      );


      BuyerData.orders = [];


      return;

    }


    BuyerData.orders =
      fallback.data || [];


    return;

  }


  BuyerData.orders =
    data || [];

}


/* =========================================================
   أسعار الجملة
========================================================= */

async function renderWholesaleOffers() {

  const wrap =
    document.getElementById(
      "wholesaleCards"
    );


  if (!wrap) {

    return;

  }


  try {

    const offers =
      await Bahrna.getMarketOffers();


    const wholesaleOffers =
      (offers || [])

        .filter(
          o =>
            Number(
              o.wholesale || 0
            ) > 0
        )

        .sort(
          (a, b) =>
            Number(a.wholesale) -
            Number(b.wholesale)
        );


    if (!wholesaleOffers.length) {

      wrap.innerHTML = `

        <div class="card">

          <p class="muted">
            لا توجد أسعار جملة متاحة حالياً.
          </p>

        </div>

      `;


      return;

    }


    wrap.innerHTML =
      wholesaleOffers

        .map(
          o => `

            <div class="card">

              <span class="badge">

                ${o.supplier || "مورد موثق"}

              </span>


              <h3>

                ${o.name}

              </h3>


              <div class="price">

                AED
                ${Number(o.wholesale).toFixed(2)}

                <small>
                  / كجم
                </small>

              </div>


              <p class="muted">

                متوفر
                ${Number(o.qty || 0)}
                كجم

                •

                Retail
                ${Number(o.retail || 0).toFixed(2)}

              </p>


              <button
                class="btn btn-primary"
                onclick='prefillRFQ(
                  ${JSON.stringify(o.name)},
                  ${Number(o.qty || 0)}
                )'>

                طلب كمية

              </button>

            </div>

          `
        )

        .join("");


  } catch (e) {

    console.error(
      "خطأ تحميل أسعار الجملة:",
      e
    );


    wrap.innerHTML = `

      <div class="card">

        <p class="muted">
          تعذر تحميل أسعار الجملة.
        </p>

      </div>

    `;

  }

}


/* =========================================================
   عدد العروض لكل RFQ
========================================================= */

function getQuoteCountForRFQ(rfqId) {

  return BuyerData.quotes
    .filter(
      q =>
        q.rfq_id === rfqId
    )
    .length;

}


/* =========================================================
   عرض RFQ
========================================================= */

function renderRFQs() {

  const rows =
    document.getElementById(
      "rfqRows"
    );


  const count =
    document.getElementById(
      "rfqCount"
    );


  if (count) {

    count.textContent =
      BuyerData.rfqs.length;

  }


  if (!rows) {

    return;

  }


  if (!BuyerData.rfqs.length) {

    rows.innerHTML = `

      <tr>

        <td colspan="6">

          لا توجد طلبات عروض أسعار حتى الآن.

        </td>

      </tr>

    `;


    return;

  }


  rows.innerHTML =
    BuyerData.rfqs

      .map(
        r => {

          const quoteCount =
            getQuoteCountForRFQ(
              r.id
            );


          return `

            <tr>

              <td>

                <strong>
                  ${r.rfq_no}
                </strong>

              </td>


              <td>

                ${r.item_name}

              </td>


              <td>

                ${Number(r.quantity_kg)}
                كجم

              </td>


              <td>

                ${r.delivery_emirate}

                ${
                  r.delivery_date

                    ? `

                      <br>

                      <small>

                        ${formatDate(r.delivery_date)}

                      </small>

                    `

                    : ""
                }

              </td>


              <td>

                <span class="status ok">

                  ${rfqStatusLabel(r.status)}

                </span>

              </td>


              <td>

                ${
                  quoteCount > 0

                    ? `

                      <button
                        class="btn btn-primary small"
                        onclick="openQuotesForRFQ('${r.id}')">

                        ${quoteCount}
                        عرض

                      </button>

                    `

                    : `

                      <span class="muted">

                        لا توجد عروض

                      </span>

                    `
                }

              </td>

            </tr>

          `;

        }
      )

      .join("");

}


/* =========================================================
   عرض عروض الموردين
========================================================= */

function renderBuyerQuotes(
  filterRfqId = null
) {

  const rows =
    document.getElementById(
      "buyerQuoteRows"
    );


  const summary =
    document.getElementById(
      "buyerQuoteSummary"
    );


  const count =
    document.getElementById(
      "quoteCount"
    );


  if (count) {

    count.textContent =
      BuyerData.quotes.length;

  }


  if (!rows) {

    return;

  }


  let quotes =
    [...BuyerData.quotes];


  if (filterRfqId) {

    quotes =
      quotes.filter(
        q =>
          q.rfq_id ===
          filterRfqId
      );

  }


  quotes.sort(
    (a, b) =>
      Number(a.price_per_kg) -
      Number(b.price_per_kg)
  );


  if (summary) {

    if (filterRfqId) {

      const rfq =
        BuyerData.rfqs.find(
          r =>
            r.id ===
            filterRfqId
        );


      summary.innerHTML = `

        <strong>

          ${
            rfq
              ? rfq.rfq_no
              : ""
          }

        </strong>

        ${
          rfq
            ? ` • ${rfq.item_name}`
            : ""
        }

        •

        عدد العروض:

        <strong>

          ${quotes.length}

        </strong>

      `;

    } else {

      summary.innerHTML = `

        إجمالي عروض الموردين:

        <strong>

          ${BuyerData.quotes.length}

        </strong>

      `;

    }

  }


  if (!quotes.length) {

    rows.innerHTML = `

      <tr>

        <td colspan="9">

          لا توجد عروض موردين حالياً.

        </td>

      </tr>

    `;


    return;

  }


  rows.innerHTML =
    quotes

      .map(
        q => {

          const rfq =
            BuyerData.rfqs.find(
              r =>
                r.id ===
                q.rfq_id
            );


          const supplierName =
            q.supplier?.display_name ||
            "مورد";


          const qty =
            Number(
              q.available_qty_kg || 0
            );


          const price =
            Number(
              q.price_per_kg || 0
            );


          const total =
            qty * price;


          return `

            <tr>

              <td>

                <strong>

                  ${rfq?.rfq_no || "—"}

                </strong>

              </td>


              <td>

                ${rfq?.item_name || "—"}

              </td>


              <td>

                ${supplierName}

                ${
                  q.supplier?.verified

                    ? `

                      <br>

                      <small>

                        ✓ مورد موثق

                      </small>

                    `

                    : ""
                }

              </td>


              <td>

                ${qty}
                كجم

              </td>


              <td>

                <strong>

                  ${money(price)}

                </strong>

              </td>


              <td>

                <strong>

                  ${money(total)}

                </strong>

              </td>


              <td>

                ${
                  Number(q.delivery_days) === 0

                    ? "نفس اليوم"

                    : Number(q.delivery_days) === 1

                      ? "خلال يوم"

                      : `${Number(q.delivery_days)} أيام`
                }

              </td>


              <td>

                <span
                  class="${quoteStatusClass(q.status)}">

                  ${quoteStatusLabel(q.status)}

                </span>

              </td>


              <td>

                <button
                  class="btn btn-primary small"
                  onclick="openQuoteDetails('${q.id}')">

                  التفاصيل

                </button>

              </td>

            </tr>

          `;

        }
      )

      .join("");

}


/* =========================================================
   فتح عروض RFQ
========================================================= */

function openQuotesForRFQ(
  rfqId
) {

  showBuyerPanel(
    "quotesPanel"
  );


  renderBuyerQuotes(
    rfqId
  );

}


/* =========================================================
   تفاصيل العرض
========================================================= */

function openQuoteDetails(
  quoteId
) {

  const quote =
    BuyerData.quotes.find(
      q =>
        q.id === quoteId
    );


  if (!quote) {

    alert(
      "تعذر العثور على العرض"
    );


    return;

  }


  const rfq =
    BuyerData.rfqs.find(
      r =>
        r.id === quote.rfq_id
    );


  const supplierName =
    quote.supplier?.display_name ||
    "مورد";


  const qty =
    Number(
      quote.available_qty_kg || 0
    );


  const price =
    Number(
      quote.price_per_kg || 0
    );


  const total =
    qty * price;


  document
    .getElementById(
      "selectedQuoteId"
    )
    .value =
      quote.id;


  document
    .getElementById(
      "selectedQuoteRfqId"
    )
    .value =
      quote.rfq_id;


  document
    .getElementById(
      "selectedQuoteRfqNo"
    )
    .value =
      rfq?.rfq_no || "";


  document
    .getElementById(
      "selectedQuoteProduct"
    )
    .value =
      rfq?.item_name || "";


  document
    .getElementById(
      "selectedQuoteSupplier"
    )
    .value =
      supplierName;


  document
    .getElementById(
      "selectedQuoteQty"
    )
    .value =
      qty + " كجم";


  document
    .getElementById(
      "selectedQuotePrice"
    )
    .value =
      money(price) +
      " / كجم";


  document
    .getElementById(
      "selectedQuoteTotal"
    )
    .value =
      money(total);


  document
    .getElementById(
      "selectedQuoteDelivery"
    )
    .value =

      Number(
        quote.delivery_days
      ) === 0

        ? "نفس اليوم"

        : Number(
            quote.delivery_days
          ) === 1

          ? "خلال يوم"

          : `${
              Number(
                quote.delivery_days
              )
            } أيام`;


  document
    .getElementById(
      "selectedQuoteNotes"
    )
    .value =
      quote.notes || "";


  const box =
    document.getElementById(
      "quoteDetailsBox"
    );


  if (box) {

    box.style.display =
      "block";


    box.scrollIntoView({

      behavior:
        "smooth",

      block:
        "start"

    });

  }

}


/* =========================================================
   إغلاق التفاصيل
========================================================= */

function closeQuoteDetails() {

  const box =
    document.getElementById(
      "quoteDetailsBox"
    );


  if (box) {

    box.style.display =
      "none";

  }

}


/* =========================================================
   البحث عن منتج المورد المقبول
========================================================= */

async function findSupplierProduct(
  quote,
  rfq
) {

  const sb =
    Bahrna.client;


  /*
    نحاول أولاً المطابقة الدقيقة
    بين المورد + اسم المنتج.
  */

  let result =
    await sb

      .from("products")

      .select(`
        id,
        supplier_id,
        name_ar,
        stock_kg,
        price_per_kg,
        wholesale_price_per_kg,
        active
      `)

      .eq(
        "supplier_id",
        quote.supplier_id
      )

      .eq(
        "name_ar",
        rfq.item_name
      )

      .eq(
        "active",
        true
      )

      .limit(1);


  if (
    !result.error &&
    result.data &&
    result.data.length
  ) {

    return result.data[0];

  }


  /*
    إذا لم نجد الاسم حرفياً،
    نأخذ أول منتج نشط لذلك المورد.
    هذا احتياط للنسخة التجريبية فقط.
  */

  result =
    await sb

      .from("products")

      .select(`
        id,
        supplier_id,
        name_ar,
        stock_kg,
        price_per_kg,
        wholesale_price_per_kg,
        active
      `)

      .eq(
        "supplier_id",
        quote.supplier_id
      )

      .eq(
        "active",
        true
      )

      .limit(1);


  if (
    result.error ||
    !result.data ||
    !result.data.length
  ) {

    throw new Error(
      "تعذر العثور على منتج مرتبط بهذا المورد لإنشاء الطلب"
    );

  }


  return result.data[0];

}


/* =========================================================
   إنشاء طلب B2B من العرض المقبول
========================================================= */

async function createB2BOrderFromQuote(
  quote,
  rfq
) {

  /*
    منع التكرار في النسخة التجريبية.
  */

  const storageKey =
    "bahrna_b2b_order_" +
    rfq.id;


  const existing =
    localStorage.getItem(
      storageKey
    );


  if (existing) {

    try {

      return JSON.parse(
        existing
      );

    } catch (e) {

      return {
        order_no:
          existing
      };

    }

  }


  if (
    !window.Bahrna ||
    typeof Bahrna.createOrder !==
      "function"
  ) {

    throw new Error(
      "وظيفة إنشاء الطلب Bahrna.createOrder غير متاحة"
    );

  }


  const product =
    await findSupplierProduct(
      quote,
      rfq
    );


  const requestedQty =
    Number(
      rfq.quantity_kg || 0
    );


  const availableQty =
    Number(
      quote.available_qty_kg || 0
    );


  /*
    لا نسمح بإنشاء طلب بكمية
    أعلى من التي عرضها المورد.
  */

  const qty =
    Math.min(
      requestedQty,
      availableQty
    );


  if (
    !Number.isFinite(qty) ||
    qty <= 0
  ) {

    throw new Error(
      "كمية العرض غير صحيحة"
    );

  }


  const unitPrice =
    Number(
      quote.price_per_kg || 0
    );


  if (
    !Number.isFinite(unitPrice) ||
    unitPrice <= 0
  ) {

    throw new Error(
      "سعر العرض غير صحيح"
    );

  }


  const subtotal =
    qty *
    unitPrice;


  /*
    طلب RFQ مؤسسي:
    السعر المقبول هو السعر النهائي
    للمنتج في هذه المرحلة التجريبية.

    لا نضيف رسوم تجهيز أو توصيل
    أو VAT تلقائياً هنا حتى لا
    نغيّر السعر الذي تم اعتماده.
  */

  const totals = {

    subtotal:
      subtotal,

    prep:
      0,

    pack:
      0,

    delivery:
      0,

    vat:
      0,

    total:
      subtotal

  };


  const flow = {

    cart: [

      {

        id:
          product.id,

        name:
          rfq.item_name,

        price:
          unitPrice,

        qty:
          qty

      }

    ],


    cut: {

      name:
        "طلب مؤسسي RFQ",

      fee:
        0

    },


    packaging: {

      name:
        "حسب عرض المورد",

      fee:
        0

    },


    keepHeadBones:
      true,


    address: {

      emirate:
        rfq.delivery_emirate ||
        "",

      area:
        "طلب مؤسسي",

      address:
        rfq.rfq_no

    },


    slot:
      rfq.delivery_date ||
      "",


    deliveryFee:
      0,


    vatRate:
      0,


    rfqId:
      rfq.id,


    rfqNo:
      rfq.rfq_no,


    quoteId:
      quote.id

  };


  const dbOrder =
    await Bahrna.createOrder(
      flow,
      totals
    );


  if (
    !dbOrder ||
    !dbOrder.id
  ) {

    throw new Error(
      "لم يتم إنشاء الطلب في قاعدة البيانات"
    );

  }


  const localOrder = {

    id:
      dbOrder.id,

    order_no:
      dbOrder.order_no,

    rfq_id:
      rfq.id,

    rfq_no:
      rfq.rfq_no,

    quote_id:
      quote.id,

    supplier_id:
      quote.supplier_id,

    product:
      rfq.item_name,

    qty:
      qty,

    unit_price:
      unitPrice,

    total:
      Number(
        dbOrder.total ??
        totals.total
      ),

    status:
      dbOrder.status ||
      "pending",

    created_at:
      dbOrder.created_at ||
      new Date().toISOString()

  };


  localStorage.setItem(
    storageKey,
    JSON.stringify(
      localOrder
    )
  );


  return localOrder;

}


/* =========================================================
   قبول عرض المورد
========================================================= */

async function acceptSupplierQuote() {

  const quoteId =
    document
      .getElementById(
        "selectedQuoteId"
      )
      ?.value;


  const rfqId =
    document
      .getElementById(
        "selectedQuoteRfqId"
      )
      ?.value;


  if (
    !quoteId ||
    !rfqId
  ) {

    alert(
      "لم يتم تحديد العرض"
    );


    return;

  }


  const quote =
    BuyerData.quotes.find(
      q =>
        q.id === quoteId
    );


  const rfq =
    BuyerData.rfqs.find(
      r =>
        r.id === rfqId
    );


  if (
    !quote ||
    !rfq
  ) {

    alert(
      "بيانات العرض أو RFQ غير مكتملة"
    );


    return;

  }


  const supplierName =
    quote.supplier?.display_name ||
    "المورد";


  /*
    إذا كان العرض مقبولاً مسبقاً،
    فهذا مفيد للـRFQ الذي قمنا
    بقبوله قبل تركيب هذه النسخة.
    سننشئ الطلب دون إعادة عملية الترسية.
  */

  if (
    quote.status === "accepted"
  ) {

    const okExisting =
      confirm(
        "العرض مقبول بالفعل.\n\n" +
        "هل تريد الآن تحويله إلى طلب شراء B2B؟"
      );


    if (!okExisting) {

      return;

    }


    try {

      const order =
        await createB2BOrderFromQuote(
          quote,
          rfq
        );


      const sb =
        Bahrna.client;


      await sb

        .from("rfqs")

        .update({

          status:
            "closed"

        })

        .eq(
          "id",
          rfq.id
        );


      alert(
        "✅ تم إنشاء طلب الشراء المؤسسي بنجاح\n\n" +
        "رقم الطلب: " +
        order.order_no
      );


      closeQuoteDetails();


      const user =
        await getBuyerUser();


      await Promise.all([

        loadBuyerRFQs(user),

        loadBuyerQuotes(),

        loadBuyerOrders(user)

      ]);


      renderRFQs();

      renderBuyerQuotes();

      renderB2BOrders();


      showBuyerPanel(
        "ordersPanel"
      );


      return;


    } catch (e) {

      console.error(
        "خطأ إنشاء B2B:",
        e
      );


      alert(
        "تعذر إنشاء طلب B2B: " +
        (e.message || e)
      );


      return;

    }

  }


  const ok =
    confirm(

      "هل تريد قبول عرض " +
      supplierName +
      " على " +
      rfq.rfq_no +
      " وتحويله إلى طلب شراء؟"

    );


  if (!ok) {

    return;

  }


  try {

    const sb =
      Bahrna.client;


    /* =====================================
       1) قبول العرض
    ===================================== */

    const {
      error: acceptError
    } = await sb

      .from("rfq_quotes")

      .update({

        status:
          "accepted"

      })

      .eq(
        "id",
        quoteId
      );


    if (acceptError) {

      throw acceptError;

    }


    /* =====================================
       2) رفض باقي العروض
    ===================================== */

    const {
      error: rejectOthersError
    } = await sb

      .from("rfq_quotes")

      .update({

        status:
          "rejected"

      })

      .eq(
        "rfq_id",
        rfqId
      )

      .neq(
        "id",
        quoteId
      )

      .eq(
        "status",
        "submitted"
      );


    if (rejectOthersError) {

      console.warn(
        "تعذر رفض بقية العروض:",
        rejectOthersError
      );

    }


    /* =====================================
       3) تحديث RFQ إلى awarded
    ===================================== */

    const {
      error: rfqAwardError
    } = await sb

      .from("rfqs")

      .update({

        status:
          "awarded"

      })

      .eq(
        "id",
        rfqId
      );


    if (rfqAwardError) {

      throw rfqAwardError;

    }


    /* =====================================
       4) إنشاء الطلب B2B
    ===================================== */

    const acceptedQuote = {

      ...quote,

      status:
        "accepted"

    };


    const order =
      await createB2BOrderFromQuote(
        acceptedQuote,
        rfq
      );


    /* =====================================
       5) إغلاق RFQ بعد إنشاء الطلب
    ===================================== */

    const {
      error: closeRfqError
    } = await sb

      .from("rfqs")

      .update({

        status:
          "closed"

      })

      .eq(
        "id",
        rfqId
      );


    if (closeRfqError) {

      console.warn(
        "تم إنشاء الطلب ولكن تعذر إغلاق RFQ:",
        closeRfqError
      );

    }


    alert(

      "✅ تم قبول عرض المورد وإنشاء طلب الشراء بنجاح\n\n" +
      "رقم الطلب: " +
      order.order_no

    );


    closeQuoteDetails();


    const user =
      await getBuyerUser();


    await Promise.all([

      loadBuyerRFQs(user),

      loadBuyerQuotes(),

      loadBuyerOrders(user)

    ]);


    renderRFQs();

    renderBuyerQuotes();

    renderB2BOrders();


    showBuyerPanel(
      "ordersPanel"
    );


  } catch (e) {

    console.error(
      "خطأ قبول العرض / إنشاء الطلب:",
      e
    );


    alert(

      "تعذر إكمال العملية: " +
      (e.message || e)

    );

  }

}


/* =========================================================
   رفض العرض
========================================================= */

async function rejectSupplierQuote() {

  const quoteId =
    document
      .getElementById(
        "selectedQuoteId"
      )
      ?.value;


  if (!quoteId) {

    alert(
      "لم يتم تحديد العرض"
    );


    return;

  }


  const quote =
    BuyerData.quotes.find(
      q =>
        q.id === quoteId
    );


  if (
    quote?.status === "accepted"
  ) {

    alert(
      "لا يمكن رفض عرض تم قبوله بالفعل."
    );


    return;

  }


  const ok =
    confirm(
      "هل تريد رفض هذا العرض؟"
    );


  if (!ok) {

    return;

  }


  try {

    const sb =
      Bahrna.client;


    const {
      error
    } = await sb

      .from("rfq_quotes")

      .update({

        status:
          "rejected"

      })

      .eq(
        "id",
        quoteId
      );


    if (error) {

      throw error;

    }


    alert(
      "تم رفض العرض"
    );


    closeQuoteDetails();


    await loadBuyerQuotes();


    renderBuyerQuotes();

    renderRFQs();


  } catch (e) {

    console.error(
      "خطأ رفض العرض:",
      e
    );


    alert(
      "تعذر رفض العرض: " +
      (e.message || e)
    );

  }

}


/* =========================================================
   عرض طلبات B2B
========================================================= */

function renderB2BOrders() {

  const rows =
    document.getElementById(
      "b2bRows"
    );


  const count =
    document.getElementById(
      "b2bOrderCount"
    );


  if (count) {

    count.textContent =
      BuyerData.orders.length;

  }


  if (!rows) {

    return;

  }


  if (!BuyerData.orders.length) {

    rows.innerHTML = `

      <tr>

        <td colspan="4">

          لا توجد طلبات شراء مؤسسية حالياً.

        </td>

      </tr>

    `;


    return;

  }


  rows.innerHTML =
    BuyerData.orders

      .map(
        order => {

          const items =
            order.order_items ||
            [];


          const products =
            items.length

              ? items

                  .map(
                    item =>
                      `${
                        item.product_name ||
                        "منتج"
                      } ${
                        Number(
                          item.qty_kg || 0
                        )
                      } كجم`
                  )

                  .join("، ")

              : "—";


          const status =
            order.tracking_status ||
            order.status ||
            "pending";


          return `

            <tr>

              <td>

                <strong>

                  ${order.order_no}

                </strong>

              </td>


              <td>

                ${products}

              </td>


              <td>

                <strong>

                  ${money(order.total)}

                </strong>

              </td>


              <td>

                <span class="status ok">

                  ${orderStatusLabel(status)}

                </span>

              </td>

            </tr>

          `;

        }
      )

      .join("");

}


/* =========================================================
   تعبئة RFQ من سعر الجملة
========================================================= */

function prefillRFQ(
  name,
  qty
) {

  showBuyerPanel(
    "newRfqPanel"
  );


  const item =
    document.getElementById(
      "rfqItem"
    );


  const qtyInput =
    document.getElementById(
      "rfqQty"
    );


  if (item) {

    item.value =
      name || "";

  }


  if (qtyInput) {

    qtyInput.value =
      Math.min(
        Number(qty || 0),
        50
      );

  }

}


/* =========================================================
   إنشاء RFQ
========================================================= */

async function submitRFQ() {

  try {

    const user =
      await getBuyerUser();


    if (!user) {

      return;

    }


    const itemInput =
      document.getElementById(
        "rfqItem"
      );


    const qtyInput =
      document.getElementById(
        "rfqQty"
      );


    const deliveryInput =
      document.getElementById(
        "rfqDelivery"
      );


    const dateInput =
      document.getElementById(
        "rfqDeliveryDate"
      );


    const notesInput =
      document.getElementById(
        "rfqNotes"
      );


    const item =
      itemInput?.value.trim();


    const qty =
      Number(
        qtyInput?.value
      );


    const delivery =
      deliveryInput?.value;


    const deliveryDate =
      dateInput?.value ||
      null;


    const notes =
      notesInput?.value.trim() ||
      null;


    if (
      !item ||
      !qty ||
      qty <= 0 ||
      !delivery
    ) {

      alert(
        "أكمل المنتج والكمية والإمارة"
      );


      return;

    }


    const sb =
      Bahrna.client;


    const {
      data,
      error
    } = await sb

      .from("rfqs")

      .insert({

        buyer_id:
          user.id,

        item_name:
          item,

        quantity_kg:
          qty,

        delivery_emirate:
          delivery,

        delivery_date:
          deliveryDate,

        notes:
          notes,

        status:
          "open"

      })

      .select(`
        id,
        rfq_no,
        buyer_id,
        company_id,
        item_name,
        quantity_kg,
        delivery_emirate,
        delivery_date,
        notes,
        status,
        created_at,
        updated_at
      `)

      .single();


    if (error) {

      throw error;

    }


    alert(

      "✅ تم إرسال طلب عرض السعر بنجاح\n" +
      data.rfq_no

    );


    if (itemInput) {

      itemInput.value =
        "";

    }


    if (qtyInput) {

      qtyInput.value =
        "";

    }


    if (dateInput) {

      dateInput.value =
        "";

    }


    if (notesInput) {

      notesInput.value =
        "";

    }


    await loadBuyerRFQs(
      user
    );


    renderRFQs();


    showBuyerPanel(
      "rfqPanel"
    );


  } catch (e) {

    console.error(
      "خطأ إنشاء RFQ:",
      e
    );


    alert(

      "تعذر إرسال RFQ: " +
      (e.message || e)

    );

  }

}


/* =========================================================
   تشغيل لوحة المشتري
========================================================= */

async function renderBuyer() {

  try {

    const user =
      await getBuyerUser();


    if (!user) {

      return;

    }


    /*
      RFQ
    */

    await loadBuyerRFQs(
      user
    );


    /*
      عروض الموردين
    */

    try {

      await loadBuyerQuotes();

    } catch (quoteError) {

      console.error(
        quoteError
      );


      BuyerData.quotes =
        [];

    }


    /*
      طلبات المشتري
    */

    try {

      await loadBuyerOrders(
        user
      );

    } catch (orderError) {

      console.error(
        orderError
      );


      BuyerData.orders =
        [];

    }


    /*
      أسعار الجملة
    */

    await renderWholesaleOffers();


    /*
      العرض
    */

    renderRFQs();

    renderBuyerQuotes();

    renderB2BOrders();


  } catch (e) {

    console.error(
      "خطأ تحميل لوحة المشتري:",
      e
    );


    alert(

      "تعذر تحميل لوحة المشتري: " +
      (e.message || e)

    );

  }

}


document.addEventListener(
  "DOMContentLoaded",
  renderBuyer
);

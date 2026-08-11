/* =========================================================
   BAHRNA & SHRAANA
   BUSINESS BUYER DASHBOARD
   Wholesale + RFQ + Supplier Quotes
========================================================= */


const BuyerData = {
  rfqs: [],
  quotes: [],
  orders: []
};


/* =========================================================
   التنقل بين أقسام لوحة المشتري
========================================================= */

function showBuyerPanel(id, el) {

  document
    .querySelectorAll(".buyer-panel")
    .forEach(x => x.classList.remove("active"));

  const panel =
    document.getElementById(id);

  if (panel) {
    panel.classList.add("active");
  }

  document
    .querySelectorAll(".buyer-sidebar a")
    .forEach(a => a.classList.remove("active"));

  if (el) {
    el.classList.add("active");
  }
}


/* =========================================================
   أدوات عامة
========================================================= */

function money(n) {
  return "AED " + Number(n || 0).toFixed(2);
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
      "تم اختيار مورد",

    closed:
      "مغلق",

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
   تحميل RFQ الخاصة بالمشتري
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

                AED ${Number(o.wholesale).toFixed(2)}

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
   عرض قائمة RFQ
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
   عرض كل عروض الموردين
========================================================= */

function renderBuyerQuotes(filterRfqId = null) {

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


  /*
    ترتيب الأسعار من الأقل إلى الأعلى
    داخل القائمة
  */

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
        ${quotes.length}

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
   فتح عروض RFQ محدد
========================================================= */

function openQuotesForRFQ(rfqId) {

  showBuyerPanel(
    "quotesPanel"
  );


  renderBuyerQuotes(
    rfqId
  );
}


/* =========================================================
   فتح تفاصيل عرض مورد
========================================================= */

function openQuoteDetails(quoteId) {

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

      Number(quote.delivery_days) === 0

        ? "نفس اليوم"

        : Number(quote.delivery_days) === 1

          ? "خلال يوم"

          : `${Number(quote.delivery_days)} أيام`;


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
      behavior: "smooth",
      block: "start"
    });
  }
}


/* =========================================================
   إغلاق تفاصيل العرض
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


  const supplierName =
    quote?.supplier?.display_name ||
    "المورد";


  const ok =
    confirm(
      "هل تريد قبول عرض " +
      supplierName +
      " على " +
      (rfq?.rfq_no || "RFQ") +
      "؟"
    );


  if (!ok) {
    return;
  }


  try {

    const sb =
      Bahrna.client;


    /*
      1) قبول العرض المختار
    */

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


    /*
      2) رفض بقية العروض على نفس RFQ
    */

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
        "تعذر تحديث بقية العروض:",
        rejectOthersError
      );
    }


    /*
      3) تحديث حالة RFQ
    */

    const {
      error: rfqError
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


    if (rfqError) {

      console.warn(
        "تم قبول العرض ولكن تعذر تحديث حالة RFQ:",
        rfqError
      );
    }


    alert(
      "✅ تم قبول عرض المورد بنجاح"
    );


    closeQuoteDetails();


    const user =
      await getBuyerUser();


    await Promise.all([

      loadBuyerRFQs(user),

      loadBuyerQuotes()

    ]);


    renderRFQs();

    renderBuyerQuotes();


  } catch (e) {

    console.error(
      "خطأ قبول العرض:",
      e
    );


    alert(
      "تعذر قبول العرض: " +
      (e.message || e)
    );
  }
}


/* =========================================================
   رفض عرض المورد
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
   تعبئة نموذج RFQ من السوق
========================================================= */

function prefillRFQ(name, qty) {

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
      dateInput?.value || null;


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
      itemInput.value = "";
    }


    if (qtyInput) {
      qtyInput.value = "";
    }


    if (dateInput) {
      dateInput.value = "";
    }


    if (notesInput) {
      notesInput.value = "";
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
   طلبات الجملة
   المرحلة التالية بعد قبول العرض
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

          لا توجد طلبات جملة حالياً.

          سيتم في المرحلة التالية
          تحويل العرض المقبول
          إلى طلب شراء مؤسسي.

        </td>

      </tr>

    `;

    return;
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


    await loadBuyerRFQs(
      user
    );


    /*
      لا نريد أن يؤدي خطأ عروض الموردين
      إلى تعطيل بقية لوحة المشتري.
    */

    try {

      await loadBuyerQuotes();

    } catch (quoteError) {

      console.error(
        quoteError
      );


      BuyerData.quotes = [];
    }


    await renderWholesaleOffers();


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


/* =========================================================
   بدء التشغيل
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  renderBuyer
);

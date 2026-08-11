const BuyerData = {
  rfqs: [],
  orders: []
};


/* =========================================
   التنقل بين أقسام لوحة المشتري
========================================= */

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


/* =========================================
   أدوات
========================================= */

function money(n) {
  return "AED " + Number(n || 0).toFixed(2);
}


function rfqStatusLabel(status) {

  const labels = {
    open: "مفتوح",
    quoted: "وردت عروض",
    awarded: "تمت الترسية",
    closed: "مغلق",
    cancelled: "ملغي"
  };

  return labels[status] || status;
}


function formatDate(value) {

  if (!value) {
    return "—";
  }

  try {

    return new Date(value)
      .toLocaleDateString("ar-AE", {
        year: "numeric",
        month: "short",
        day: "numeric"
      });

  } catch (e) {

    return value;
  }
}


/* =========================================
   التحقق من الاتصال والمستخدم
========================================= */

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


/* =========================================
   تحميل RFQ الحقيقي من Supabase
========================================= */

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
    throw error;
  }

  BuyerData.rfqs =
    data || [];
}


/* =========================================
   عرض أسعار الجملة
========================================= */

async function renderWholesaleOffers() {

  const wrap =
    document.getElementById(
      "wholesaleCards"
    );

  if (!wrap) {
    return;
  }

  const offers =
    await Bahrna.getMarketOffers();


  const wholesaleOffers =
    (offers || [])

      .filter(
        o =>
          Number(o.wholesale || 0) > 0
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
    wholesaleOffers.map(o => `

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
            /كجم
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
          )'
        >

          طلب كمية

        </button>

      </div>

    `).join("");
}


/* =========================================
   عرض RFQ
========================================= */

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
        <td colspan="5">
          لا توجد طلبات عروض أسعار حتى الآن.
        </td>
      </tr>
    `;

    return;
  }


  rows.innerHTML =
    BuyerData.rfqs.map(r => `

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
          ${Number(r.quantity_kg)} كجم
        </td>

        <td>
          ${r.delivery_emirate}
          ${
            r.delivery_date
              ? `<br><small>${formatDate(r.delivery_date)}</small>`
              : ""
          }
        </td>

        <td>
          <span class="status ok">
            ${rfqStatusLabel(r.status)}
          </span>
        </td>

      </tr>

    `).join("");
}


/* =========================================
   طلبات الجملة
   سيتم ربطها لاحقاً بالعرض المقبول
========================================= */

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
    count.textContent = 0;
  }


  if (rows) {

    rows.innerHTML = `
      <tr>
        <td colspan="4">
          لا توجد طلبات جملة حالياً.
          سيتم إنشاء الطلب بعد قبول عرض المورد.
        </td>
      </tr>
    `;
  }
}


/* =========================================
   تعبئة نموذج RFQ من سعر الجملة
========================================= */

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


/* =========================================
   إنشاء RFQ حقيقي
========================================= */

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


    /*
      buyer.html الحالي لا يحتوي IDs
      لحقل التاريخ والملاحظات،
      لذلك نقرأهما من داخل القسم.
    */

    const dateInput =
      document.querySelector(
        '#newRfqPanel input[type="date"]'
      );

    const notesInput =
      document.querySelector(
        "#newRfqPanel textarea"
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
      notesInput?.value.trim() || null;


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


    /*
      تنظيف النموذج
    */

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


    /*
      إعادة تحميل البيانات من Supabase
    */

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


/* =========================================
   تشغيل لوحة المشتري
========================================= */

async function renderBuyer() {

  try {

    const user =
      await getBuyerUser();

    if (!user) {
      return;
    }


    await Promise.all([

      loadBuyerRFQs(user),

      renderWholesaleOffers()

    ]);


    renderRFQs();

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

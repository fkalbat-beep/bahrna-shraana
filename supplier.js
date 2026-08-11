/* =========================================================
   BAHRNA & SHRAANA
   SUPPLIER DASHBOARD
   Products + Orders + RFQ
========================================================= */


const SupplierData = {
  offers: [],
  orders: [],
  rfqs: [],
  quotes: [],
  supplier: null
};


let offerModes = new Set(["retail"]);


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
    open: "مفتوح",
    quoted: "وردت عروض",
    awarded: "تمت الترسية",
    closed: "مغلق",
    cancelled: "ملغي"
  };

  return labels[status] || status;
}


function showSupplierPanel(id, el) {

  document
    .querySelectorAll(".supplier-panel")
    .forEach(
      p => p.classList.remove("active")
    );


  const panel =
    document.getElementById(id);


  if (panel) {
    panel.classList.add("active");
  }


  document
    .querySelectorAll(
      ".supplier-sidebar a"
    )
    .forEach(
      a => a.classList.remove("active")
    );


  if (el) {
    el.classList.add("active");
  }
}



/* =========================================================
   المورد الحالي
========================================================= */

async function getCurrentSupplier() {

  if (
    !window.Bahrna ||
    !Bahrna.client
  ) {

    throw new Error(
      "Supabase غير متصل"
    );
  }


  const sb =
    Bahrna.client;


  const user =
    await Bahrna.getCurrentUser();


  if (!user) {

    localStorage.setItem(
      "bahrna_return_after_login",
      "supplier.html"
    );

    throw new Error(
      "يجب تسجيل الدخول بحساب المورد"
    );
  }


  const {
    data,
    error
  } = await sb

    .from("suppliers")

    .select(`
      id,
      owner_id,
      company_id,
      display_name,
      emirate,
      verified,
      rating,
      created_at
    `)

    .eq(
      "owner_id",
      user.id
    )

    .single();


  if (error) {

    console.error(
      "خطأ قراءة المورد:",
      error
    );

    throw new Error(
      "لم يتم العثور على سجل المورد لهذا الحساب"
    );
  }


  SupplierData.supplier =
    data;


  return data;
}



/* =========================================================
   بيانات المورد
========================================================= */

function renderSupplierProfile() {

  const supplier =
    SupplierData.supplier;


  if (!supplier) {
    return;
  }


  const name =
    document.getElementById(
      "supplierProfileName"
    );


  const emirate =
    document.getElementById(
      "supplierProfileEmirate"
    );


  const verified =
    document.getElementById(
      "supplierProfileVerified"
    );


  const badge =
    document.getElementById(
      "supplierVerificationBadge"
    );


  if (name) {

    name.value =
      supplier.display_name ||
      "مورد";
  }


  if (emirate) {

    emirate.value =
      supplier.emirate ||
      "—";
  }


  if (verified) {

    verified.value =
      supplier.verified
        ? "موثق"
        : "قيد التحقق";
  }


  if (badge) {

    if (supplier.verified) {

      badge.textContent =
        "حساب مورد موثق ✓";

      badge.className =
        "status ok";

    } else {

      badge.textContent =
        "الحساب قيد التحقق";

      badge.className =
        "status wait";
    }
  }
}



/* =========================================================
   قراءة عروض المورد من products
========================================================= */

async function loadSupplierOffers() {

  const sb =
    Bahrna.client;


  const supplier =
    SupplierData.supplier ||
    await getCurrentSupplier();


  const {
    data,
    error
  } = await sb

    .from("products")

    .select(`
      id,
      supplier_id,
      name_ar,
      origin,
      price_per_kg,
      wholesale_price_per_kg,
      stock_kg,
      arrived_at,
      active,
      created_at
    `)

    .eq(
      "supplier_id",
      supplier.id
    )

    .order(
      "created_at",
      {
        ascending: false
      }
    );


  if (error) {

    console.error(
      "خطأ تحميل عروض المورد:",
      error
    );

    SupplierData.offers = [];

    return;
  }


  SupplierData.offers =
    (data || []).map(
      x => ({

        id:
          x.id,

        name:
          x.name_ar,

        qty:
          Number(
            x.stock_kg || 0
          ),

        retail:
          Number(
            x.price_per_kg || 0
          ),

        wholesale:
          Number(
            x.wholesale_price_per_kg || 0
          ),

        auction:
          false,

        status:
          x.active
            ? "active"
            : "paused",

        arrived:
          x.arrived_at || "",

        supplier:
          supplier.display_name ||
          "مورد",

        origin:
          x.origin ||
          "الإمارات",

        isReal:
          true
      })
    );
}



/* =========================================================
   قراءة طلبات المورد
========================================================= */

async function loadSupplierOrders() {

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


  if (error) {

    console.error(
      "خطأ تحميل الطلبات:",
      error
    );

    SupplierData.orders = [];

    return;
  }


  SupplierData.orders =
    (data || []).map(
      order => {

        const items =
          order.order_items || [];


        const itemText =
          items.length

            ? items
                .map(
                  i =>
                    `${i.product_name || "منتج"} ${Number(i.qty_kg || 0)} كجم`
                )
                .join("، ")

            : "—";


        return {

          id:
            order.id,

          no:
            order.order_no,

          item:
            itemText,

          total:
            Number(
              order.total || 0
            ),

          status:
            order.tracking_status ||
            order.status ||
            "confirmed"
        };
      }
    );
}



/* =========================================================
   قراءة RFQ المفتوحة
========================================================= */

async function loadSupplierRFQs() {

  const sb =
    Bahrna.client;


  const supplier =
    SupplierData.supplier ||
    await getCurrentSupplier();


  /*
    أولاً:
    نقرأ RFQ المفتوحة التي يسمح بها RLS للمورد.
  */

  const {
    data: rfqs,
    error: rfqError
  } = await sb

    .from("rfqs")

    .select(`
      id,
      rfq_no,
      item_name,
      quantity_kg,
      delivery_emirate,
      delivery_date,
      notes,
      status,
      created_at
    `)

    .eq(
      "status",
      "open"
    )

    .order(
      "created_at",
      {
        ascending: false
      }
    );


  if (rfqError) {

    console.error(
      "خطأ تحميل RFQ:",
      rfqError
    );

    SupplierData.rfqs = [];

    return;
  }


  /*
    ثانياً:
    نقرأ عروض هذا المورد لمعرفة
    أي RFQ سبق أن قدم عليه عرضاً.
  */

  const {
    data: quotes,
    error: quoteError
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
      created_at
    `)

    .eq(
      "supplier_id",
      supplier.id
    );


  if (quoteError) {

    console.error(
      "خطأ تحميل عروض RFQ الخاصة بالمورد:",
      quoteError
    );

    SupplierData.quotes = [];

  } else {

    SupplierData.quotes =
      quotes || [];
  }


  SupplierData.rfqs =
    rfqs || [];
}



/* =========================================================
   عرض لوحة المورد
========================================================= */

function renderSupplier() {

  renderSupplierProfile();


  const activeOffers =
    document.getElementById(
      "activeOffers"
    );


  const stockKg =
    document.getElementById(
      "stockKg"
    );


  const pendingOrders =
    document.getElementById(
      "pendingOrders"
    );


  const supplierGMV =
    document.getElementById(
      "supplierGMV"
    );


  const offerRows =
    document.getElementById(
      "offerRows"
    );


  const supplierOrderRows =
    document.getElementById(
      "supplierOrderRows"
    );


  if (activeOffers) {

    activeOffers.textContent =
      SupplierData.offers
        .filter(
          x =>
            x.status === "active"
        )
        .length;
  }


  if (stockKg) {

    stockKg.textContent =
      SupplierData.offers
        .reduce(
          (s, x) =>
            s +
            Number(
              x.qty || 0
            ),
          0
        ) +
      " كجم";
  }


  if (pendingOrders) {

    pendingOrders.textContent =
      SupplierData.orders
        .filter(
          o =>
            o.status !==
            "delivered"
        )
        .length;
  }


  if (supplierGMV) {

    supplierGMV.textContent =
      money(
        SupplierData.orders
          .reduce(
            (s, o) =>
              s +
              Number(
                o.total || 0
              ),
            0
          )
      );
  }


  /* =====================================================
     جدول العروض
  ===================================================== */

  if (offerRows) {

    offerRows.innerHTML =

      SupplierData.offers.length

        ? SupplierData.offers
            .map(
              o => `

                <tr>

                  <td>
                    ${o.name}
                  </td>

                  <td>
                    ${o.qty} كجم
                  </td>

                  <td>
                    ${money(o.retail)}
                  </td>

                  <td>
                    ${
                      o.wholesale > 0
                        ? money(o.wholesale)
                        : "—"
                    }
                  </td>

                  <td>
                    ${
                      o.auction
                        ? "نعم"
                        : "لا"
                    }
                  </td>

                  <td>

                    ${
                      o.status === "active"

                        ? '<span class="status ok">نشط</span>'

                        : '<span class="status wait">موقوف</span>'
                    }

                  </td>

                  <td>

                    <button
                      class="btn btn-primary small"
                      onclick="toggleOffer('${o.id}')">

                      ${
                        o.status === "active"
                          ? "إيقاف"
                          : "تفعيل"
                      }

                    </button>

                  </td>

                </tr>

              `
            )
            .join("")

        : `

            <tr>

              <td colspan="7">
                لا توجد عروض حالياً
              </td>

            </tr>

          `;
  }


  /* =====================================================
     الطلبات
  ===================================================== */

  if (supplierOrderRows) {

    supplierOrderRows.innerHTML =

      SupplierData.orders.length

        ? SupplierData.orders
            .map(
              o => `

                <tr>

                  <td>
                    ${o.no}
                  </td>

                  <td>
                    ${o.item}
                  </td>

                  <td>
                    ${money(o.total)}
                  </td>

                  <td>

                    <select
                      class="order-status-select"
                      onchange="updateOrderStatus('${o.id}',this.value)">


                      <option
                        value="confirmed"
                        ${
                          o.status === "confirmed"
                            ? "selected"
                            : ""
                        }>
                        تم التأكيد
                      </option>


                      <option
                        value="preparing"
                        ${
                          o.status === "preparing"
                            ? "selected"
                            : ""
                        }>
                        جاري التجهيز
                      </option>


                      <option
                        value="out_for_delivery"
                        ${
                          o.status === "out_for_delivery"
                            ? "selected"
                            : ""
                        }>
                        خرج للتوصيل
                      </option>


                      <option
                        value="delivered"
                        ${
                          o.status === "delivered"
                            ? "selected"
                            : ""
                        }>
                        تم التسليم
                      </option>

                    </select>

                  </td>

                </tr>

              `
            )
            .join("")

        : `

            <tr>
              <td colspan="4">
                لا توجد طلبات حالياً
              </td>
            </tr>

          `;
  }


  renderSupplierRFQs();
}



/* =========================================================
   عرض RFQ
========================================================= */

function renderSupplierRFQs() {

  const rows =
    document.getElementById(
      "supplierRfqRows"
    );


  if (!rows) {
    return;
  }


  if (!SupplierData.rfqs.length) {

    rows.innerHTML = `

      <tr>

        <td colspan="7">
          لا توجد طلبات RFQ مفتوحة حالياً.
        </td>

      </tr>

    `;

    return;
  }


  rows.innerHTML =
    SupplierData.rfqs
      .map(
        rfq => {

          const oldQuote =
            SupplierData.quotes
              .find(
                q =>
                  q.rfq_id ===
                  rfq.id
              );


          const action =

            oldQuote

              ? `

                  <span class="status ok">
                    تم تقديم عرض
                  </span>

                  <br>

                  <small>
                    ${money(oldQuote.price_per_kg)} / كجم
                  </small>

                `

              : `

                  <button
                    class="btn btn-primary small"
                    onclick='openQuoteBox(
                      ${JSON.stringify(rfq)}
                    )'>

                    تقديم عرض

                  </button>

                `;


          return `

            <tr>

              <td>
                <strong>
                  ${rfq.rfq_no}
                </strong>
              </td>


              <td>
                ${rfq.item_name}
              </td>


              <td>
                ${Number(rfq.quantity_kg)} كجم
              </td>


              <td>
                ${rfq.delivery_emirate}
              </td>


              <td>
                ${formatDate(rfq.delivery_date)}
              </td>


              <td>

                <span class="status ok">
                  ${rfqStatusLabel(rfq.status)}
                </span>

              </td>


              <td>
                ${action}
              </td>

            </tr>

          `;
        }
      )
      .join("");
}



/* =========================================================
   فتح نموذج تقديم العرض
========================================================= */

function openQuoteBox(rfq) {

  const box =
    document.getElementById(
      "rfqQuoteBox"
    );


  if (!box) {
    return;
  }


  document.getElementById(
    "quoteRfqId"
  ).value =
    rfq.id;


  document.getElementById(
    "quoteRfqNo"
  ).value =
    rfq.rfq_no;


  document.getElementById(
    "quoteProduct"
  ).value =
    rfq.item_name;


  document.getElementById(
    "quoteRequestedQty"
  ).value =
    Number(
      rfq.quantity_kg
    ) +
    " كجم";


  document.getElementById(
    "quoteAvailableQty"
  ).value =
    Number(
      rfq.quantity_kg
    );


  document.getElementById(
    "quoteUnitPrice"
  ).value =
    "";


  document.getElementById(
    "quoteDeliveryDays"
  ).value =
    "";


  document.getElementById(
    "quoteNotes"
  ).value =
    "";


  box.style.display =
    "block";


  box.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}



/* =========================================================
   إغلاق نموذج العرض
========================================================= */

function closeQuoteBox() {

  const box =
    document.getElementById(
      "rfqQuoteBox"
    );


  if (box) {

    box.style.display =
      "none";
  }
}



/* =========================================================
   إرسال عرض سعر RFQ
========================================================= */

async function submitSupplierQuote() {

  try {

    const supplier =
      SupplierData.supplier ||
      await getCurrentSupplier();


    const rfqId =
      document
        .getElementById(
          "quoteRfqId"
        )
        .value;


    const availableQty =
      Number(
        document
          .getElementById(
            "quoteAvailableQty"
          )
          .value
      );


    const unitPrice =
      Number(
        document
          .getElementById(
            "quoteUnitPrice"
          )
          .value
      );


    const deliveryDays =
      Number(
        document
          .getElementById(
            "quoteDeliveryDays"
          )
          .value
      );


    const notes =
      document
        .getElementById(
          "quoteNotes"
        )
        .value
        .trim();


    if (!rfqId) {

      return alert(
        "لم يتم تحديد RFQ"
      );
    }


    if (
      !Number.isFinite(
        availableQty
      ) ||
      availableQty <= 0
    ) {

      return alert(
        "أدخل الكمية المتوفرة بشكل صحيح"
      );
    }


    if (
      !Number.isFinite(
        unitPrice
      ) ||
      unitPrice <= 0
    ) {

      return alert(
        "أدخل السعر لكل كجم بشكل صحيح"
      );
    }


    if (
      !Number.isFinite(
        deliveryDays
      ) ||
      deliveryDays < 0
    ) {

      return alert(
        "أدخل مدة التوصيل بشكل صحيح"
      );
    }


    const alreadyExists =
      SupplierData.quotes
        .some(
          q =>
            q.rfq_id ===
            rfqId
        );


    if (alreadyExists) {

      alert(
        "سبق أن قدمت عرضاً لهذا RFQ"
      );

      return;
    }


    const sb =
      Bahrna.client;


    const {
      data,
      error
    } = await sb

      .from("rfq_quotes")

      .insert({

        rfq_id:
          rfqId,

        supplier_id:
          supplier.id,

        price_per_kg:
          unitPrice,

        available_qty_kg:
          availableQty,

        delivery_days:
          deliveryDays,

        notes:
          notes || null,

        status:
          "submitted"

      })

      .select(`
        id,
        rfq_id,
        supplier_id,
        price_per_kg,
        available_qty_kg,
        delivery_days,
        notes,
        status,
        created_at
      `)

      .single();


    if (error) {
      throw error;
    }


    alert(
      "✅ تم إرسال عرض السعر بنجاح"
    );


    closeQuoteBox();


    await loadSupplierRFQs();


    renderSupplierRFQs();


  } catch (e) {

    console.error(
      "خطأ إرسال عرض السعر:",
      e
    );


    alert(
      "تعذر إرسال عرض السعر: " +
      (e.message || e)
    );
  }
}



/* =========================================================
   تحديث حالة الطلب
========================================================= */

async function updateOrderStatus(
  orderId,
  newStatus
) {

  if (
    !window.Bahrna ||
    !Bahrna.client
  ) {

    alert(
      "قاعدة البيانات غير متصلة"
    );

    return;
  }


  const allowedStatuses = [
    "confirmed",
    "preparing",
    "out_for_delivery",
    "delivered"
  ];


  if (
    !allowedStatuses.includes(
      newStatus
    )
  ) {

    alert(
      "حالة الطلب غير صحيحة"
    );

    return;
  }


  const sb =
    Bahrna.client;


  const {
    error
  } = await sb

    .from("orders")

    .update({

      tracking_status:
        newStatus

    })

    .eq(
      "id",
      orderId
    );


  if (error) {

    console.error(
      "خطأ تحديث حالة الطلب:",
      error
    );


    alert(
      "تعذر تحديث حالة الطلب: " +
      error.message
    );


    await loadSupplierOrders();

    renderSupplier();

    return;
  }


  await loadSupplierOrders();

  renderSupplier();


  alert(
    "تم تحديث حالة الطلب بنجاح ✅"
  );
}



/* =========================================================
   قنوات البيع
========================================================= */

function toggleMode(
  el,
  mode
) {

  if (
    offerModes.has(
      mode
    )
  ) {

    offerModes.delete(
      mode
    );

    el.classList.remove(
      "active"
    );

  } else {

    offerModes.add(
      mode
    );

    el.classList.add(
      "active"
    );
  }
}



/* =========================================================
   نشر عرض جديد في السوق
========================================================= */

async function addOffer() {

  try {

    if (
      !window.Bahrna ||
      !Bahrna.client
    ) {

      return alert(
        "قاعدة البيانات غير متصلة"
      );
    }


    const name =
      document
        .getElementById(
          "fishName"
        )
        .value
        .trim();


    const qty =
      Number(
        document
          .getElementById(
            "qtyKg"
          )
          .value
      );


    const retail =
      Number(
        document
          .getElementById(
            "retailPrice"
          )
          .value
      );


    const wholesale =
      Number(
        document
          .getElementById(
            "wholesalePrice"
          )
          .value || 0
      );


    const arrived =
      document
        .getElementById(
          "arrivedAt"
        )
        .value;


    const origin =
      document
        .getElementById(
          "offerOrigin"
        )
        ?.value ||
      "الإمارات";


    if (
      !name ||
      !Number.isFinite(qty) ||
      qty <= 0 ||
      !Number.isFinite(retail) ||
      retail <= 0
    ) {

      return alert(
        "أكمل اسم المنتج والكمية وسعر التجزئة بشكل صحيح"
      );
    }


    const supplier =
      SupplierData.supplier ||
      await getCurrentSupplier();


    let arrivedAt =
      null;


    if (arrived) {

      const now =
        new Date();


      const parts =
        arrived.split(":");


      const hours =
        Number(
          parts[0] || 0
        );


      const minutes =
        Number(
          parts[1] || 0
        );


      now.setHours(
        hours,
        minutes,
        0,
        0
      );


      arrivedAt =
        now.toISOString();
    }


    const payload = {

      supplier_id:
        supplier.id,

      name_ar:
        name,

      category:
        "سمك",

      origin:
        origin,

      price_per_kg:
        retail,

      wholesale_price_per_kg:
        offerModes.has(
          "wholesale"
        )
          ? wholesale
          : null,

      stock_kg:
        qty,

      arrived_at:
        arrivedAt,

      active:
        true
    };


    const sb =
      Bahrna.client;


    const {
      error
    } = await sb

      .from("products")

      .insert(payload);


    if (error) {

      console.error(
        "خطأ نشر العرض:",
        error
      );


      return alert(
        "تعذر نشر العرض: " +
        error.message
      );
    }


    alert(
      "تم نشر العرض بنجاح في السوق ✅"
    );


    await loadSupplierOffers();


    renderSupplier();


    showSupplierPanel(
      "offersPanel"
    );


  } catch (e) {

    console.error(e);


    alert(
      e.message ||
      "حدث خطأ أثناء نشر العرض"
    );
  }
}



/* =========================================================
   إيقاف / تفعيل العرض
========================================================= */

async function toggleOffer(id) {

  alert(
    "سيتم تفعيل خاصية إيقاف وتفعيل العرض بعد استكمال صلاحية UPDATE للمنتجات."
  );
}



/* =========================================================
   تشغيل لوحة المورد
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  async () => {

    try {

      /*
        نقرأ المورد مرة واحدة فقط
      */

      await getCurrentSupplier();


      /*
        تحميل بيانات اللوحة
      */

      await Promise.all([

        loadSupplierOffers(),

        loadSupplierOrders(),

        loadSupplierRFQs()

      ]);


      /*
        عرض جميع البيانات
      */

      renderSupplier();


    } catch (e) {

      console.error(
        "خطأ تشغيل لوحة المورد:",
        e
      );


      alert(
        e.message ||
        "تعذر تشغيل لوحة المورد"
      );


      renderSupplier();
    }
  }
);

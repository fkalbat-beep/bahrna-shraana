/* =========================================================
   BAHRNA & SHRAANA
   B2B ORDER DETAILS
   Delivery + Buyer Receipt + Supplier Invoice
========================================================= */

let CurrentOrder = null;
let CurrentUser = null;
let CurrentSupplier = null;
let CurrentInvoice = null;


/* =========================================================
   أدوات عامة
========================================================= */

function money(value) {
  return "AED " + Number(value || 0).toFixed(2);
}


function formatDateTime(value) {

  if (!value) return "—";

  try {

    return new Date(value).toLocaleString(
      "ar-AE",
      {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      }
    );

  } catch (e) {

    return value;
  }
}


function formatDate(value) {

  if (!value) return "—";

  try {

    return new Date(value).toLocaleDateString(
      "ar-AE",
      {
        year: "numeric",
        month: "long",
        day: "numeric"
      }
    );

  } catch (e) {

    return value;
  }
}


function statusLabel(
  status,
  receiptStatus
) {

  if (
    status === "delivered" &&
    receiptStatus === "confirmed"
  ) {
    return "تم الاستلام";
  }

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
      "تم الإلغاء"
  };

  return labels[status] ||
    status ||
    "—";
}


function paymentStatusLabel(status) {

  const labels = {

    unpaid:
      "غير مدفوع",

    pending:
      "بانتظار الدفع",

    paid:
      "مدفوع",

    refunded:
      "مسترد"
  };

  return labels[status] ||
    status ||
    "غير مدفوع";
}


function paymentMethodLabel(method) {

  const labels = {

    pilot_no_charge:
      "طلب تجريبي / بدون تحصيل",

    card:
      "بطاقة بنكية",

    apple_pay:
      "Apple Pay",

    cash:
      "نقداً",

    bank_transfer:
      "تحويل بنكي"
  };

  return labels[method] ||
    method ||
    "غير محدد";
}


function invoiceStatusLabel(status) {

  const labels = {

    draft:
      "مسودة",

    issued:
      "صادرة",

    approved:
      "معتمدة",

    paid:
      "مدفوعة",

    cancelled:
      "ملغاة"
  };

  return labels[status] ||
    status ||
    "—";
}


function setText(id, value) {

  const element =
    document.getElementById(id);

  if (element) {

    element.textContent =
      value ?? "—";
  }
}


function getOrderBuyerId(order) {

  if (!order) return null;

  return (
    order.user_id ||
    order.buyer_id ||
    null
  );
}


/* =========================================================
   رقم الطلب من الرابط
========================================================= */

function getOrderNoFromURL() {

  const params =
    new URLSearchParams(
      window.location.search
    );

  return params.get("order");
}


/* =========================================================
   المستخدم الحالي
========================================================= */

async function loadCurrentUser() {

  CurrentUser = null;

  try {

    if (
      window.Bahrna &&
      typeof Bahrna.getCurrentUser ===
        "function"
    ) {

      CurrentUser =
        await Bahrna.getCurrentUser();
    }

  } catch (e) {

    console.warn(
      "تعذر قراءة المستخدم الحالي",
      e
    );
  }

  return CurrentUser;
}


/* =========================================================
   تحميل الطلب
========================================================= */

async function loadOrderDetails() {

  const orderNo =
    getOrderNoFromURL();

  if (!orderNo) {

    showError(
      "لم يتم تحديد رقم الطلب في الرابط."
    );

    return;
  }

  if (
    !window.Bahrna ||
    !Bahrna.client
  ) {

    showError(
      "الاتصال بقاعدة البيانات غير متاح."
    );

    return;
  }

  try {

    await loadCurrentUser();

    const {
      data,
      error
    } = await Bahrna.client

      .from("orders")

      .select(`
        *,
        order_items (
          *
        )
      `)

      .eq(
        "order_no",
        orderNo
      )

      .single();

    if (error) {
      throw error;
    }

    if (!data) {

      throw new Error(
        "الطلب غير موجود"
      );
    }

    CurrentOrder =
      data;

    renderOrder(data);

    await loadBuyerInfo(data);

    await loadSupplierInfo(data);

    renderReceiptSection(data);

    await loadInvoice(data);

  } catch (e) {

    console.error(
      "ORDER DETAILS ERROR:",
      e
    );

    showError(
      "تعذر تحميل تفاصيل الطلب: " +
      (e.message || e)
    );
  }
}


/* =========================================================
   عرض الطلب
========================================================= */

function renderOrder(order) {

  const trackingStatus =
    order.tracking_status ||
    order.status ||
    "pending";

  setText(
    "orderNo",
    order.order_no
  );

  setText(
    "orderStatus",
    statusLabel(
      trackingStatus,
      order.receipt_status
    )
  );

  setText(
    "orderDate",
    formatDateTime(
      order.created_at
    )
  );

  setText(
    "paymentMethod",
    paymentMethodLabel(
      order.payment_method
    )
  );

  setText(
    "paymentStatus",
    paymentStatusLabel(
      order.payment_status
    )
  );

  const address =
    order.delivery_address ||
    {};

  setText(
    "deliveryEmirate",
    address.emirate || "—"
  );

  setText(
    "deliveryArea",
    address.area || "—"
  );

  setText(
    "deliveryAddress",
    address.address || "—"
  );

  setText(
    "subtotal",
    money(order.subtotal)
  );

  setText(
    "deliveryFee",
    money(order.delivery_fee)
  );

  setText(
    "vat",
    money(order.vat)
  );

  setText(
    "orderTotal",
    money(order.total)
  );

  renderItems(
    order.order_items || []
  );

  renderTimeline(
    trackingStatus,
    order.receipt_status
  );

  setText(
    "trackingMessage",
    trackingMessage(
      trackingStatus,
      order.receipt_status
    )
  );
}


/* =========================================================
   المنتجات
========================================================= */

function renderItems(items) {

  const tbody =
    document.getElementById(
      "orderItems"
    );

  if (!tbody) return;

  if (!items.length) {

    tbody.innerHTML = `

      <tr>

        <td colspan="4">
          لا توجد منتجات مسجلة على الطلب.
        </td>

      </tr>

    `;

    return;
  }

  tbody.innerHTML =
    items.map(
      item => `

        <tr>

          <td>

            <strong>
              ${item.product_name || "منتج"}
            </strong>

          </td>

          <td>

            ${Number(item.qty_kg || 0)}
            كجم

          </td>

          <td>

            ${money(item.unit_price)}

          </td>

          <td>

            <strong>
              ${money(item.line_total)}
            </strong>

          </td>

        </tr>

      `
    ).join("");
}


/* =========================================================
   مراحل الطلب
========================================================= */

function renderTimeline(
  status,
  receiptStatus
) {

  let current = 0;

  if (status === "confirmed") {
    current = 0;
  }

  if (status === "preparing") {
    current = 1;
  }

  if (
    status === "out_for_delivery"
  ) {
    current = 2;
  }

  if (status === "delivered") {
    current = 3;
  }

  if (
    status === "delivered" &&
    receiptStatus === "confirmed"
  ) {
    current = 4;
  }

  document
    .querySelectorAll(
      ".timeline-step"
    )

    .forEach(
      (step, index) => {

        step.classList.remove(
          "done",
          "current"
        );

        if (index < current) {

          step.classList.add(
            "done"
          );
        }

        if (index === current) {

          step.classList.add(
            "current"
          );
        }

        if (
          receiptStatus ===
            "confirmed" &&
          index <= 4
        ) {

          step.classList.remove(
            "current"
          );

          step.classList.add(
            "done"
          );
        }
      }
    );
}


/* =========================================================
   رسالة التنفيذ
========================================================= */

function trackingMessage(
  status,
  receiptStatus
) {

  if (
    status === "delivered" &&
    receiptStatus === "confirmed"
  ) {

    return (
      "تم تأكيد استلام الطلب " +
      "من المشتري بنجاح."
    );
  }

  const messages = {

    pending:
      "تم استلام الطلب وهو بانتظار تأكيد المورد.",

    confirmed:
      "تم تأكيد الطلب من المورد وسيبدأ التجهيز.",

    preparing:
      "المورد يقوم حالياً بتجهيز الطلب.",

    out_for_delivery:
      "تم تجهيز الطلب وخرج للتوصيل.",

    delivered:
      "أفاد المورد بأنه تم تسليم الطلب، وبانتظار تأكيد الاستلام من المشتري.",

    cancelled:
      "تم إلغاء الطلب."
  };

  return (
    messages[status] ||
    "جاري متابعة حالة الطلب."
  );
}


/* =========================================================
   تأكيد استلام المشتري
========================================================= */

function renderReceiptSection(order) {

  const box =
    document.getElementById(
      "receiptBox"
    );

  const button =
    document.getElementById(
      "confirmReceiptBtn"
    );

  const title =
    document.getElementById(
      "receiptTitle"
    );

  const message =
    document.getElementById(
      "receiptMessage"
    );

  const date =
    document.getElementById(
      "receiptDate"
    );

  if (!box) return;

  const trackingStatus =
    order.tracking_status ||
    order.status;

  if (
    trackingStatus !== "delivered"
  ) {

    box.style.display =
      "none";

    return;
  }

  box.style.display =
    "block";

  if (
    order.receipt_status ===
      "confirmed"
  ) {

    box.classList.add(
      "receipt-success"
    );

    if (title) {

      title.textContent =
        "✅ تم تأكيد الاستلام";
    }

    if (message) {

      message.textContent =
        "تم استلام الطلب وإغلاق مرحلة التسليم بنجاح.";
    }

    if (button) {

      button.style.display =
        "none";
    }

    if (
      date &&
      order.buyer_received_at
    ) {

      date.style.display =
        "block";

      date.textContent =
        "تاريخ تأكيد الاستلام: " +
        formatDateTime(
          order.buyer_received_at
        );
    }

    return;
  }

  const buyerId =
    getOrderBuyerId(order);

  const isBuyer =
    CurrentUser &&
    buyerId &&
    String(CurrentUser.id) ===
      String(buyerId);

  if (isBuyer) {

    if (title) {

      title.textContent =
        "تأكيد استلام الطلب";
    }

    if (message) {

      message.textContent =
        "إذا استلمت المنتجات فعلياً وبالحالة المتفق عليها، اضغط تأكيد الاستلام.";
    }

    if (button) {

      button.style.display =
        "inline-flex";

      button.disabled =
        false;

      button.textContent =
        "✓ تأكيد استلام الطلب";
    }

    return;
  }

  if (title) {

    title.textContent =
      "بانتظار تأكيد المشتري";
  }

  if (message) {

    message.textContent =
      "تم التسليم من المورد وبانتظار أن يؤكد المشتري استلام الطلب.";
  }

  if (button) {

    button.style.display =
      "none";
  }
}


/* =========================================================
   تنفيذ تأكيد الاستلام
========================================================= */

async function confirmBuyerReceipt() {

  if (!CurrentOrder) {

    alert(
      "تعذر تحديد الطلب"
    );

    return;
  }

  const trackingStatus =
    CurrentOrder.tracking_status ||
    CurrentOrder.status;

  if (
    trackingStatus !== "delivered"
  ) {

    alert(
      "لا يمكن تأكيد الاستلام قبل وصول حالة الطلب إلى تم التسليم."
    );

    return;
  }

  if (
    CurrentOrder.receipt_status ===
      "confirmed"
  ) {

    alert(
      "تم تأكيد استلام هذا الطلب مسبقاً."
    );

    return;
  }

  await loadCurrentUser();

  const buyerId =
    getOrderBuyerId(
      CurrentOrder
    );

  if (!CurrentUser) {

    alert(
      "يرجى تسجيل الدخول بحساب المشتري أولاً."
    );

    return;
  }

  if (
    !buyerId ||
    String(CurrentUser.id) !==
      String(buyerId)
  ) {

    alert(
      "تأكيد الاستلام متاح للمشتري صاحب الطلب فقط."
    );

    return;
  }

  const ok =
    confirm(
      "هل تؤكد أنك استلمت الطلب " +
      CurrentOrder.order_no +
      "؟\n\n" +
      "بعد التأكيد سيتم إغلاق مرحلة التسليم والانتقال للفاتورة."
    );

  if (!ok) return;

  const button =
    document.getElementById(
      "confirmReceiptBtn"
    );

  try {

    if (button) {

      button.disabled =
        true;

      button.textContent =
        "جاري تأكيد الاستلام...";
    }

    const {
      error
    } = await Bahrna.client

      .from("orders")

      .update({

        receipt_status:
          "confirmed",

        buyer_received_at:
          new Date().toISOString()

      })

      .eq(
        "id",
        CurrentOrder.id
      );

    if (error) {
      throw error;
    }

    alert(
      "✅ تم تأكيد استلام الطلب بنجاح"
    );

    await loadOrderDetails();

  } catch (e) {

    console.error(
      "RECEIPT CONFIRM ERROR:",
      e
    );

    alert(
      "تعذر تأكيد الاستلام: " +
      (e.message || e)
    );

    if (button) {

      button.disabled =
        false;

      button.textContent =
        "✓ تأكيد استلام الطلب";
    }
  }
}


/* =========================================================
   بيانات المشتري
========================================================= */

async function loadBuyerInfo(order) {

  try {

    const buyerId =
      getOrderBuyerId(order);

    if (!buyerId) return;

    const {
      data,
      error
    } = await Bahrna.client

      .from("profiles")

      .select("*")

      .eq(
        "id",
        buyerId
      )

      .maybeSingle();

    if (
      !error &&
      data
    ) {

      const name =
        data.full_name ||
        data.display_name ||
        data.company_name ||
        data.name;

      if (name) {

        setText(
          "buyerName",
          name
        );
      }
    }

  } catch (e) {

    console.log(
      "Buyer profile not available"
    );
  }
}


/* =========================================================
   بيانات المورد
========================================================= */

async function loadSupplierInfo(order) {

  CurrentSupplier = null;

  try {

    const firstItem =
      (order.order_items || [])
      .find(
        item =>
          item.product_id
      );

    if (!firstItem) {

      setText(
        "supplierName",
        "بحرنا وشراعنا"
      );

      setText(
        "supplierStatus",
        "مورد مسجل"
      );

      renderInvoiceSection();

      return;
    }

    const {
      data,
      error
    } = await Bahrna.client

      .from("products")

      .select(`
        id,
        supplier_id,
        supplier:suppliers (
          id,
          owner_id,
          display_name,
          verified,
          emirate
        )
      `)

      .eq(
        "id",
        firstItem.product_id
      )

      .maybeSingle();

    if (
      error ||
      !data
    ) {

      throw (
        error ||
        new Error(
          "Supplier not found"
        )
      );
    }

    CurrentSupplier =
      data.supplier ||
      null;

    setText(
      "supplierName",
      CurrentSupplier?.display_name ||
      "بحرنا وشراعنا"
    );

    setText(
      "supplierStatus",
      CurrentSupplier?.verified
        ? "✓ مورد موثق"
        : "مورد مسجل"
    );

    renderInvoiceSection();

  } catch (e) {

    console.warn(
      "تعذر تحميل المورد",
      e
    );

    setText(
      "supplierName",
      "بحرنا وشراعنا"
    );

    setText(
      "supplierStatus",
      "مورد مسجل"
    );

    renderInvoiceSection();
  }
}


/* =========================================================
   تحميل الفاتورة
========================================================= */

async function loadInvoice(order) {

  CurrentInvoice = null;

  try {

    const {
      data,
      error
    } = await Bahrna.client

      .from("invoices")

      .select("*")

      .eq(
        "order_id",
        order.id
      )

      .maybeSingle();

    if (error) {

      console.warn(
        "تعذر قراءة الفاتورة:",
        error
      );

    } else {

      CurrentInvoice =
        data || null;
    }

  } catch (e) {

    console.warn(
      "Invoice load error",
      e
    );
  }

  renderInvoiceSection();
}


/* =========================================================
   إنشاء واجهة الفاتورة ديناميكياً
========================================================= */

function ensureInvoiceSection() {

  let box =
    document.getElementById(
      "invoiceSection"
    );

  if (box) return box;

  const receiptBox =
    document.getElementById(
      "receiptBox"
    );

  if (!receiptBox) return null;

  box =
    document.createElement("div");

  box.id =
    "invoiceSection";

  box.style.cssText = `
    margin-top:20px;
    padding:22px;
    border:1px solid #dfe7ef;
    border-radius:16px;
    background:#ffffff;
  `;

  receiptBox.insertAdjacentElement(
    "afterend",
    box
  );

  return box;
}


/* =========================================================
   عرض مرحلة الفاتورة
========================================================= */

function renderInvoiceSection() {

  const box =
    ensureInvoiceSection();

  if (!box) return;

  if (!CurrentOrder) {

    box.style.display =
      "none";

    return;
  }

  if (
    CurrentOrder.receipt_status !==
      "confirmed"
  ) {

    box.style.display =
      "none";

    return;
  }

  box.style.display =
    "block";

  const buyerId =
    getOrderBuyerId(
      CurrentOrder
    );

  const isBuyer =
    CurrentUser &&
    buyerId &&
    String(CurrentUser.id) ===
      String(buyerId);

  const isSupplier =
    CurrentUser &&
    CurrentSupplier?.owner_id &&
    String(CurrentUser.id) ===
      String(CurrentSupplier.owner_id);


  /* -----------------------------------------
     الفاتورة موجودة بالفعل
  ----------------------------------------- */

  if (CurrentInvoice) {

    box.innerHTML = `

      <div
        style="
          display:flex;
          justify-content:space-between;
          align-items:flex-start;
          gap:20px;
          flex-wrap:wrap;
        "
      >

        <div>

          <h2
            style="
              margin-top:0;
              color:#062f5f;
            "
          >
            🧾 الفاتورة
          </h2>

          <p class="muted">
            الفاتورة المرتبطة بهذا الطلب.
          </p>

        </div>

        <span class="status ok">

          ${invoiceStatusLabel(
            CurrentInvoice.status
          )}

        </span>

      </div>


      <div
        style="
          display:grid;
          grid-template-columns:
            repeat(2,minmax(0,1fr));
          gap:14px;
          margin-top:16px;
        "
      >

        <div>

          <div class="muted">
            رقم الفاتورة
          </div>

          <strong>
            ${CurrentInvoice.invoice_no}
          </strong>

        </div>


        <div>

          <div class="muted">
            رقم الطلب
          </div>

          <strong>
            ${CurrentInvoice.order_no}
          </strong>

        </div>


        <div>

          <div class="muted">
            تاريخ الإصدار
          </div>

          <strong>
            ${formatDateTime(
              CurrentInvoice.issued_at
            )}
          </strong>

        </div>


        <div>

          <div class="muted">
            تاريخ الاستحقاق
          </div>

          <strong>
            ${formatDate(
              CurrentInvoice.due_date
            )}
          </strong>

        </div>


        <div>

          <div class="muted">
            قيمة المنتجات
          </div>

          <strong>
            ${money(
              CurrentInvoice.subtotal
            )}
          </strong>

        </div>


        <div>

          <div class="muted">
            الضريبة
          </div>

          <strong>
            ${money(
              CurrentInvoice.vat
            )}
          </strong>

        </div>

      </div>


      <div
        style="
          margin-top:18px;
          padding-top:16px;
          border-top:1px solid #dfe7ef;
        "
      >

        <div class="muted">
          إجمالي الفاتورة
        </div>

        <div
          style="
            font-size:30px;
            font-weight:800;
            color:#062f5f;
          "
        >
          ${money(
            CurrentInvoice.total
          )}
        </div>

      </div>


      ${
        isBuyer
          ? `
            <p
              style="
                margin-top:18px;
                color:#52677c;
              "
            >
              تم إصدار الفاتورة من المورد
              وهي متاحة الآن للمشتري.
            </p>
          `
          : ""
      }

    `;

    return;
  }


  /* -----------------------------------------
     لا توجد فاتورة بعد
  ----------------------------------------- */

  if (isSupplier) {

    box.innerHTML = `

      <h2
        style="
          margin-top:0;
          color:#062f5f;
        "
      >
        🧾 إصدار فاتورة
      </h2>

      <p class="muted">

        تم تأكيد استلام الطلب من المشتري.
        يمكنك الآن إصدار الفاتورة المرتبطة
        بالطلب

        <strong>
          ${CurrentOrder.order_no}
        </strong>.

      </p>


      <div
        style="
          margin:18px 0;
          padding:16px;
          border-radius:12px;
          background:#f7fafc;
        "
      >

        <div class="muted">
          قيمة الفاتورة
        </div>

        <div
          style="
            font-size:28px;
            font-weight:800;
            color:#062f5f;
          "
        >

          ${money(
            CurrentOrder.total
          )}

        </div>

      </div>


      <button
        class="btn btn-primary"
        onclick="issueSupplierInvoice()"
      >

        إصدار الفاتورة

      </button>

    `;

    return;
  }


  if (isBuyer) {

    box.innerHTML = `

      <h2
        style="
          margin-top:0;
          color:#062f5f;
        "
      >
        🧾 الفاتورة
      </h2>

      <p class="muted">

        تم تأكيد استلام الطلب.
        بانتظار المورد لإصدار الفاتورة.

      </p>

    `;

    return;
  }


  box.innerHTML = `

    <h2
      style="
        margin-top:0;
        color:#062f5f;
      "
    >
      🧾 الفاتورة
    </h2>

    <p class="muted">

      تم تأكيد استلام الطلب.
      بانتظار إصدار الفاتورة.

    </p>

  `;
}


/* =========================================================
   إنشاء رقم فاتورة
========================================================= */

function generateInvoiceNo() {

  const now =
    new Date();

  const date =
    now
      .toISOString()
      .slice(0,10)
      .replaceAll("-", "");

  let random;

  try {

    random =
      crypto
        .randomUUID()
        .replaceAll("-", "")
        .slice(0,8)
        .toUpperCase();

  } catch (e) {

    random =
      Math.random()
        .toString(36)
        .slice(2,10)
        .toUpperCase();
  }

  return (
    "INV-" +
    date +
    "-" +
    random
  );
}


/* =========================================================
   المورد يصدر الفاتورة
========================================================= */

async function issueSupplierInvoice() {

  if (!CurrentOrder) {

    alert(
      "تعذر تحديد الطلب"
    );

    return;
  }

  if (
    CurrentOrder.receipt_status !==
      "confirmed"
  ) {

    alert(
      "لا يمكن إصدار الفاتورة قبل تأكيد المشتري استلام الطلب."
    );

    return;
  }

  await loadCurrentUser();

  if (
    !CurrentUser ||
    !CurrentSupplier?.owner_id ||
    String(CurrentUser.id) !==
      String(CurrentSupplier.owner_id)
  ) {

    alert(
      "إصدار الفاتورة متاح للمورد صاحب الطلب فقط."
    );

    return;
  }

  if (CurrentInvoice) {

    alert(
      "تم إصدار فاتورة لهذا الطلب مسبقاً."
    );

    return;
  }

  const ok =
    confirm(
      "هل تريد إصدار فاتورة للطلب " +
      CurrentOrder.order_no +
      " بقيمة " +
      money(CurrentOrder.total) +
      "؟"
    );

  if (!ok) return;

  try {

    const dueDate =
      new Date();

    dueDate.setDate(
      dueDate.getDate() + 7
    );

    const buyerId =
      getOrderBuyerId(
        CurrentOrder
      );

    const invoiceData = {

      invoice_no:
        generateInvoiceNo(),

      order_id:
        CurrentOrder.id,

      order_no:
        CurrentOrder.order_no,

      supplier_id:
        CurrentSupplier.id,

      buyer_user_id:
        buyerId,

      subtotal:
        Number(
          CurrentOrder.subtotal ||
          CurrentOrder.total ||
          0
        ),

      delivery_fee:
        Number(
          CurrentOrder.delivery_fee ||
          0
        ),

      vat:
        Number(
          CurrentOrder.vat ||
          0
        ),

      total:
        Number(
          CurrentOrder.total ||
          0
        ),

      status:
        "issued",

      issued_at:
        new Date().toISOString(),

      due_date:
        dueDate
          .toISOString()
          .slice(0,10),

      notes:
        "فاتورة طلب شراء مؤسسي B2B"
    };

    const {
      data,
      error
    } = await Bahrna.client

      .from("invoices")

      .insert(
        invoiceData
      )

      .select("*")

      .single();

    if (error) {
      throw error;
    }

    CurrentInvoice =
      data;

    alert(
      "✅ تم إصدار الفاتورة بنجاح\n\n" +
      "رقم الفاتورة: " +
      data.invoice_no
    );

    renderInvoiceSection();

  } catch (e) {

    console.error(
      "ISSUE INVOICE ERROR:",
      e
    );

    alert(
      "تعذر إصدار الفاتورة: " +
      (e.message || e)
    );
  }
}


/* =========================================================
   تحديث الحالة
========================================================= */

async function refreshOrder() {

  setText(
    "trackingMessage",
    "جاري تحديث حالة الطلب..."
  );

  await loadOrderDetails();
}


/* =========================================================
   عرض الخطأ
========================================================= */

function showError(message) {

  const box =
    document.getElementById(
      "orderError"
    );

  if (box) {

    box.style.display =
      "block";

    box.textContent =
      message;
  }

  setText(
    "orderNo",
    "تعذر تحميل الطلب"
  );
}


/* =========================================================
   تشغيل الصفحة
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  loadOrderDetails
);

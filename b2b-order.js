/* =========================================================
   BAHRNA & SHRAANA
   B2B ORDER DETAILS
========================================================= */


let CurrentOrder = null;


/* =========================================================
   أدوات عامة
========================================================= */

function money(value) {

  return "AED " +
    Number(value || 0).toFixed(2);

}


function formatDateTime(value) {

  if (!value) {
    return "—";
  }


  try {

    return new Date(value)
      .toLocaleString(
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


function statusLabel(status) {

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


  return labels[status] || status || "—";

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
    "غير محدد";

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
      "نقداً"

  };


  return labels[method] ||
    method ||
    "غير محدد";

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

    const sb =
      Bahrna.client;


    /*
      استخدام * يجعل الصفحة أكثر تحملاً
      لأي أعمدة إضافية موجودة في orders.
    */

    const {
      data,
      error
    } = await sb

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


    renderOrder(
      data
    );


    await loadBuyerInfo(
      data
    );


    await loadSupplierInfo(
      data
    );


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
      trackingStatus
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
    money(
      order.subtotal
    )
  );


  setText(
    "deliveryFee",
    money(
      order.delivery_fee
    )
  );


  setText(
    "vat",
    money(
      order.vat
    )
  );


  setText(
    "orderTotal",
    money(
      order.total
    )
  );


  renderItems(
    order.order_items ||
    []
  );


  renderTimeline(
    trackingStatus
  );


  setText(
    "trackingMessage",
    trackingMessage(
      trackingStatus
    )
  );

}


/* =========================================================
   عرض المنتجات
========================================================= */

function renderItems(items) {

  const tbody =
    document.getElementById(
      "orderItems"
    );


  if (!tbody) {
    return;
  }


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
    items

      .map(
        item => `

          <tr>

            <td>

              <strong>

                ${
                  item.product_name ||
                  "منتج"
                }

              </strong>

            </td>


            <td>

              ${
                Number(
                  item.qty_kg || 0
                )
              }
              كجم

            </td>


            <td>

              ${
                money(
                  item.unit_price
                )
              }

            </td>


            <td>

              <strong>

                ${
                  money(
                    item.line_total
                  )
                }

              </strong>

            </td>

          </tr>

        `
      )

      .join("");

}


/* =========================================================
   Timeline
========================================================= */

function renderTimeline(status) {

  const flow = [

    "confirmed",

    "preparing",

    "out_for_delivery",

    "delivered"

  ];


  let current =
    flow.indexOf(
      status
    );


  if (current < 0) {

    current = 0;

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
          status === "delivered" &&
          index <= current
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
   رسالة حالة الطلب
========================================================= */

function trackingMessage(status) {

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
      "تم تسليم الطلب بنجاح.",

    cancelled:
      "تم إلغاء الطلب."

  };


  return messages[status] ||
    "جاري متابعة حالة الطلب.";

}


/* =========================================================
   بيانات المشتري
========================================================= */

async function loadBuyerInfo(order) {

  try {

    const buyerId =
      order.buyer_id ||
      order.user_id;


    if (!buyerId) {

      return;

    }


    /*
      محاولة قراءة الاسم من profiles
      إن كان الجدول موجوداً.
    */

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

  try {

    const firstItem =
      (order.order_items || [])
      .find(
        x => x.product_id
      );


    if (!firstItem) {

      setText(
        "supplierName",
        "بحرنا وشراعنا"
      );

      setText(
        "supplierStatus",
        "مورد معتمد"
      );

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

      throw error ||
        new Error(
          "Supplier not found"
        );

    }


    const supplier =
      data.supplier;


    setText(
      "supplierName",
      supplier?.display_name ||
      "بحرنا وشراعنا"
    );


    setText(
      "supplierStatus",
      supplier?.verified
        ? "✓ مورد موثق"
        : "مورد مسجل"
    );


  } catch (e) {

    setText(
      "supplierName",
      "بحرنا وشراعنا"
    );


    setText(
      "supplierStatus",
      "مورد مسجل"
    );

  }

}


/* =========================================================
   تحديث
========================================================= */

async function refreshOrder() {

  setText(
    "trackingMessage",
    "جاري تحديث حالة الطلب..."
  );


  await loadOrderDetails();

}


/* =========================================================
   Helpers
========================================================= */

function setText(
  id,
  value
) {

  const el =
    document.getElementById(
      id
    );


  if (el) {

    el.textContent =
      value ?? "—";

  }

}


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
   Start
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  loadOrderDetails
);

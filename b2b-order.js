/* =========================================================
   BAHRNA & SHRAANA
   B2B ORDER DETAILS
   Delivery + Buyer Receipt Confirmation
========================================================= */


let CurrentOrder = null;

let CurrentUser = null;



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


  return params.get(
    "order"
  );
}



/* =========================================================
   المستخدم الحالي
========================================================= */

async function loadCurrentUser() {

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

    CurrentUser =
      null;
  }

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


    renderOrder(
      data
    );


    await loadBuyerInfo(
      data
    );


    await loadSupplierInfo(
      data
    );


    renderReceiptSection(
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

function renderTimeline(
  status,
  receiptStatus
) {

  const flow = [

    "confirmed",

    "preparing",

    "out_for_delivery",

    "delivered",

    "received"

  ];


  let current = 0;


  if (
    status === "confirmed"
  ) {

    current = 0;

  }


  if (
    status === "preparing"
  ) {

    current = 1;

  }


  if (
    status === "out_for_delivery"
  ) {

    current = 2;

  }


  if (
    status === "delivered"
  ) {

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


        if (
          index < current
        ) {

          step.classList.add(
            "done"
          );

        }


        if (
          index === current
        ) {

          step.classList.add(
            "current"
          );

        }


        if (
          receiptStatus === "confirmed" &&
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
   رسالة حالة الطلب
========================================================= */

function trackingMessage(
  status,
  receiptStatus
) {

  if (
    status === "delivered" &&
    receiptStatus === "confirmed"
  ) {

    return "تم تأكيد استلام الطلب من المشتري بنجاح.";
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


  return messages[status] ||
    "جاري متابعة حالة الطلب.";
}



/* =========================================================
   قسم تأكيد الاستلام
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


  if (!box) {
    return;
  }


  const trackingStatus =
    order.tracking_status ||
    order.status;


  /*
    لا يظهر قسم الاستلام
    قبل أن يعلن المورد التسليم
  */

  if (
    trackingStatus !== "delivered"
  ) {

    box.style.display =
      "none";

    return;
  }


  box.style.display =
    "block";


  /*
    تم تأكيد الاستلام مسبقاً
  */

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
        "أغلق المشتري مرحلة الاستلام بنجاح.";
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


  /*
    إذا لم يكن المستخدم الحالي
    هو المشتري صاحب الطلب
    لا نظهر زر التأكيد
  */

  const isBuyer =
    CurrentUser &&
    order.buyer_id &&
    CurrentUser.id ===
      order.buyer_id;


  if (!isBuyer) {

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


    return;
  }


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
  }

}



/* =========================================================
   المشتري يؤكد الاستلام
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


  if (
    !CurrentUser ||
    CurrentUser.id !==
      CurrentOrder.buyer_id
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


  if (!ok) {
    return;
  }


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
      data,
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
      )

      .eq(
        "buyer_id",
        CurrentUser.id
      )

      .select("*")

      .single();


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
      order.buyer_id ||
      order.user_id;


    if (!buyerId) {
      return;
    }


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
   تحديث الصفحة
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

  const element =
    document.getElementById(
      id
    );


  if (element) {

    element.textContent =
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

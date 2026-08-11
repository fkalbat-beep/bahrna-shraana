function loadSavedFlow() {
  try {
    return JSON.parse(
      localStorage.getItem("bahrna_orderflow") || "null"
    );
  } catch (e) {
    return null;
  }
}

const savedFlow = loadSavedFlow();

const OrderFlow = {

  cart:
    JSON.parse(
      localStorage.getItem("bahrna_cart") || "null"
    ) || [
      {
        id: "demo-hamour",
        name: "هامور محلي",
        price: 49.90,
        qty: 2
      }
    ],

  cut:
    savedFlow?.cut ||
    {
      name: "كامل",
      fee: 0
    },

  packaging:
    savedFlow?.packaging ||
    {
      name: "بدون ثلج",
      fee: 0
    },

  keepHeadBones:
    savedFlow?.keepHeadBones ?? true,

  address:
    savedFlow?.address ||
    {
      emirate: "دبي",
      area: "",
      address: ""
    },

  slot:
    savedFlow?.slot || "",

  deliveryFee: 10,

  vatRate: 0.05
};


/* =========================================
   حفظ بيانات الطلب
========================================= */

function persistFlow() {

  localStorage.setItem(
    "bahrna_orderflow",
    JSON.stringify(OrderFlow)
  );
}


function saveCart() {

  localStorage.setItem(
    "bahrna_cart",
    JSON.stringify(OrderFlow.cart)
  );

  persistFlow();
}


/* =========================================
   الحسابات
========================================= */

function money(n) {

  return "AED " +
    Number(n || 0).toFixed(2);
}


function cartSubtotal() {

  return OrderFlow.cart.reduce(
    (s, x) =>
      s +
      Number(x.price) *
      Number(x.qty),
    0
  );
}


function calcTotals() {

  const subtotal =
    cartSubtotal();

  const prep =
    Number(
      OrderFlow.cut.fee || 0
    );

  const pack =
    Number(
      OrderFlow.packaging.fee || 0
    );

  const delivery =
    Number(
      OrderFlow.deliveryFee || 0
    );

  const vat =
    (
      subtotal +
      prep +
      pack +
      delivery
    ) *
    OrderFlow.vatRate;

  const total =
    subtotal +
    prep +
    pack +
    delivery +
    vat;

  return {
    subtotal,
    prep,
    pack,
    delivery,
    vat,
    total
  };
}


/* =========================================
   السلة
========================================= */

function renderCart() {

  const wrap =
    document.getElementById(
      "cartRows"
    );

  if (!wrap) return;


  wrap.innerHTML =
    OrderFlow.cart.map(
      (x, i) => `

        <div class="cart-item">

          <div class="cart-thumb">
            🐟
          </div>

          <div>

            <strong>
              ${x.name}
            </strong>

            <div class="muted">
              ${money(x.price)} / كجم
            </div>

            <div class="stepper">

              <button
                onclick="changeQty(${i},-1)">
                −
              </button>

              <strong>
                ${x.qty} كجم
              </strong>

              <button
                onclick="changeQty(${i},1)">
                +
              </button>

            </div>

          </div>

          <div>

            <strong>
              ${money(
                x.price * x.qty
              )}
            </strong>

            <br>

            <button
              class="btn small"
              onclick="removeItem(${i})">
              حذف
            </button>

          </div>

        </div>

      `
    ).join("");


  const t =
    calcTotals();


  const cartSubtotalEl =
    document.getElementById(
      "cartSubtotal"
    );

  const cartTotalEl =
    document.getElementById(
      "cartTotal"
    );


  if (cartSubtotalEl) {

    cartSubtotalEl.textContent =
      money(t.subtotal);
  }


  if (cartTotalEl) {

    cartTotalEl.textContent =
      money(t.total);
  }
}


function changeQty(i, d) {

  OrderFlow.cart[i].qty =
    Math.max(
      1,
      Number(
        OrderFlow.cart[i].qty
      ) + d
    );

  saveCart();

  renderCart();

  renderSummary();
}


function removeItem(i) {

  OrderFlow.cart.splice(
    i,
    1
  );

  saveCart();

  renderCart();

  renderSummary();
}


/* =========================================
   التجهيز
========================================= */

function chooseCut(
  el,
  name,
  fee
) {

  document
    .querySelectorAll(
      "[data-cut]"
    )
    .forEach(
      x =>
        x.classList.remove(
          "active"
        )
    );


  el.classList.add(
    "active"
  );


  OrderFlow.cut = {
    name,
    fee: Number(fee)
  };


  persistFlow();


  const v =
    document.getElementById(
      "cutVideoTitle"
    );


  if (v) {

    v.textContent =
      "فيديو توضيحي: " +
      name;
  }


  renderSummary();
}


function choosePack(
  el,
  name,
  fee
) {

  document
    .querySelectorAll(
      "[data-pack]"
    )
    .forEach(
      x =>
        x.classList.remove(
          "active"
        )
    );


  el.classList.add(
    "active"
  );


  OrderFlow.packaging = {
    name,
    fee: Number(fee)
  };


  persistFlow();

  renderSummary();
}


function setKeep(v) {

  OrderFlow.keepHeadBones =
    v;

  persistFlow();

  renderSummary();
}


/* =========================================
   ملخص الطلب
========================================= */

function renderSummary() {

  const t =
    calcTotals();


  const vals = {

    sumSubtotal:
      t.subtotal,

    sumPrep:
      t.prep,

    sumPack:
      t.pack,

    sumDelivery:
      t.delivery,

    sumVat:
      t.vat,

    sumTotal:
      t.total
  };


  Object.entries(
    vals
  ).forEach(
    ([id, val]) => {

      const el =
        document.getElementById(
          id
        );

      if (el) {

        el.textContent =
          money(val);
      }
    }
  );


  const p =
    document.getElementById(
      "prepText"
    );


  if (p) {

    p.textContent =

      OrderFlow.cut.name +

      " • " +

      OrderFlow.packaging.name +

      " • " +

      (
        OrderFlow.keepHeadBones
          ? "مع الرأس والعظم"
          : "بدون الرأس والعظم"
      );
  }
}


/* =========================================
   التوصيل
========================================= */

function continueToDelivery() {

  persistFlow();

  location.href =
    "delivery.html";
}


function restoreDelivery() {

  const em =
    document.getElementById(
      "emirate"
    );

  const ar =
    document.getElementById(
      "area"
    );

  const ad =
    document.getElementById(
      "address"
    );

  const sl =
    document.getElementById(
      "slot"
    );


  if (
    em &&
    OrderFlow.address.emirate
  ) {

    em.value =
      OrderFlow.address.emirate;
  }


  if (ar) {

    ar.value =
      OrderFlow.address.area || "";
  }


  if (ad) {

    ad.value =
      OrderFlow.address.address || "";
  }


  if (
    sl &&
    OrderFlow.slot
  ) {

    sl.value =
      OrderFlow.slot;
  }
}


function confirmDelivery() {

  OrderFlow.address = {

    emirate:
      document.getElementById(
        "emirate"
      ).value,

    area:
      document.getElementById(
        "area"
      ).value,

    address:
      document.getElementById(
        "address"
      ).value
  };


  OrderFlow.slot =
    document.getElementById(
      "slot"
    ).value;


  persistFlow();


  location.href =
    "payment.html";
}


/* =========================================
   إنشاء طلب حقيقي
========================================= */

async function createPilotOrder() {

  const btn =
    document.getElementById(
      "confirmOrderBtn"
    );


  try {

    if (btn) {

      btn.disabled =
        true;

      btn.textContent =
        "جاري تسجيل الطلب...";
    }


    persistFlow();


    const t =
      calcTotals();


    if (
      !window.Bahrna?.configured
    ) {

      return createLocalFallback(
        t,
        "الموقع يعمل في وضع Demo لأن Supabase غير متصل."
      );
    }


    const user =
      await Bahrna.getCurrentUser();


    if (!user) {

      localStorage.setItem(
        "bahrna_return_after_login",
        "payment.html"
      );


      alert(
        "لإنشاء طلب حقيقي محفوظ في قاعدة البيانات، يرجى تسجيل الدخول أو إنشاء حساب أولاً."
      );


      location.href =
        "login.html";

      return;
    }


    const dbOrder =
      await Bahrna.createOrder(
        OrderFlow,
        t
      );


    const order = {

      orderNo:
        dbOrder.order_no,

      status:
        dbOrder.tracking_status ||
        dbOrder.status ||
        "confirmed",

      isReal:
        true,

      createdAt:
        dbOrder.created_at,

      items:
        OrderFlow.cart,

      cut:
        OrderFlow.cut,

      packaging:
        OrderFlow.packaging,

      keepHeadBones:
        OrderFlow.keepHeadBones,

      address:
        OrderFlow.address,

      slot:
        OrderFlow.slot,

      total:
        Number(
          dbOrder.total
        )
    };


    localStorage.setItem(
      "bahrna_last_order",
      JSON.stringify(order)
    );


    location.href =
      "confirmation.html";


  } catch (e) {

    console.error(e);


    if (
      e.message ===
      "LOGIN_REQUIRED"
    ) {

      alert(
        "يرجى تسجيل الدخول أولاً."
      );

      location.href =
        "login.html";

      return;
    }


    alert(
      "تعذر تسجيل الطلب في قاعدة البيانات: " +
      (e.message || e)
    );


    if (btn) {

      btn.disabled =
        false;

      btn.textContent =
        "تأكيد الطلب التجريبي";
    }
  }
}


/* =========================================
   وضع Demo
========================================= */

function createLocalFallback(
  t,
  note
) {

  const order = {

    orderNo:
      "DEMO-" +
      Date.now()
        .toString()
        .slice(-8),

    status:
      "confirmed",

    isReal:
      false,

    createdAt:
      new Date()
        .toISOString(),

    items:
      OrderFlow.cart,

    cut:
      OrderFlow.cut,

    packaging:
      OrderFlow.packaging,

    keepHeadBones:
      OrderFlow.keepHeadBones,

    address:
      OrderFlow.address,

    slot:
      OrderFlow.slot,

    total:
      t.total,

    note
  };


  localStorage.setItem(
    "bahrna_last_order",
    JSON.stringify(order)
  );


  location.href =
    "confirmation.html";
}


/* =========================================
   صفحة تأكيد الطلب
========================================= */

function renderConfirmation() {

  const o =
    JSON.parse(
      localStorage.getItem(
        "bahrna_last_order"
      ) || "null"
    );


  if (!o) return;


  const no =
    document.getElementById(
      "orderNo"
    );

  const tot =
    document.getElementById(
      "orderTotal"
    );

  const d =
    document.getElementById(
      "deliveryText"
    );

  const badge =
    document.getElementById(
      "orderMode"
    );


  if (no) {

    no.textContent =
      o.orderNo;
  }


  if (tot) {

    tot.textContent =
      money(o.total);
  }


  if (d) {

    d.textContent =

      (
        o.address?.emirate ||
        ""
      ) +

      " • " +

      (
        o.address?.area ||
        ""
      ) +

      " • " +

      (
        o.slot ||
        "موعد يحدد لاحقًا"
      );
  }


  if (badge) {

    badge.textContent =
      o.isReal

        ? "✓ محفوظ في Supabase — الدفع غير محصل"

        : "وضع Demo محلي";
  }
}


/* =========================================
   صفحة تتبع الطلب
========================================= */

async function renderTracking() {

  const local =
    JSON.parse(
      localStorage.getItem(
        "bahrna_last_order"
      ) || "null"
    );


  if (!local) {

    const cs =
      document.getElementById(
        "currentStatus"
      );

    if (cs) {

      cs.textContent =
        "لا يوجد طلب محفوظ للتتبع";
    }

    return;
  }


  let o = {
    ...local
  };


  /*
    إذا كان الطلب حقيقياً:
    نقرأ أحدث حالة مباشرة من Supabase.
  */

  if (
    local.isReal &&
    window.Bahrna?.configured
  ) {

    try {

      const fresh =
        await Bahrna.getOrderByNo(
          local.orderNo
        );


      if (fresh) {

        /*
          مهم جداً:
          tracking_status له الأولوية
          لأنه هو الذي يغيره المورد.
        */

        o = {

          ...local,

          status:
            fresh.tracking_status ||
            fresh.status ||
            local.status,

          total:
            Number(
              fresh.total ||
              local.total
            )

        };


        /*
          نحفظ آخر حالة محلياً أيضاً
          حتى تبقى متزامنة.
        */

        localStorage.setItem(
          "bahrna_last_order",
          JSON.stringify(o)
        );
      }

    } catch (e) {

      console.error(
        "تعذر تحديث حالة التتبع:",
        e
      );
    }
  }


  const no =
    document.getElementById(
      "trackOrderNo"
    );


  if (no) {

    no.textContent =
      o.orderNo;
  }


  /*
    الحالات التشغيلية التي اعتمدناها
    في لوحة المورد.
  */

  const flow = [

    "confirmed",

    "preparing",

    "out_for_delivery",

    "delivered"

  ];


  let current =
    flow.indexOf(
      o.status
    );


  if (current < 0) {

    /*
      الطلب القديم pending
      يعرض في أول مرحلة.
    */

    if (
      o.status === "pending"
    ) {

      current = 0;

    } else {

      current = 0;
    }
  }


  document
    .querySelectorAll(
      ".track-step"
    )
    .forEach(
      (el, i) => {

        el.classList.remove(
          "done",
          "current"
        );


        if (i < current) {

          el.classList.add(
            "done"
          );

        } else if (
          i === current
        ) {

          el.classList.add(
            "current"
          );
        }
      }
    );


  const statusLabels = {

    pending:
      "بانتظار تأكيد الطلب",

    confirmed:
      "تم تأكيد الطلب",

    preparing:
      "جاري التجهيز",

    out_for_delivery:
      "خرج للتوصيل",

    delivered:
      "تم التسليم",

    cancelled:
      "تم إلغاء الطلب"
  };


  const cs =
    document.getElementById(
      "currentStatus"
    );


  if (cs) {

    cs.textContent =
      statusLabels[o.status] ||
      o.status;
  }


  const sim =
    document.getElementById(
      "simulateBtn"
    );


  const note =
    document.getElementById(
      "trackingNote"
    );


  /*
    الطلب الحقيقي:
    لا نسمح بالمحاكاة.
  */

  if (local.isReal) {

    if (sim) {

      sim.style.display =
        "none";
    }


    if (note) {

      note.textContent =
        "الحالة محدثة مباشرة من نظام بحرنا وشراعنا وفق آخر تحديث من المورد.";
    }

  } else {

    /*
      Demo فقط
    */

    if (sim) {

      sim.style.display =
        "";
    }


    if (note) {

      note.textContent =
        "هذا طلب تجريبي محلي ويمكن محاكاة انتقاله بين المراحل.";
    }
  }
}


/* =========================================
   محاكاة التتبع للـ Demo فقط
========================================= */

function advanceTracking() {

  const o =
    JSON.parse(
      localStorage.getItem(
        "bahrna_last_order"
      ) || "null"
    );


  if (
    !o ||
    o.isReal
  ) {

    return;
  }


  const flow = [

    "confirmed",

    "preparing",

    "out_for_delivery",

    "delivered"

  ];


  let i =
    flow.indexOf(
      o.status
    );


  if (i < 0) {

    i = 0;
  }


  if (
    i <
    flow.length - 1
  ) {

    o.status =
      flow[i + 1];
  }


  localStorage.setItem(
    "bahrna_last_order",
    JSON.stringify(o)
  );


  location.reload();
}


/* =========================================
   تشغيل الصفحات
========================================= */

document.addEventListener(
  "DOMContentLoaded",
  async () => {

    renderCart();

    renderSummary();

    restoreDelivery();

    renderConfirmation();

    await renderTracking();

  }
);

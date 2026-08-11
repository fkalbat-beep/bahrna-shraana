const SupplierDemo = {
  offers: [],
  orders: []
};

let offerModes = new Set(["retail"]);

/* =========================================
   أدوات عامة
========================================= */

function money(n) {
  return "AED " + Number(n || 0).toFixed(2);
}

function showSupplierPanel(id, el) {
  document.querySelectorAll(".supplier-panel")
    .forEach(p => p.classList.remove("active"));

  const panel = document.getElementById(id);
  if (panel) panel.classList.add("active");

  document.querySelectorAll(".supplier-sidebar a")
    .forEach(a => a.classList.remove("active"));

  if (el) el.classList.add("active");
}


/* =========================================
   الحصول على المورد الحالي
========================================= */

async function getCurrentSupplier() {

  if (!window.Bahrna || !Bahrna.client) {
    throw new Error("Supabase غير متصل");
  }

  const sb = Bahrna.client;

  const user = await Bahrna.getCurrentUser();

  if (!user) {
    throw new Error("يجب تسجيل الدخول بحساب المورد");
  }

  const { data, error } = await sb
    .from("suppliers")
    .select("id,owner_id,display_name,emirate,verified")
    .eq("owner_id", user.id)
    .single();

  if (error) {
    console.error("خطأ قراءة المورد:", error);
    throw new Error("لم يتم العثور على سجل المورد لهذا الحساب");
  }

  return data;
}


/* =========================================
   قراءة عروض المورد الحقيقية من products
========================================= */

async function loadSupplierOffers() {

  try {

    const sb = Bahrna.client;
    const supplier = await getCurrentSupplier();

    const { data, error } = await sb
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
        active
      `)
      .eq("supplier_id", supplier.id)
      .order("created_at", { ascending: false });

    if (error) {
      console.error("خطأ تحميل عروض المورد:", error);
      SupplierDemo.offers = [];
      return;
    }

    SupplierDemo.offers = (data || []).map(x => ({
      id: x.id,
      name: x.name_ar,
      qty: Number(x.stock_kg || 0),
      retail: Number(x.price_per_kg || 0),
      wholesale: Number(x.wholesale_price_per_kg || 0),
      auction: false,
      status: x.active ? "active" : "paused",
      arrived: x.arrived_at || "",
      supplier: supplier.display_name || "مورد",
      origin: x.origin || "الإمارات",
      isReal: true
    }));

  } catch (e) {

    console.error(e);
    SupplierDemo.offers = [];

  }
}


/* =========================================
   قراءة الطلبات
========================================= */

async function loadSupplierOrders() {

  if (!window.Bahrna || !Bahrna.client) {
    console.warn("Supabase غير متصل");
    SupplierDemo.orders = [];
    return;
  }

  const sb = Bahrna.client;

  const { data, error } = await sb
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
    .order("created_at", { ascending: false });

  if (error) {
    console.error("خطأ تحميل الطلبات:", error);
    SupplierDemo.orders = [];
    return;
  }

  SupplierDemo.orders = (data || []).map(order => {

    const items = order.order_items || [];

    const itemText = items.length
      ? items.map(i =>
          `${i.product_name || "منتج"} ${Number(i.qty_kg || 0)} كجم`
        ).join("، ")
      : "—";

    return {
      id: order.id,
      no: order.order_no,
      item: itemText,
      total: Number(order.total || 0),
      status: order.tracking_status || order.status || "pending"
    };
  });
}


/* =========================================
   عرض لوحة المورد
========================================= */

function renderSupplier() {

  const activeOffers = document.getElementById("activeOffers");
  const stockKg = document.getElementById("stockKg");
  const pendingOrders = document.getElementById("pendingOrders");
  const supplierGMV = document.getElementById("supplierGMV");
  const offerRows = document.getElementById("offerRows");
  const supplierOrderRows = document.getElementById("supplierOrderRows");

  if (activeOffers) {
    activeOffers.textContent =
      SupplierDemo.offers.filter(x => x.status === "active").length;
  }

  if (stockKg) {
    stockKg.textContent =
      SupplierDemo.offers.reduce(
        (s, x) => s + Number(x.qty || 0),
        0
      ) + " كجم";
  }

  if (pendingOrders) {
    pendingOrders.textContent =
      SupplierDemo.orders.length;
  }

  if (supplierGMV) {
    supplierGMV.textContent =
      money(
        SupplierDemo.orders.reduce(
          (s, o) => s + Number(o.total || 0),
          0
        )
      );
  }

  if (offerRows) {

    offerRows.innerHTML =
      SupplierDemo.offers.length

        ? SupplierDemo.offers.map(o => `
          <tr>

            <td>${o.name}</td>

            <td>${o.qty} كجم</td>

            <td>${money(o.retail)}</td>

            <td>${money(o.wholesale)}</td>

            <td>${o.auction ? "نعم" : "لا"}</td>

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
                ${o.status === "active" ? "إيقاف" : "تفعيل"}
              </button>
            </td>

          </tr>
        `).join("")

        : `
          <tr>
            <td colspan="7">
              لا توجد عروض حالياً
            </td>
          </tr>
        `;
  }

  if (supplierOrderRows) {

    supplierOrderRows.innerHTML =
      SupplierDemo.orders.length

        ? SupplierDemo.orders.map(o => `
          <tr>
            <td>${o.no}</td>
            <td>${o.item}</td>
            <td>${money(o.total)}</td>
            <td>${o.status}</td>
          </tr>
        `).join("")

        : `
          <tr>
            <td colspan="4">
              لا توجد طلبات حالياً
            </td>
          </tr>
        `;
  }
}


/* =========================================
   تفعيل قنوات البيع
========================================= */

function toggleMode(el, mode) {

  if (offerModes.has(mode)) {

    offerModes.delete(mode);
    el.classList.remove("active");

  } else {

    offerModes.add(mode);
    el.classList.add("active");

  }
}


/* =========================================
   نشر عرض حقيقي في Supabase
========================================= */

async function addOffer() {

  try {

    if (!window.Bahrna || !Bahrna.client) {
      return alert("قاعدة البيانات غير متصلة");
    }

    const name =
      document.getElementById("fishName").value.trim();

    const qty =
      Number(document.getElementById("qtyKg").value);

    const retail =
      Number(document.getElementById("retailPrice").value);

    const wholesale =
      Number(
        document.getElementById("wholesalePrice").value || 0
      );

    const arrived =
      document.getElementById("arrivedAt").value;

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
      await getCurrentSupplier();

    let arrivedAt = null;

    if (arrived) {

      const now = new Date();

      const parts = arrived.split(":");

      const hours =
        Number(parts[0] || 0);

      const minutes =
        Number(parts[1] || 0);

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

      supplier_id: supplier.id,

      name_ar: name,

      category: "سمك",

      origin:
        supplier.emirate || "الإمارات",

      price_per_kg:
        retail,

      wholesale_price_per_kg:
        offerModes.has("wholesale")
          ? wholesale
          : null,

      stock_kg:
        qty,

      arrived_at:
        arrivedAt,

      active:
        true
    };

    const sb = Bahrna.client;

    const { data, error } = await sb
      .from("products")
      .insert(payload)
      .select(`
        id,
        supplier_id,
        name_ar,
        origin,
        price_per_kg,
        wholesale_price_per_kg,
        stock_kg,
        arrived_at,
        active
      `)
      .single();

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


/* =========================================
   إيقاف / تفعيل العرض
========================================= */

async function toggleOffer(id) {

  /*
    لم نفعّل UPDATE Policy للمنتجات بعد.
    لذلك نمنع تعديل قاعدة البيانات مؤقتاً
    حتى نضيف صلاحية المورد لتعديل عروضه فقط.
  */

  alert(
    "سيتم تفعيل خاصية إيقاف وتفعيل العرض في الخطوة التالية."
  );
}


/* =========================================
   تشغيل لوحة المورد
========================================= */

document.addEventListener(
  "DOMContentLoaded",
  async () => {

    try {

      await loadSupplierOffers();

      await loadSupplierOrders();

      renderSupplier();

    } catch (e) {

      console.error(
        "خطأ تشغيل لوحة المورد:",
        e
      );

      renderSupplier();

    }

  }
);

const SupplierDemo = {
  offers: (window.Bahrna && Bahrna.getDemoSupplierOffers)
    ? Bahrna.getDemoSupplierOffers()
    : [],
  orders: []
};

let offerModes = new Set(["retail"]);

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

/* ==============================
   قراءة الطلبات الحقيقية من Supabase
================================ */

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

/* ==============================
   عرض لوحة المورد
================================ */

function renderSupplier() {

  document.getElementById("activeOffers").textContent =
    SupplierDemo.offers.filter(x => x.status === "active").length;

  document.getElementById("stockKg").textContent =
    SupplierDemo.offers.reduce((s, x) => s + Number(x.qty || 0), 0)
    + " كجم";

  document.getElementById("pendingOrders").textContent =
    SupplierDemo.orders.length;

  document.getElementById("supplierGMV").textContent =
    money(
      SupplierDemo.orders.reduce(
        (s, o) => s + Number(o.total || 0),
        0
      )
    );

  document.getElementById("offerRows").innerHTML =
    SupplierDemo.offers.map(o => `
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
            onclick="toggleOffer(${o.id})">
            ${o.status === "active" ? "إيقاف" : "تفعيل"}
          </button>
        </td>
      </tr>
    `).join("");

  document.getElementById("supplierOrderRows").innerHTML =
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
            <td colspan="4">لا توجد طلبات حالياً</td>
          </tr>
        `;
}

function persist() {
  if (
    window.Bahrna &&
    Bahrna.saveDemoSupplierOffers
  ) {
    Bahrna.saveDemoSupplierOffers(
      SupplierDemo.offers
    );
  }
}

function toggleOffer(id) {

  const o = SupplierDemo.offers.find(
    x => x.id === id
  );

  if (!o) return;

  o.status =
    o.status === "active"
      ? "paused"
      : "active";

  persist();
  renderSupplier();
}

function toggleMode(el, mode) {

  if (offerModes.has(mode)) {
    offerModes.delete(mode);
    el.classList.remove("active");
  } else {
    offerModes.add(mode);
    el.classList.add("active");
  }
}

function addOffer() {

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
    isNaN(qty) ||
    isNaN(retail)
  ) {
    return alert(
      "أكمل اسم المنتج والكمية وسعر التجزئة"
    );
  }

  SupplierDemo.offers.push({
    id: Date.now(),
    name,
    qty,
    retail,
    wholesale,
    auction: offerModes.has("auction"),
    status: "active",
    arrived,
    supplier: "مورد تجريبي",
    origin: "الإمارات"
  });

  persist();
  renderSupplier();
  showSupplierPanel("offersPanel");
}

/* ==============================
   تشغيل لوحة المورد
================================ */

document.addEventListener(
  "DOMContentLoaded",
  async () => {

    await loadSupplierOrders();

    renderSupplier();

  }
);

function money(n) {

  return "AED " +
    Number(n || 0).toFixed(2);
}


/* =========================================
   ترجمة حالة الطلب
========================================= */

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


/* =========================================
   تنسيق التاريخ
========================================= */

function formatOrderDate(value) {

  if (!value) return "—";


  try {

    return new Date(value)
      .toLocaleString(
        "ar-AE",
        {
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit"
        }
      );

  } catch (e) {

    return value;
  }
}


/* =========================================
   فتح صفحة التتبع
========================================= */

function trackOrder(order) {

  const saved = {

    orderNo:
      order.order_no,

    status:
      order.tracking_status ||
      order.status ||
      "confirmed",

    isReal:
      true,

    createdAt:
      order.created_at,

    total:
      Number(order.total || 0),

    address:
      order.delivery_address || {},

    slot:
      order.preparation_summary?.slot || ""

  };


  localStorage.setItem(
    "bahrna_last_order",
    JSON.stringify(saved)
  );


  location.href =
    "tracking.html";
}


/* =========================================
   تحميل طلبات العميل
========================================= */

async function loadMyOrders() {

  const loading =
    document.getElementById(
      "ordersLoading"
    );

  const noOrders =
    document.getElementById(
      "noOrders"
    );

  const wrap =
    document.getElementById(
      "ordersWrap"
    );

  const rows =
    document.getElementById(
      "myOrderRows"
    );


  try {


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
        "my-orders.html"
      );


      alert(
        "يرجى تسجيل الدخول لعرض طلباتك"
      );


      location.href =
        "login.html";

      return;
    }


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
        user_id,
        status,
        tracking_status,
        total,
        created_at,
        delivery_address,
        preparation_summary,
        order_items (
          product_name,
          qty_kg
        )
      `)

      .eq(
        "user_id",
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


    const orders =
      data || [];


    if (loading) {

      loading.style.display =
        "none";
    }


    if (!orders.length) {

      if (noOrders) {

        noOrders.style.display =
          "block";
      }

      return;
    }


    if (wrap) {

      wrap.style.display =
        "block";
    }


    rows.innerHTML =
      orders.map(order => {


        const items =
          order.order_items || [];


        const itemsText =
          items.length

            ? items.map(item =>

                `${item.product_name || "منتج"} ${Number(item.qty_kg || 0)} كجم`

              ).join("، ")

            : "—";


        const currentStatus =

          order.tracking_status ||

          order.status ||

          "pending";


        const encodedOrder =
          encodeURIComponent(
            JSON.stringify(order)
          );


        return `

          <tr>

            <td>

              <strong>
                ${order.order_no}
              </strong>

            </td>


            <td>
              ${itemsText}
            </td>


            <td>
              ${formatOrderDate(order.created_at)}
            </td>


            <td>

              <strong>
                ${money(order.total)}
              </strong>

            </td>


            <td>

              <span class="status ok">

                ${orderStatusLabel(currentStatus)}

              </span>

            </td>


            <td>

              <button
                class="btn btn-primary small"
                onclick="trackOrder(
                  JSON.parse(
                    decodeURIComponent(
                      '${encodedOrder}'
                    )
                  )
                )"
              >

                تتبع الطلب

              </button>

            </td>

          </tr>

        `;

      }).join("");


  } catch (e) {


    console.error(
      "خطأ تحميل طلبات العميل:",
      e
    );


    if (loading) {

      loading.textContent =
        "تعذر تحميل الطلبات: " +
        (e.message || e);
    }
  }
}


/* =========================================
   تشغيل الصفحة
========================================= */

document.addEventListener(
  "DOMContentLoaded",
  loadMyOrders
);

// Ortak Defter: küçük kolaylıklar. Sayfalar JavaScript olmadan da çalışır.
(function () {
  "use strict";

  // --- Tutar: yazarken nasıl kaydedileceğini göster (sunucudaki kuralın aynısı)
  var UNIT = /^₺|(₺|tl|try)$/i;
  var GROUPED = /^[1-9][0-9]{0,2}(\.[0-9]{3})+$/;

  function parseAmount(text) {
    var s = String(text || "").replace(/\s/g, "").slice(0, 40).replace(UNIT, "").replace(UNIT, "");
    if (!s || !/^[0-9.,]+$/.test(s)) return null;
    var whole, frac = "";
    if (s.indexOf(",") !== -1) {
      var p = s.split(",");
      if (p.length > 2 || p[1].indexOf(".") !== -1) return null;
      whole = p[0];
      frac = p[1];
      if (whole.indexOf(".") !== -1) {
        if (!GROUPED.test(whole)) return null;
        whole = whole.replace(/\./g, "");
      }
    } else if (s.indexOf(".") !== -1) {
      if (GROUPED.test(s)) {
        whole = s.replace(/\./g, "");
      } else if (s.split(".").length === 2) {
        whole = s.split(".")[0];
        frac = s.split(".")[1];
      } else {
        return null;
      }
    } else {
      whole = s;
    }
    if (frac.length > 2 || (!whole && !frac) || whole.length > 12) return null;
    var kurus = parseInt(whole || "0", 10) * 100 + parseInt((frac + "00").slice(0, 2), 10);
    return kurus > 0 && kurus <= 100000000000 ? kurus : null;
  }

  function formatTry(kurus) {
    var lira = Math.floor(kurus / 100), k = kurus % 100;
    return String(lira).replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + (k < 10 ? "0" + k : k) + " ₺";
  }

  document.querySelectorAll("[data-amount]").forEach(function (input) {
    var echo = input.closest(".field").querySelector("[data-amount-echo]");
    if (!echo) return;
    function update() {
      var raw = input.value.trim();
      if (!raw) { echo.textContent = ""; return; }
      var k = parseAmount(raw);
      echo.textContent = k === null ? "Tutar anlaşılamadı. Örnek: 1.250,50" : formatTry(k) + " olarak kaydedilecek";
    }
    input.addEventListener("input", update);
    update();
  });

  // --- Aynı formun iki kez gönderilmesini önle (çift dokunma, yavaş fiş yüklemesi)
  document.querySelectorAll('form[method="post"]').forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (form.dataset.sent === "1") { e.preventDefault(); return; }
      form.dataset.sent = "1";
      form.setAttribute("aria-busy", "true");
    });
  });
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-sent]").forEach(function (form) {
      delete form.dataset.sent;
      form.removeAttribute("aria-busy");
    });
  });

  // --- Tarih kısayolları
  document.querySelectorAll("[data-set-date]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.closest(".date-row").querySelector('input[type="date"]');
      if (input) input.value = btn.getAttribute("data-set-date");
    });
  });

  // --- Seçilen fişlerin önizlemesi
  document.querySelectorAll("input[type=file][data-previews]").forEach(function (input) {
    var box = document.getElementById(input.getAttribute("data-previews"));
    if (!box) return;
    input.addEventListener("change", function () {
      box.querySelectorAll("img").forEach(function (img) { URL.revokeObjectURL(img.src); });
      box.textContent = "";
      Array.prototype.forEach.call(input.files, function (file) {
        if (file.type.indexOf("image/") === 0) {
          var img = document.createElement("img");
          img.alt = file.name;
          img.src = URL.createObjectURL(file);
          box.appendChild(img);
        } else {
          var tile = document.createElement("span");
          tile.className = "pdf-tile";
          tile.textContent = "PDF";
          tile.title = file.name;
          box.appendChild(tile);
        }
      });
    });
  });

  // --- Fiş büyütme
  var lightbox = document.getElementById("lightbox");
  if (lightbox && typeof lightbox.showModal === "function") {
    var big = lightbox.querySelector("img");
    var link = lightbox.querySelector("a");
    document.querySelectorAll("[data-lightbox]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var url = btn.getAttribute("data-lightbox");
        big.src = url;
        link.href = url;
        lightbox.showModal();
      });
    });
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox) lightbox.close();
    });
  } else {
    document.querySelectorAll("[data-lightbox]").forEach(function (btn) {
      btn.addEventListener("click", function () { window.open(btn.getAttribute("data-lightbox"), "_blank"); });
    });
  }

  // --- Grafik: sütunun üzerine gelince ayın değerleri
  document.querySelectorAll("[data-chart]").forEach(function (box) {
    var svg = box.querySelector("svg");
    var tip = box.querySelector(".tip");
    if (!svg || !tip) return;

    function row(cls, label, value, swatch) {
      var div = document.createElement("div");
      if (cls) div.className = cls;
      var left = document.createElement("span");
      if (swatch) {
        var i = document.createElement("i");
        i.style.background = swatch;
        left.appendChild(i);
      }
      left.appendChild(document.createTextNode(label));
      var right = document.createElement("span");
      right.textContent = value;
      div.appendChild(left);
      div.appendChild(right);
      return div;
    }

    function show(col) {
      var css = getComputedStyle(document.documentElement);
      tip.textContent = "";
      var title = document.createElement("b");
      title.textContent = col.getAttribute("data-label");
      tip.appendChild(title);
      tip.appendChild(row("", "Gelir", col.getAttribute("data-gelir"), css.getPropertyValue("--gelir")));
      tip.appendChild(row("", "Gider", col.getAttribute("data-gider"), css.getPropertyValue("--gider")));
      tip.appendChild(row("t-net", "Net", col.getAttribute("data-net")));
      tip.hidden = false;
      var scale = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
      var x = parseFloat(col.getAttribute("data-cx")) * scale;
      var w = tip.offsetWidth;
      var left = Math.max(0, Math.min(x - w / 2, box.clientWidth - w));
      tip.style.left = left + "px";
      tip.style.top = "0px";
    }
    function hide() { tip.hidden = true; }

    svg.querySelectorAll(".col").forEach(function (col) {
      col.addEventListener("mouseenter", function () { show(col); });
      col.addEventListener("mouseleave", hide);
      col.addEventListener("focus", function () { show(col); });
      col.addEventListener("blur", hide);
      col.addEventListener("click", function () { show(col); });
    });
  });
})();

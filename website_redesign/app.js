/* Banxum static export — shared behaviors + earnings-calendar renderer.
   No framework. Figures are computed from the same payment data the platform uses. */
(function () {
  "use strict";

  /* ---- account menu ---- */
  document.querySelectorAll("[data-menu]").forEach(function (btn) {
    var menu = document.getElementById(btn.getAttribute("data-menu"));
    if (!menu) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
    });
    document.addEventListener("click", function (e) {
      if (!menu.hidden && !menu.contains(e.target)) menu.hidden = true;
    });
  });

  /* ---- generic expand/collapse: button[data-toggle="id"] ----
     Optional attrs: data-open-label / data-close-label (swap first [data-label] text),
     [data-sign] child gets +/−, wrapper gets .open class. */
  document.querySelectorAll("[data-toggle]").forEach(function (btn) {
    var body = document.getElementById(btn.getAttribute("data-toggle"));
    if (!body) return;
    btn.addEventListener("click", function () {
      var open = body.hidden;
      body.hidden = !open;
      btn.classList.toggle("open", open);
      var sign = btn.querySelector("[data-sign]");
      if (sign) sign.textContent = open ? "−" : "+";
      var label = btn.querySelector("[data-label]");
      if (label) {
        var ol = btn.getAttribute("data-open-label"), cl = btn.getAttribute("data-close-label");
        if (ol && cl) label.textContent = open ? cl : ol;
      }
    });
  });

  /* ---- segmented controls: [data-seg] > button[data-seg-value] switches
     [data-seg-panel][data-seg-group] panels; also [data-seg-class-target] gets value as class ---- */
  function activateSeg(seg, value) {
    seg.querySelectorAll("[data-seg-value]").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-seg-value") === value);
    });
    var group = seg.getAttribute("data-seg");
    document.querySelectorAll('[data-seg-panel][data-seg-group="' + group + '"]').forEach(function (p) {
      p.hidden = p.getAttribute("data-seg-panel") !== value;
    });
    var targetSel = seg.getAttribute("data-seg-class-target");
    if (targetSel) {
      var t = document.querySelector(targetSel);
      if (t) {
        seg.querySelectorAll("[data-seg-value]").forEach(function (b) { t.classList.remove(b.getAttribute("data-seg-value")); });
        t.classList.add(value);
      }
    }
  }
  document.querySelectorAll("[data-seg]").forEach(function (seg) {
    seg.querySelectorAll("[data-seg-value]").forEach(function (b) {
      b.addEventListener("click", function () { activateSeg(seg, b.getAttribute("data-seg-value")); });
    });
  });
  /* buttons elsewhere can jump a seg to a value */
  document.querySelectorAll("[data-seg-set]").forEach(function (b) {
    b.addEventListener("click", function () {
      var parts = b.getAttribute("data-seg-set").split(":"); // group:value
      var seg = document.querySelector('[data-seg="' + parts[0] + '"]');
      if (seg) activateSeg(seg, parts[1]);
    });
  });

  /* ---- FAQ accordion (one open at a time) ---- */
  document.querySelectorAll(".faq-q").forEach(function (q) {
    q.addEventListener("click", function () {
      var a = q.nextElementSibling;
      if (!a || !a.classList.contains("faq-a")) return;
      var wasOpen = !a.hidden;
      document.querySelectorAll(".faq-a").forEach(function (x) { x.hidden = true; });
      document.querySelectorAll(".faq-q .sign").forEach(function (s) { s.textContent = "+"; });
      a.hidden = wasOpen;
      var s = q.querySelector(".sign");
      if (s) s.textContent = wasOpen ? "+" : "−";
    });
  });

  /* ---- show all / show fewer rows: button[data-more="group"] toggles [data-more-row="group"] ---- */
  document.querySelectorAll("[data-more]").forEach(function (btn) {
    var group = btn.getAttribute("data-more");
    var rows = document.querySelectorAll('[data-more-row="' + group + '"]');
    var open = false;
    btn.addEventListener("click", function () {
      open = !open;
      rows.forEach(function (r) { r.hidden = !open; });
      var alt = btn.getAttribute("data-more-alt");
      if (alt) { var cur = btn.textContent; btn.textContent = alt; btn.setAttribute("data-more-alt", cur); }
      var line = document.querySelector('[data-more-line="' + group + '"]');
      if (line) {
        var altLine = line.getAttribute("data-more-alt");
        if (altLine) { var curLine = line.textContent; line.textContent = altLine; line.setAttribute("data-more-alt", curLine); }
      }
    });
  });

  /* =====================================================================
     Earnings calendar — ported from the platform prototype.
     Every figure is derived from the loan schedule below (balance, monthly
     payment, contract rate), exactly as the live product computes it.
     ===================================================================== */
  var HOST = document.getElementById("bxCal");
  if (!HOST) return;

  var COLLATERAL = {
    aurelia: "First-rank mortgage on the bakery in Ploiești, together with a movable mortgage over its collection accounts.",
    nord: "Movable mortgage on 28 tractor units at the Bacău yard, plus a surety from both shareholders.",
    verde: "First-rank mortgage on 9 unsold townhouses in Otopeni and the land beneath them.",
    solaria: "Second-rank mortgage on the head office in Craiova, and a movable mortgage over the feed-in tariff receivables from both arrays.",
    cristal: "Movable mortgage on 2 annealing lines at the Turda works.",
    graul: "First-rank mortgage on the mill at Slobozia, and a movable mortgage over its collection accounts.",
    munti: "Movable mortgage on the sawmill and the drying kilns.",
    farma: "Movable mortgage on 11 refrigerated vans, and an assignment of the pharmacy-chain receivables.",
    fanul: "Fidejusiune — a personal surety from the owner. No asset of the company is pledged.",
    podul: "First-rank mortgage on a completed office floor in Cluj, plus a surety from the owner.",
    apa: "Movable mortgage on the bottling and filtration equipment.",
    termo: "Movable mortgage on the installation plant and 4 service vans, and over two framework-contract receivables.",
    zavoi: "First-rank mortgage on 52 hectares of arable land near Buzău.",
    lumina: "Fidejusiune — a personal surety from the owner. No asset of the company is pledged.",
    ceramica: "Movable mortgage on 3 tunnel kilns.",
    bastion: "First-rank mortgage on a warehouse near Arad and its access plot."
  };
  /* key, payday, name, monthly payment, first-month interest, first-month principal,
     outstanding balance, payments made, term, annual rate %, valuation, borrowed, penalty %/day, late? */
  var RAW = [
    ["aurelia", 2, "Aurelia Panificație SRL", 1904.40, 352.00, 1552.40, 37715.80, 14, 36, 11.2, 1640000, 984000, 0.10, false],
    ["nord", 4, "Nord Trans Cargo SRL", 1097.80, 251.20, 846.60, 25978.20, 21, 48, 11.6, 2780000, 1668000, 0.10, false],
    ["verde", 6, "Verde Imobiliare SRL", 1740.00, 254.20, 1485.80, 25626.40, 8, 24, 11.9, 1920000, 1152000, 0.12, false],
    ["cristal", 9, "Cristal Sticlă SA", 1231.00, 202.60, 1028.40, 21305.80, 11, 30, 11.4, 880000, 396000, 0.15, false],
    ["graul", 11, "Grâul de Aur SA", 1346.20, 134.80, 1211.40, 15264.40, 12, 24, 10.6, 1340000, 804000, 0.10, false],
    ["munti", 13, "Munții Lemn SRL", 1069.80, 74.00, 995.80, 8222.20, 16, 24, 10.8, 720000, 360000, 0.15, false],
    ["farma", 14, "Farmavia Distribuție SRL", 721.20, 158.60, 562.60, 17163.60, 9, 36, 11.1, 640000, 352000, 0.12, false],
    ["podul", 16, "Podul Nou Construcții SRL", 1159.60, 121.20, 1038.40, 12015.80, 7, 18, 12.1, 1180000, 731600, 0.12, false],
    ["apa", 18, "Apa Limpede SRL", 555.80, 79.20, 476.60, 8718.00, 19, 36, 10.9, 495000, 222750, 0.15, false],
    ["termo", 20, "Termo Instal SRL", 852.40, 101.80, 750.60, 10355.20, 5, 18, 10.9, 380000, 190000, 0.15, false],
    ["zavoi", 22, "Zăvoi Agro SA", 471.20, 64.40, 406.80, 7418.00, 13, 30, 10.9, 2340000, 1404000, 0.10, false],
    ["lumina", 23, "Lumina Electric SRL", 487.20, 77.00, 410.20, 8018.80, 6, 24, 10.9, 0, 0, 0.20, true],
    ["bastion", 25, "Bastion Depozite SRL", 297.60, 54.80, 242.80, 5627.40, 15, 36, 10.9, 1760000, 1073600, 0.10, false],
    ["ceramica", 27, "Ceramica Veche SRL", 555.40, 33.40, 522.00, 3753.40, 11, 18, 10.7, 410000, 184500, 0.15, false]
  ];
  var ANNUAL = {
    7: { day: 18, name: "Solaria Verde Energie SA", amt: 4182.00, int: 4182.00, pri: 0, bal: 34000.00, n: 1, term: 3, security: COLLATERAL.solaria, valuation: 690000, borrowed: 448500, penRate: "0.12%", annual: true },
    8: { day: 9, name: "Fânul Alb SRL", amt: 2180.00, int: 2180.00, pri: 0, bal: 20000.00, n: 1, term: 2, security: COLLATERAL.fanul, valuation: 0, borrowed: 0, penRate: "0.2%", annual: true }
  };
  var MN = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"];
  var MFULL = ["August", "September", "October", "November", "December", "January", "February", "March", "April", "May", "June", "July"];
  var MYEAR = [2026, 2026, 2026, 2026, 2026, 2027, 2027, 2027, 2027, 2027, 2027, 2027];
  var MOFF = [5, 1, 3, 6, 1, 4, 0, 0, 3, 5, 1, 3];
  var MLEN = [31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30, 31];

  var sched = RAW.map(function (r) {
    return { key: r[0], day: r[1], name: r[2], pay: r[3], fInt: r[4], fPri: r[5], bal: r[6],
      made: r[7], term: r[8], i: r[9] / 1200, val: r[10], bor: r[11], pen: r[12], late: r[13] };
  });
  var MONTHS = MN.map(function (mm, m) {
    var rows = [];
    sched.forEach(function (s) {
      var n = s.made + 1 + m;
      if (n > s.term) return;
      var int_, pri;
      if (m === 0) { int_ = s.fInt; pri = s.fPri; }
      else { int_ = s.bal * s.i; pri = Math.min(s.pay - int_, s.bal); s.bal -= pri; }
      rows.push({ day: s.day, name: s.name, amt: s.pay, int: int_, pri: pri, bal: s.bal, n: n, term: s.term,
        late: s.late, security: COLLATERAL[s.key], valuation: s.val, borrowed: s.bor, pen: s.pen });
    });
    if (ANNUAL[m]) rows.push(ANNUAL[m]);
    rows.sort(function (a, b) { return a.day - b.day; });
    var byDay = {};
    rows.forEach(function (r) { (byDay[r.day] = byDay[r.day] || []).push(r); });
    var max = 0;
    Object.keys(byDay).forEach(function (d) {
      var t = byDay[d].reduce(function (a, b) { return a + b.amt; }, 0);
      if (t > max) max = t;
    });
    return { mm: mm, full: MFULL[m], year: MYEAR[m], rows: rows, byDay: byDay, off: MOFF[m], len: MLEN[m],
      total: rows.reduce(function (a, b) { return a + b.amt; }, 0), max: max };
  });

  var cur = 0, sel = null;
  var e2 = function (n) { return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
  var eur0 = function (n) { return "€ " + n.toLocaleString("en-US", { maximumFractionDigits: 0 }); };
  var esc = function (s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); };

  function render() {
    var M = MONTHS[cur];
    var html = '<div class="cal-strip">';
    MONTHS.forEach(function (x, i) {
      html += '<button type="button" data-cal-month="' + i + '" class="' + (i === cur ? "on" : "") + '"><span>' + x.mm.toUpperCase() + '</span><span class="yr">' + (x.year === 2026 ? "" : "'27") + '</span></button>';
    });
    html += '</div><div class="cal-box"><div class="cal-head">';
    html += '<button type="button" class="cal-nav" data-cal-prev ' + (cur === 0 ? "disabled" : "") + '>&#8249;</button>';
    html += '<span class="cal-title">' + M.full + " " + M.year + '</span>';
    html += '<button type="button" class="cal-nav" data-cal-next ' + (cur === 11 ? "disabled" : "") + '>&#8250;</button>';
    html += '<span class="cal-meta">' + M.rows.length + ' payments · € ' + e2(M.total) + '</span><span class="grow"></span>';
    html += '<span class="cal-legend"><span style="width:9px;height:9px;border-radius:2px;background:#1E6A4B"></span>payday</span>';
    html += '<span class="cal-legend"><span style="width:9px;height:2px;background:#151719"></span>final payment</span>';
    html += '<span class="cal-legend"><span style="width:9px;height:9px;border-radius:2px;background:#C4312C"></span>late</span>';
    html += '</div><div class="cal-dows"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div><div class="cal-grid">';
    for (var k = 0; k < 42; k++) {
      var d = k - M.off + 1;
      var inM = d >= 1 && d <= M.len;
      var g = inM ? M.byDay[d] : null;
      if (!inM) { html += '<div class="cal-plain"></div>'; continue; }
      if (!g) { html += '<div class="cal-plain">' + d + '</div>'; continue; }
      var sum = g.reduce(function (a, b) { return a + b.amt; }, 0);
      var isLate = cur === 0 && g.some(function (r) { return r.late; });
      var final_ = g.some(function (r) { return r.n === r.term; });
      var cls = "cal-cell" + (sel === d ? " sel" : "") + (isLate ? " late" : "") + (final_ ? " final" : "");
      var who = g.length > 1 ? g.length + " payments" : g[0].name.replace(/ (SRL|SA)$/, "");
      html += '<button type="button" class="' + cls + '" data-cal-day="' + d + '">' +
        '<span class="d">' + d + '</span><span class="amt">' + e2(sum) + '</span>' +
        '<span class="who">' + esc(who) + '</span>' +
        '<span class="bar"><span style="width:' + Math.round(sum / M.max * 100) + '%"></span></span>' +
        '<span class="endline"></span></button>';
    }
    html += '</div>';
    html += sel != null ? detailHtml(M) : ('<div class="cal-footnote"><span style="font-size:13.5px;color:#626B70">Bars are scaled within the month, so the longest one is that month\u2019s largest payment.</span><span class="grow"></span><span style="font-size:13.5px;font-weight:600;margin-right:16px">' + M.full + ' in total</span><span style="font-size:13.5px;color:#626B70;margin-right:6px">€</span><span class="num" style="font-size:20px;font-weight:600;letter-spacing:-0.03em">' + e2(M.total) + '</span></div>');
    html += '</div>';
    HOST.innerHTML = html;

    HOST.querySelectorAll("[data-cal-month]").forEach(function (b) {
      b.addEventListener("click", function () { cur = +b.getAttribute("data-cal-month"); sel = null; render(); });
    });
    var prev = HOST.querySelector("[data-cal-prev]"), next = HOST.querySelector("[data-cal-next]");
    if (prev) prev.addEventListener("click", function () { if (cur > 0) { cur--; sel = null; render(); } });
    if (next) next.addEventListener("click", function () { if (cur < 11) { cur++; sel = null; render(); } });
    HOST.querySelectorAll("[data-cal-day]").forEach(function (b) {
      b.addEventListener("click", function () {
        var d = +b.getAttribute("data-cal-day");
        sel = sel === d ? null : d;
        render();
      });
    });
    var x = HOST.querySelector("[data-cal-close]");
    if (x) x.addEventListener("click", function () { sel = null; render(); });
  }

  function kvRow(k, v, cls) {
    return '<div style="display:flex;align-items:baseline;padding:8px 0;border-top:1px solid #E4E1D8">' +
      '<span style="white-space:nowrap;color:' + (cls === "green" ? "#1E6A4B" : "#626B70") + '">' + k + '</span>' +
      '<span class="leader"></span>' +
      '<span class="num" style="font-weight:600;color:' + (cls === "green" ? "#1E6A4B" : "#151719") + '">' + v + '</span></div>';
  }
  function detailHtml(M) {
    var g = M.byDay[sel];
    if (!g) return "";
    var dateLine = sel + " " + M.full + " " + M.year;
    if (g.length > 1) {
      var tot = g.reduce(function (a, b) { return a + b.amt; }, 0);
      var word = ["", "", "Two", "Three", "Four"][g.length];
      var cols = g.map(function (r) {
        var lateNow = r.late && cur === 0;
        return '<div><div style="display:flex;align-items:baseline;margin-bottom:12px"><span style="font-size:16px;font-weight:600;letter-spacing:-0.02em;color:' + (lateNow ? "#C4312C" : "#151719") + '">' + esc(r.name) + '</span><span class="grow"></span><span class="num" style="font-size:16px;font-weight:600">€ ' + e2(r.amt) + '</span></div>' +
          '<div style="display:flex;flex-direction:column;font-size:13px;margin-bottom:12px">' +
          kvRow("Interest — what you earn", e2(r.int), "green") +
          kvRow("Your money coming back", e2(r.pri)) +
          kvRow("Payments made", r.n + " of " + r.term) +
          '</div><div style="font-size:13px;line-height:1.5;color:#151719;text-wrap:pretty">' + esc(r.security) + '</div></div>';
      }).join("");
      return '<div class="cal-detail"><div style="display:flex;align-items:flex-start;gap:20px;margin-bottom:20px">' +
        '<div style="flex:1"><div class="microlabel" style="margin-bottom:9px">' + dateLine + '</div>' +
        '<div style="font-size:22px;font-weight:600;letter-spacing:-0.025em">' + word + ' companies pay you on this day</div></div>' +
        '<div style="display:flex;align-items:baseline;flex:none"><span style="font-size:15px;font-weight:500;color:#626B70;margin-right:7px">€</span><span class="num" style="font-size:34px;font-weight:600;letter-spacing:-0.05em;line-height:.9">' + e2(tot) + '</span></div>' +
        '<button type="button" class="cal-x" data-cal-close>&times;</button></div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:36px">' + cols + '</div></div>';
    }
    var r = g[0];
    var lateNow = r.late && cur === 0;
    var whole = Math.floor(r.amt).toLocaleString("en-US");
    var cents = e2(r.amt).slice(-3);
    var penDay = r.bal * r.pen / 100;
    var ltv = r.valuation ? Math.round(r.borrowed / r.valuation * 100) : 0;
    var badge = lateNow ? '<span style="font-size:13px;color:#C4312C">9 days late · penalty € ' + e2(penDay * 9) + ' accrued</span>'
      : (r.n === r.term ? '<span style="font-size:13px;font-weight:600">final payment — this loan is repaid in full</span>' : "");
    var colBlock = '<div><div class="microlabel" style="color:#151719;margin-bottom:10px">Collateral</div>' +
      '<div style="font-size:14px;line-height:1.5;margin-bottom:12px;text-wrap:pretty">' + esc(r.security) + '</div>' +
      (r.valuation ? '<div style="display:flex;height:4px;background:#DDE3E1;border-radius:2px;overflow:hidden;margin-bottom:9px"><div style="width:' + ltv + '%;background:#151719"></div></div>' +
        '<div style="font-size:13px;color:#626B70;margin-bottom:12px;text-wrap:pretty">Valued independently at ' + eur0(r.valuation) + ' · lent against it ' + eur0(r.borrowed) + ' · ' + ltv + '% of the valuation</div>' : "") +
      '<div style="font-size:13px;line-height:1.55;color:#626B70;text-wrap:pretty">If payment stops, penalty interest of <span style="color:#151719;font-weight:600">' + (r.pen ? (r.pen.toFixed(2).replace(/0$/, "").replace(/\.$/, "")) : r.penRate || "") + '% a day</span> accrues on what is outstanding — € ' + e2(penDay) + ' a day at today\u2019s balance — and is collected ahead of principal.</div></div>';
    return '<div class="cal-detail"><div style="display:flex;align-items:flex-start;gap:20px;margin-bottom:20px">' +
      '<div style="flex:1"><div class="microlabel" style="margin-bottom:9px">' + dateLine + '</div>' +
      '<div style="display:flex;align-items:baseline;gap:14px"><span style="font-size:22px;font-weight:600;letter-spacing:-0.025em;color:' + (lateNow ? "#C4312C" : "#151719") + '">' + esc(r.name) + '</span>' + badge + '</div></div>' +
      '<div style="display:flex;align-items:baseline;flex:none"><span style="font-size:15px;font-weight:500;color:#626B70;margin-right:7px">€</span><span class="num" style="font-size:34px;font-weight:600;letter-spacing:-0.05em;line-height:.9;color:' + (lateNow ? "#C4312C" : "#151719") + '">' + whole + '</span><span class="num" style="font-size:15px;font-weight:600;color:#626B70">' + cents + '</span></div>' +
      '<button type="button" class="cal-x" data-cal-close>&times;</button></div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:40px">' +
      '<div style="display:flex;flex-direction:column;font-size:13.5px">' +
      kvRow("Interest — what you earn", e2(r.int), "green") +
      kvRow("Your money coming back", e2(r.pri)) +
      kvRow("Still outstanding", e2(r.bal)) +
      kvRow("Payments made", r.n + " of " + r.term) +
      '</div>' + colBlock + '</div></div>';
  }

  render();
})();

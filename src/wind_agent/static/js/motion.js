/**
 * 通用动效：交错入场、模块依次显现、进度条过渡。
 * 系统开启「减少动态效果」时直接落定最终态。
 */
(function () {
  "use strict";

  var reduce =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function assignStagger(selector) {
    document.querySelectorAll(selector).forEach(function (el, i) {
      el.style.setProperty("--stagger", String(i));
    });
  }

  function revealBars(root) {
    var bars = (root || document).querySelectorAll(".bar > i");
    bars.forEach(function (el) {
      var target = el.getAttribute("data-target-width");
      if (!target) return;
      if (reduce) {
        el.style.width = target;
        return;
      }
      el.style.width = "0%";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          el.style.width = target;
        });
      });
    });
  }

  function prepareBars() {
    document.querySelectorAll(".bar > i").forEach(function (el) {
      var w = el.style.width;
      if (!w) return;
      el.setAttribute("data-target-width", w);
      el.style.width = reduce ? w : "0%";
    });
  }

  /** 报告模块 / HITL：按顺序错开 delay，再随滚动显现 */
  function observeRevealables() {
    var items = document.querySelectorAll(".card.motion-reveal, .hitl.motion-reveal");
    if (!items.length) return;

    items.forEach(function (el, i) {
      el.style.setProperty("--reveal-delay", reduce ? "0ms" : i * 90 + "ms");
    });

    if (reduce || typeof IntersectionObserver === "undefined") {
      items.forEach(function (c) {
        c.classList.add("is-visible");
      });
      revealBars(document);
      return;
    }

    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          revealBars(entry.target);
          io.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.06 }
    );

    items.forEach(function (c) {
      io.observe(c);
    });
  }

  function boot() {
    assignStagger(".gate .motion-stagger");
    assignStagger(".hero .motion-stagger");

    document.querySelectorAll(".motion-enter").forEach(function (el) {
      if (reduce) el.classList.remove("motion-enter");
    });

    var gate = document.querySelector(".gate");
    if (gate) gate.classList.add("is-ready");

    prepareBars();
    observeRevealables();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

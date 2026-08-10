/**
 * 首页：方向点选 + 生成报告（含 loading 阶段动效）。
 */
(function () {
  "use strict";

  var dirInput = document.getElementById("direction");
  var form = document.getElementById("f");
  if (!dirInput || !form) return;

  // 加载过程文案：顺序播放一遍后循环，覆盖取数 / 分析 / 生成各环节
  var STAGES = [
    "正在读取岗位与技能数据…",
    "正在计算市场指标…",
    "正在分析市场动向…",
    "正在查看热门趋势…",
    "正在对比分城岗位供给…",
    "正在计算预期薪资…",
    "正在梳理核心能力要求…",
    "正在生成学习准备计划…",
    "正在调用百炼撰写结论…",
    "正在整理风向报告…",
  ];
  var stageTimer = null;

  document.querySelectorAll("#dirOpts .opt").forEach(function (el) {
    el.addEventListener("click", function () {
      document.querySelectorAll("#dirOpts .opt").forEach(function (x) {
        x.classList.remove("on");
      });
      el.classList.add("on");
      var v = el.getAttribute("data-v");
      if (v === "__open__") {
        dirInput.value = "";
        dirInput.focus();
      } else {
        dirInput.value = v;
      }
    });
  });

  function dotsHtml() {
    return '<span class="stage-dots" aria-hidden="true"><i></i><i></i><i></i></span>';
  }

  function setStatusHtml(html, className) {
    var status = document.getElementById("status");
    status.innerHTML = html;
    status.className = className || "has-text";
  }

  function startStageCycle(btn) {
    var idx = 0;
    btn.classList.add("is-loading");
    btn.disabled = true;
    var label = btn.querySelector(".btn-label");
    if (label) label.textContent = "生成中";
    setStatusHtml(STAGES[0] + dotsHtml(), "has-text");
    stageTimer = setInterval(function () {
      idx = (idx + 1) % STAGES.length;
      setStatusHtml(STAGES[idx] + dotsHtml(), "has-text");
    }, 1600);
  }

  function stopStageCycle() {
    if (stageTimer) {
      clearInterval(stageTimer);
      stageTimer = null;
    }
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var btn = document.getElementById("btn");
    var label = btn.querySelector(".btn-label");
    startStageCycle(btn);
    try {
      var body = {
        query: document.getElementById("query").value.trim(),
        direction: document.getElementById("direction").value.trim() || null,
        use_real_metrics: true,
      };
      var res = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      var data = await res.json();
      if (!res.ok) throw new Error(data.detail || "生成失败");
      stopStageCycle();
      setStatusHtml("生成完成，正在打开报告…", "has-text");
      if (label) label.textContent = "即将跳转";
      window.location.href = data.html_url;
    } catch (err) {
      stopStageCycle();
      btn.disabled = false;
      btn.classList.remove("is-loading");
      if (label) label.textContent = "生成风向报告";
      setStatusHtml((err && err.message) || "请求失败", "err has-text");
    }
  });
})();

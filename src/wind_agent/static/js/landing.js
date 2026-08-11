/**
 * 首页：推荐方向点选同步提问 + 生成报告（含 loading 阶段动效）。
 */
(function () {
  "use strict";

  var dirInput = document.getElementById("direction");
  var queryInput = document.getElementById("query");
  var form = document.getElementById("f");
  if (!dirInput || !form || !queryInput) return;

  // 推荐方向 → 预设提问（与 chip 的 data-query 双保险）
  var PRESET_QUERIES = {
    数据分析:
      "我现在是大二统计专业学生，以后想找数据分析岗位工作，我应该如何准备。",
    产品经理:
      "我是大三商科学生，想转产品经理方向，需要补哪些能力和项目经验？",
    后端开发:
      "我是计算机大二学生，目标后端开发岗，该如何规划实习与技术栈学习？",
    算法:
      "我是大二学生，以后想做算法工程师（含 Agent/大模型方向），应该如何准备？",
  };

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
  var submitting = false;

  function setQueryText(text) {
    var next = text || "";
    // 先清空再写入，避免部分浏览器/输入法下 value 已变但可视区不刷新
    queryInput.blur();
    queryInput.value = "";
    queryInput.defaultValue = "";
    queryInput.value = next;
    queryInput.defaultValue = next;
    try {
      queryInput.dispatchEvent(new Event("input", { bubbles: true }));
      queryInput.dispatchEvent(new Event("change", { bubbles: true }));
    } catch (e) {
      /* ignore */
    }
    queryInput.classList.remove("query-flash");
    // 强制一次 reflow，确保闪动动画可重触发
    void queryInput.offsetWidth;
    queryInput.classList.add("query-flash");
    // 把光标放到文首，方便用户立刻看到全文已替换
    try {
      queryInput.focus();
      queryInput.setSelectionRange(0, 0);
      queryInput.scrollTop = 0;
    } catch (e2) {
      /* ignore */
    }
  }

  function applyRecommendedDirection(v, presetFromChip) {
    if (!v) return;
    dirInput.value = v;
    var preset = (presetFromChip || "").trim() || PRESET_QUERIES[v] || "";
    if (preset) {
      setQueryText(preset);
    }
  }

  document.querySelectorAll("#dirOpts .opt").forEach(function (el) {
    el.addEventListener("click", function () {
      document.querySelectorAll("#dirOpts .opt").forEach(function (x) {
        x.classList.remove("on");
      });
      el.classList.add("on");
      applyRecommendedDirection(
        el.getAttribute("data-v"),
        el.getAttribute("data-query")
      );
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

  function triggerSubmit() {
    if (submitting) return;
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    }
  }

  // 提问框：回车提交；Shift+Enter 换行；中文输入法组合中不拦截
  queryInput.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    if (e.shiftKey) return;
    if (e.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    triggerSubmit();
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (submitting) return;
    submitting = true;
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
      submitting = false;
      stopStageCycle();
      btn.disabled = false;
      btn.classList.remove("is-loading");
      if (label) label.textContent = "生成风向报告";
      setStatusHtml((err && err.message) || "请求失败", "err has-text");
    }
  });
})();

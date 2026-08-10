/**
 * 报告页人在回路：快捷动作 + 追问重算（含忙碌 / 错误反馈动效）。
 * 配置来自 #report-bootstrap（JSON）。
 */
(function () {
  "use strict";

  var bootEl = document.getElementById("report-bootstrap");
  var status = document.getElementById("hitlStatus");
  var input = document.getElementById("hitlFollowup");
  var hitl = document.getElementById("hitl");
  if (!bootEl || !status || !input || !hitl) return;

  var cfg = {};
  try {
    cfg = JSON.parse(bootEl.textContent || "{}");
  } catch (_) {
    cfg = {};
  }

  var reportId = cfg.report_id || "";
  var direction = cfg.direction || "";
  var cities = cfg.cities || [];
  var apiBase =
    location.protocol === "http:" || location.protocol === "https:"
      ? location.origin
      : "";
  var busy = false;

  // 状态行内嵌 spinner 节点
  if (!status.querySelector(".hitl-spinner")) {
    status.innerHTML =
      '<span class="hitl-spinner" aria-hidden="true"></span><span class="hitl-msg"></span>';
  }
  var msgEl = status.querySelector(".hitl-msg") || status;

  function setStatus(msg, opts) {
    opts = opts || {};
    msgEl.textContent = msg || "";
    var cls = "hitl-status";
    if (msg) cls += " has-text";
    if (opts.err) cls += " err";
    if (opts.loading) cls += " is-loading";
    status.className = cls;
  }

  function showErr(msg) {
    setBusy(false);
    setStatus(msg, { err: true });
  }

  function setBusy(on, activeBtn) {
    busy = on;
    hitl.classList.toggle("is-busy", on);
    document.querySelectorAll("#hitl .hitl-btn").forEach(function (b) {
      b.classList.toggle("is-active-action", !!(on && activeBtn && b === activeBtn));
    });
  }

  function detailText(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (d) {
          return (d && d.msg) || JSON.stringify(d);
        })
        .join("; ");
    }
    if (detail && typeof detail === "object") return JSON.stringify(detail);
    return "重算失败";
  }

  async function runHitl(action, sourceBtn) {
    if (busy) return;
    if (!reportId) {
      showErr("当前为静态报告预览，请从 Web 首页生成报告后再用人在回路重算。");
      return;
    }
    if (!apiBase) {
      showErr(
        "请通过服务地址打开报告（如 http://主机:8765/report/…），直接打开本地 HTML 无法调用接口。"
      );
      return;
    }
    var followup = (input.value || "").trim();
    if (action === "regenerate" && !followup) {
      showErr("请先填写追问内容，或点选上方快捷动作。");
      return;
    }
    if (action === "exclude_jobs" && !followup) {
      input.value = "不考虑外包/销售性质的数据岗";
    }
    // 兼容旧报告「增加对比城市」按钮
    if (action === "add_city") {
      action = "switch_direction";
    }
    if (action === "switch_direction" && !followup) {
      input.value = "请切换到产品经理方向，按新目标岗位重算";
    }
    if (action === "reject_conclusion" && !followup) {
      input.value = "请重新审视第1部分结论，证据不足的表述请改写或删除";
    }

    setBusy(true, sourceBtn || null);
    setStatus("正在按人在回路反馈重算…", { loading: true });
    try {
      var res = await fetch(apiBase + "/api/hitl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report_id: reportId,
          direction: direction,
          cities: cities,
          action: action || "regenerate",
          followup: (input.value || "").trim(),
        }),
      });
      var data = {};
      try {
        data = await res.json();
      } catch (_) {
        /* 非 JSON 响应 */
      }
      if (!res.ok) {
        throw new Error(detailText(data.detail) || "HTTP " + res.status);
      }
      setStatus("重算完成，正在打开新报告…", { loading: true });
      window.location.href = data.html_url;
    } catch (err) {
      var msg = String((err && err.message) || "");
      if (
        /failed to fetch|networkerror|load failed/i.test(msg) ||
        (err && err.name === "TypeError")
      ) {
        showErr(
          "连不上重算接口：请确认已启动开发或公网服务，并从首页生成后的 /report/… 打开本页（勿用 Live Server / 直接打开文件）。"
        );
        return;
      }
      showErr(msg || "请求失败");
    }
  }

  document.querySelectorAll("#hitl [data-action]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      runHitl(btn.getAttribute("data-action"), btn);
    });
  });

  var sendBtn = document.getElementById("hitlSend");
  if (sendBtn) {
    sendBtn.addEventListener("click", function () {
      runHitl("regenerate", sendBtn);
    });
  }

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") runHitl("regenerate", sendBtn || null);
  });
})();

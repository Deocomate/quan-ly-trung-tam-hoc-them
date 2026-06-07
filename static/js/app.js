const formatter = new Intl.NumberFormat("vi-VN");

function formatMoney(value) {
  return formatter.format(Number(value || 0));
}

function todayIso() {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  const local = new Date(now.getTime() - offset * 60000);
  return local.toISOString().slice(0, 10);
}

async function api(url, options = {}) {
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const response = await fetch(url, { credentials: "same-origin", headers, ...options });
  const type = response.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof data === "object" ? data.detail || data.message : data;
    throw new Error(message || "Có lỗi xảy ra, vui lòng thử lại.");
  }
  return data;
}

function toast(message, isError = false) {
  const node = document.createElement("div");
  node.className = `toast ${isError ? "error" : ""}`;
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 3200);
}

function formDataJson(form) {
  const formData = new FormData(form);
  const data = {};
  
  for (const name of formData.keys()) {
    const element = form.elements[name];
    if (element && element.multiple) {
      const values = formData.getAll(name);
      const isNumber = element.dataset.number === "true" || element.getAttribute("data-number") === "true";
      data[name] = isNumber ? values.map(Number) : values;
    } else {
      data[name] = formData.get(name);
    }
  }

  for (const input of form.querySelectorAll("input[type='checkbox']")) {
    data[input.name] = input.checked;
  }
  for (const input of form.querySelectorAll("[data-number='true']:not(select)")) {
    data[input.name] = input.value === "" ? null : Number(input.value);
  }
  return data;
}

function requireConfirm(message) {
  return window.confirm(message);
}

async function logout() {
  await api("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

async function checkAndRunAutoBackup() {
  if (window.location.pathname === "/login") {
    return;
  }
  if (sessionStorage.getItem("auto_backup_checked") === "true") {
    return;
  }
  
  try {
    const status = await api("/api/data/check-auto-backup");
    if (status.due) {
      toast("Đang tự động tải bản sao lưu định kỳ của hệ thống...");
      
      const response = await fetch("/api/data/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targets: ["students", "classes", "attendance", "tuition", "settings", "users"],
          format: "sql"
        })
      });
      
      if (!response.ok) {
        throw new Error("Không thể tải file sao lưu.");
      }
      
      const blob = await response.blob();
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `backup_auto_${status.backup_date}.sql`;
      if (contentDisposition && contentDisposition.indexOf('filename=') !== -1) {
        const matches = contentDisposition.match(/filename="([^"]+)"/);
        if (matches != null && matches[1]) {
          filename = matches[1];
        }
      }
      
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      await api("/api/data/confirm-auto-backup", {
        method: "POST",
        body: JSON.stringify({ backup_date: status.backup_date })
      });
      
      toast(`Đã tự động tải về bản sao lưu ngày ${status.backup_date} thành công.`);
    }
  } catch (err) {
    console.error("Auto-backup check failed:", err);
  } finally {
    sessionStorage.setItem("auto_backup_checked", "true");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    checkAndRunAutoBackup().catch(console.error);
  });
} else {
  checkAndRunAutoBackup().catch(console.error);
}


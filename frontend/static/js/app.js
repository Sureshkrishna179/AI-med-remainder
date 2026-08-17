/**
 * app.js — Client-side logic for the AI Medicine Reminder Dashboard
 * Handles AJAX CRUD operations, live table rendering, toasts, and form validation.
 */

// ── Toast Notification System ──────────────────────────────────
function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const iconMap = {
        success: "fa-circle-check",
        error: "fa-circle-xmark",
        info: "fa-circle-info",
    };

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="fa-solid ${iconMap[type] || iconMap.info}"></i><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast-fade-out");
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// ── Helper: Format time (HH:MM:SS → HH:MM AM/PM) ──────────────
function formatTimeDisplay(timeStr) {
    if (!timeStr) return "";
    const parts = timeStr.split(":");
    let h = parseInt(parts[0]);
    const m = parts[1];
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    return `${h}:${m} ${ampm}`;
}

// ── Fetch & Render Active Schedules ────────────────────────────
async function loadSchedules() {
    const tbody = document.getElementById("schedules-tbody");
    const statTotal = document.getElementById("stat-total-schedules");
    const statActive = document.getElementById("stat-active-schedules");

    try {
        const res = await fetch("/api/schedules");
        const json = await res.json();

        if (json.status !== "success") {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load schedules.</td></tr>`;
            return;
        }

        const data = json.data;
        if (statTotal) statTotal.textContent = data.length;
        if (statActive) statActive.textContent = data.filter(s => s.is_active).length;

        if (data.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6">
                    <div class="empty-state">
                        <i class="fa-solid fa-calendar-xmark"></i>
                        No schedules configured yet. Add one using the form!
                    </div>
                </td></tr>`;
            return;
        }

        tbody.innerHTML = data.map(s => `
            <tr>
                <td><strong>${s.patient_name}</strong></td>
                <td>${s.medicine_name}</td>
                <td>${s.dosage}</td>
                <td style="color: var(--primary); font-weight: 600;">${formatTimeDisplay(s.alarm_time)}</td>
                <td>
                    <span class="badge ${s.is_active ? 'badge-taken' : 'badge-missed'}">
                        ${s.is_active ? '● Active' : '● Off'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-secondary btn-icon btn-sm" title="Edit" onclick="openEditModal(${s.schedule_id}, '${s.patient_name}', '${s.medicine_name}', '${s.dosage}', '${s.alarm_time}')">
                        <i class="fa-solid fa-pencil" style="font-size:0.75rem"></i>
                    </button>
                    <button class="btn btn-danger btn-icon btn-sm" title="Delete" onclick="deleteSchedule(${s.schedule_id})">
                        <i class="fa-solid fa-trash-can" style="font-size:0.75rem"></i>
                    </button>
                </td>
            </tr>
        `).join("");

    } catch (err) {
        console.error("Load schedules error:", err);
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Connection error.</td></tr>`;
    }
}

// ── Fetch & Render Adherence Logs ──────────────────────────────
async function loadLogs() {
    const tbody = document.getElementById("logs-tbody");
    const statTaken = document.getElementById("stat-taken-count");

    try {
        const res = await fetch("/api/logs");
        const json = await res.json();

        if (json.status !== "success") {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load logs.</td></tr>`;
            return;
        }

        const data = json.data;
        if (statTaken) {
            statTaken.textContent = data.filter(l => l.status === "Taken").length;
        }

        if (data.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6">
                    <div class="empty-state">
                        <i class="fa-solid fa-clipboard-list"></i>
                        No adherence logs yet. The AI will create logs when alarms trigger.
                    </div>
                </td></tr>`;
            return;
        }

        tbody.innerHTML = data.map(l => {
            let badgeClass = "badge-pending";
            let badgeIcon = "fa-clock";
            if (l.status === "Taken") { badgeClass = "badge-taken"; badgeIcon = "fa-circle-check"; }
            else if (l.status === "Missed") { badgeClass = "badge-missed"; badgeIcon = "fa-circle-xmark"; }

            return `
                <tr>
                    <td>${l.triggered_at}</td>
                    <td>${l.patient_name}</td>
                    <td>${l.medicine_name}</td>
                    <td>${l.dosage}</td>
                    <td style="color: var(--text-muted);">${formatTimeDisplay(l.alarm_time)}</td>
                    <td>
                        <span class="badge ${badgeClass}">
                            <i class="fa-solid ${badgeIcon}"></i> ${l.status}
                        </span>
                    </td>
                </tr>
            `;
        }).join("");

    } catch (err) {
        console.error("Load logs error:", err);
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Connection error.</td></tr>`;
    }
}

// ── Add Schedule (Form Submit) ─────────────────────────────────
async function handleAddSchedule(e) {
    e.preventDefault();

    const patient_name = document.getElementById("patient_name").value.trim();
    const medicine_name = document.getElementById("medicine_name").value.trim();
    const dosage = document.getElementById("dosage").value.trim();
    const alarm_time = document.getElementById("alarm_time").value.trim();

    // Client-side validation
    if (!patient_name || !medicine_name || !dosage || !alarm_time) {
        showToast("All fields are required!", "error");
        return;
    }

    try {
        const res = await fetch("/api/add_schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patient_name, medicine_name, dosage, alarm_time }),
        });

        const json = await res.json();

        if (json.status === "success") {
            showToast(json.message, "success");
            document.getElementById("scheduleForm").reset();
            loadSchedules();
        } else {
            showToast(json.message, "error");
        }
    } catch (err) {
        showToast("Failed to connect to the backend server. Is Python running?", "error");
    }
}

// ── Delete Schedule ────────────────────────────────────────────
async function deleteSchedule(scheduleId) {
    if (!confirm("Are you sure you want to delete this schedule?")) return;

    try {
        const res = await fetch(`/api/delete_schedule/${scheduleId}`, { method: "DELETE" });
        const json = await res.json();

        if (json.status === "success") {
            showToast("Schedule deleted.", "success");
            loadSchedules();
            loadLogs();
        } else {
            showToast(json.message, "error");
        }
    } catch (err) {
        showToast("Network error. Check the server.", "error");
    }
}

// ── Edit Modal ─────────────────────────────────────────────────
let editingScheduleId = null;

function openEditModal(id, patient, medicine, dosage, alarm_time) {
    editingScheduleId = id;
    document.getElementById("edit-patient").value = patient;
    document.getElementById("edit-medicine").value = medicine;
    document.getElementById("edit-dosage").value = dosage;
    // alarm_time comes as HH:MM:SS, time input needs HH:MM
    document.getElementById("edit-time").value = alarm_time.substring(0, 5);
    document.getElementById("edit-modal").classList.add("active");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.remove("active");
    editingScheduleId = null;
}

async function handleEditSubmit(e) {
    e.preventDefault();
    if (!editingScheduleId) return;

    const payload = {
        patient_name: document.getElementById("edit-patient").value.trim(),
        medicine_name: document.getElementById("edit-medicine").value.trim(),
        dosage: document.getElementById("edit-dosage").value.trim(),
        alarm_time: document.getElementById("edit-time").value.trim(),
    };

    try {
        const res = await fetch(`/api/update_schedule/${editingScheduleId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const json = await res.json();

        if (json.status === "success") {
            showToast("Schedule updated!", "success");
            closeEditModal();
            loadSchedules();
        } else {
            showToast(json.message, "error");
        }
    } catch (err) {
        showToast("Network error.", "error");
    }
}

// ── Voice Test ─────────────────────────────────────────────────
async function testVoiceAlert() {
    showToast("Playing voice test...", "info");
    try {
        await fetch("/api/test_voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: "Hello! This is a test of the AI Medicine Reminder voice system. The system is working correctly." }),
        });
        showToast("Voice test completed.", "success");
    } catch (err) {
        showToast("Voice test failed.", "error");
    }
}

// ── Logout ─────────────────────────────────────────────────────
async function handleLogout() {
    try {
        await fetch("/api/logout", { method: "POST" });
        window.location.href = "/login";
    } catch (err) {
        window.location.href = "/login";
    }
}

// ── Initialization ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Bind form
    const addForm = document.getElementById("scheduleForm");
    if (addForm) addForm.addEventListener("submit", handleAddSchedule);

    const editForm = document.getElementById("editForm");
    if (editForm) editForm.addEventListener("submit", handleEditSubmit);

    // Close edit modal
    const closeBtn = document.getElementById("close-edit-modal");
    if (closeBtn) closeBtn.addEventListener("click", closeEditModal);

    // Voice test button
    const voiceBtn = document.getElementById("test-voice-btn");
    if (voiceBtn) voiceBtn.addEventListener("click", testVoiceAlert);

    // Logout
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);

    // Initial data load
    loadSchedules();
    loadLogs();

    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadSchedules();
        loadLogs();
    }, 30000);
});

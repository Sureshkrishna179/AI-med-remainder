/**
 * MedAssist AI — Main Application Logic
 * Multi-screen SPA with caregiver authentication, schedule management,
 * slide-out panels, and Razorpay integration.
 * 
 * Phase 1 Enhancements:
 *  - Edit/Delete/Pause schedules via context menu
 *  - Bottle photo upload with preview
 *  - AM/PM visual indicator + 24hr toggle
 *  - Polypharmacy safety warning
 *  - Missed-dose highlighting + acknowledge
 *  - Skeleton loader during fetch
 *  - Empty state SVG illustration
 *  - Doctor's Report export (print CSS)
 */

document.addEventListener('DOMContentLoaded', () => {
  // === Screen References ===
  const screens = {
    splash: document.getElementById('screen-splash'),
    onboarding: document.getElementById('screen-onboarding'),
    setup: document.getElementById('screen-setup'),
    dashboard: document.getElementById('screen-dashboard')
  };

  // === Element References ===
  const btnGetStarted = document.getElementById('btn-get-started');
  const setupForm = document.getElementById('setup-form');
  const setupAlert = document.getElementById('setup-alert');
  const scheduleForm = document.getElementById('schedule-form');
  const scheduleAlert = document.getElementById('schedule-alert');
  const btnAddSchedule = document.getElementById('btn-add-schedule');
  const btnClosePanel = document.getElementById('btn-close-panel');
  const schedulePanel = document.getElementById('schedule-panel');
  const scheduleOverlay = document.getElementById('schedule-overlay');
  const btnRefreshLogs = document.getElementById('btn-refresh-logs');
  const logsTableBody = document.getElementById('logs-table-body');
  const scheduleList = document.getElementById('schedule-list');
  const scheduleCount = document.getElementById('schedule-count');
  const headerPatientName = document.getElementById('header-patient-name');
  const profileInitial = document.getElementById('profile-initial');
  const subBanner = document.getElementById('subscription-banner');
  const btnSubscribe = document.getElementById('btn-subscribe');
  const panelTitle = document.getElementById('panel-title');
  const editScheduleId = document.getElementById('edit_schedule_id');
  const btnSaveSchedule = document.getElementById('btn-save-schedule');

  // Photo upload
  const bottlePhotoInput = document.getElementById('bottle_photo');
  const uploadPlaceholder = document.getElementById('upload-placeholder');
  const photoPreviewRow = document.getElementById('photo-preview-row');
  const photoPreview = document.getElementById('photo-preview');
  const btnRemovePhoto = document.getElementById('btn-remove-photo');
  const bottleImageUrlInput = document.getElementById('bottle_image_url');

  // AM/PM indicator
  const timeInput = document.getElementById('time_str');
  const timeIndicator = document.getElementById('time-indicator');
  const timeIndicatorIcon = document.getElementById('time-indicator-icon');
  const timeIndicatorLabel = document.getElementById('time-indicator-label');
  const toggle24hr = document.getElementById('toggle-24hr');

  // Safety warning modal
  const safetyOverlay = document.getElementById('safety-warning-overlay');
  const safetyModal = document.getElementById('safety-warning-modal');
  const btnCancelSafety = document.getElementById('btn-cancel-safety');
  const btnConfirmSafety = document.getElementById('btn-confirm-safety');

  // Export report
  const btnExportReport = document.getElementById('btn-export-report');

  // Login modal
  const loginOverlay = document.getElementById('login-overlay');
  const loginModal = document.getElementById('login-modal');
  const loginForm = document.getElementById('login-form');
  const loginAlert = document.getElementById('login-alert');
  const linkSignup = document.getElementById('link-signup');

  // Sidebar references
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebar-overlay');
  const btnOpenSidebar = document.getElementById('btn-open-sidebar');
  const btnCloseSidebar = document.getElementById('btn-close-sidebar');
  const sidebarProfileName = document.getElementById('sidebar-profile-name');
  const sidebarProfilePhone = document.getElementById('sidebar-profile-phone');
  const sidebarProfileInitial = document.getElementById('sidebar-profile-initial');

  // Logout Caution Modal
  const btnLogout = document.getElementById('btn-logout');
  const logoutOverlay = document.getElementById('logout-overlay');
  const logoutModal = document.getElementById('logout-modal');
  const btnCancelLogout = document.getElementById('btn-cancel-logout');
  const btnConfirmLogout = document.getElementById('btn-confirm-logout');

  // Delete Account Caution Modal
  const btnDeleteAccount = document.getElementById('btn-delete-account');
  const deleteOverlay = document.getElementById('delete-overlay');
  const deleteModal = document.getElementById('delete-modal');
  const deleteConfirmCheck = document.getElementById('delete-confirm-check');
  const btnCancelDelete = document.getElementById('btn-cancel-delete');
  const btnConfirmDelete = document.getElementById('btn-confirm-delete');

  // === State ===
  let currentCaregiver = null;
  let schedules = [];
  let use24hr = localStorage.getItem('medassist_24hr') === 'true';
  let pendingSafetyResolve = null; // For polypharmacy safety promise
  let activeContextMenu = null; // Track open context menu

  // === Screen Router ===
  function showScreen(name) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    if (screens[name]) {
      screens[name].classList.remove('hidden');
      requestAnimationFrame(() => {
        screens[name].classList.add('active');
      });
    }
  }

  // === Alert Helper ===
  function showAlert(el, msg, type = 'success') {
    el.textContent = msg;
    el.className = `alert alert-${type}`;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 5000);
  }

  // === Startup Flow ===
  function initApp() {
    const saved = localStorage.getItem('medassist_caregiver');
    if (saved) {
      currentCaregiver = JSON.parse(saved);
      showScreen('splash');
      setTimeout(() => {
        showScreen('dashboard');
        loadDashboard();
      }, 3000);
    } else {
      showScreen('splash');
      setTimeout(() => showScreen('onboarding'), 3000);
    }

    // Init 24hr toggle state
    if (use24hr) toggle24hr.classList.add('active');
  }

  // === ONBOARDING → SETUP ===
  btnGetStarted.addEventListener('click', () => {
    showScreen('setup');
  });

  // === Login Modal ===
  if (linkSignup) {
    linkSignup.addEventListener('click', (e) => {
      e.preventDefault();
      loginOverlay.classList.add('hidden');
      loginModal.classList.add('hidden');
      loginOverlay.classList.remove('visible');
      loginModal.classList.remove('visible');
      showScreen('setup');
    });
  }

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const phone = '+91' + document.getElementById('login_phone').value.trim();
      const passcode = document.getElementById('login_passcode').value.trim();

      try {
        const response = await fetch('/caregivers/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ caregiver_phone: phone, passcode: passcode })
        });

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || 'Login failed');
        }

        currentCaregiver = await response.json();
        localStorage.setItem('medassist_caregiver', JSON.stringify(currentCaregiver));
        loginOverlay.classList.add('hidden');
        loginModal.classList.add('hidden');
        showScreen('dashboard');
        loadDashboard();
      } catch (err) {
        showAlert(loginAlert, err.message, 'error');
      }
    });
  }

  // === SETUP: Save Profile ===
  setupForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const data = {
      caregiver_name: document.getElementById('cg_name').value.trim(),
      caregiver_phone: '+91' + document.getElementById('cg_phone').value.trim(),
      caregiver_whatsapp: document.getElementById('cg_whatsapp').value.trim()
        ? '+91' + document.getElementById('cg_whatsapp').value.trim()
        : null,
      passcode: document.getElementById('cg_passcode').value.trim(),
      patient_name: document.getElementById('pt_name').value.trim(),
      patient_phone: '+91' + document.getElementById('pt_phone').value.trim(),
      language: document.getElementById('pt_language').value,
      consent_accepted: document.getElementById('consent_check').checked
    };

    if (!data.consent_accepted) {
      showAlert(setupAlert, 'Please accept the privacy policy to continue.', 'error');
      return;
    }

    try {
      const response = await fetch('/caregivers/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `Registration failed (${response.status})`);
      }

      currentCaregiver = await response.json();
      localStorage.setItem('medassist_caregiver', JSON.stringify(currentCaregiver));
      showScreen('dashboard');
      loadDashboard();
    } catch (err) {
      showAlert(setupAlert, err.message, 'error');
    }
  });

  // === DASHBOARD: Load all data ===
  function loadDashboard() {
    if (!currentCaregiver) return;

    headerPatientName.textContent = `Protecting ${currentCaregiver.patient_name}`;
    profileInitial.textContent = (currentCaregiver.caregiver_name || 'C')[0].toUpperCase();
    if (sidebarProfileInitial) sidebarProfileInitial.textContent = (currentCaregiver.caregiver_name || 'C')[0].toUpperCase();
    if (sidebarProfileName) sidebarProfileName.textContent = currentCaregiver.caregiver_name || 'Caregiver';
    if (sidebarProfilePhone) sidebarProfilePhone.textContent = currentCaregiver.caregiver_phone || '';

    updateSubscriptionBanner();
    fetchSchedules();
    fetchLogs();
  }

  // === SIDEBAR CONTROLS ===
  if (btnOpenSidebar) btnOpenSidebar.addEventListener('click', openSidebar);
  if (btnCloseSidebar) btnCloseSidebar.addEventListener('click', closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

  function openSidebar() {
    sidebarOverlay.classList.remove('hidden');
    sidebar.classList.remove('hidden');
    requestAnimationFrame(() => {
      sidebarOverlay.classList.add('visible');
      sidebar.classList.add('visible');
    });
  }

  function closeSidebar() {
    sidebarOverlay.classList.remove('visible');
    sidebar.classList.remove('visible');
    setTimeout(() => {
      sidebarOverlay.classList.add('hidden');
      sidebar.classList.add('hidden');
    }, 350);
  }

  // === LOGOUT CAUTION MODAL ===
  if (btnLogout) {
    btnLogout.addEventListener('click', () => {
      closeSidebar();
      openModal(logoutOverlay, logoutModal);
    });
  }
  if (btnCancelLogout) {
    btnCancelLogout.addEventListener('click', () => closeModal(logoutOverlay, logoutModal));
  }
  if (btnConfirmLogout) {
    btnConfirmLogout.addEventListener('click', () => {
      closeModal(logoutOverlay, logoutModal);
      currentCaregiver = null;
      localStorage.clear();
      sessionStorage.clear();
      showScreen('onboarding');
    });
  }

  // === DELETE ACCOUNT CAUTION MODAL ===
  if (btnDeleteAccount) {
    btnDeleteAccount.addEventListener('click', () => {
      closeSidebar();
      if (deleteConfirmCheck) deleteConfirmCheck.checked = false;
      if (btnConfirmDelete) btnConfirmDelete.disabled = true;
      openModal(deleteOverlay, deleteModal);
    });
  }
  if (deleteConfirmCheck) {
    deleteConfirmCheck.addEventListener('change', (e) => {
      btnConfirmDelete.disabled = !e.target.checked;
    });
  }
  if (btnCancelDelete) {
    btnCancelDelete.addEventListener('click', () => closeModal(deleteOverlay, deleteModal));
  }
  if (btnConfirmDelete) {
    btnConfirmDelete.addEventListener('click', async () => {
      if (!currentCaregiver) return;
      try {
        const response = await fetch(`/caregivers/${currentCaregiver.id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete account.');

        closeModal(deleteOverlay, deleteModal);
        currentCaregiver = null;
        schedules = [];
        localStorage.clear();
        sessionStorage.clear();
        if (setupForm) setupForm.reset();
        if (scheduleForm) scheduleForm.reset();
        alert('Your account details (Name, Phone Numbers, Passcode), schedules, adherence logs, and subscription records have been permanently deleted with zero trace.');
        showScreen('onboarding');
      } catch (err) {
        alert('Error deleting account: ' + err.message);
      }
    });
  }

  function openModal(overlayEl, modalEl) {
    overlayEl.classList.remove('hidden');
    modalEl.classList.remove('hidden');
    requestAnimationFrame(() => {
      overlayEl.classList.add('visible');
      modalEl.classList.add('visible');
    });
  }

  function closeModal(overlayEl, modalEl) {
    overlayEl.classList.remove('visible');
    modalEl.classList.remove('visible');
    setTimeout(() => {
      overlayEl.classList.add('hidden');
      modalEl.classList.add('hidden');
    }, 300);
  }

  function updateSubscriptionBanner() {
    if (!currentCaregiver) return;
    if (currentCaregiver.is_premium) {
      subBanner.className = 'sub-banner sub-premium';
      subBanner.innerHTML = `
        <div class="sub-info">
          <span class="sub-badge">PREMIUM ✓</span>
          <span class="sub-text">Unlimited schedules active. Thank you for subscribing!</span>
        </div>
      `;
    }
  }

  // =============================================
  // SCHEDULE MANAGEMENT
  // =============================================

  // === Show Skeleton Loader ===
  function showScheduleSkeleton() {
    scheduleList.innerHTML = `
      <div class="skeleton-card">
        <div class="skeleton-dot"></div>
        <div class="skeleton-time"></div>
        <div class="skeleton-details">
          <div class="skeleton-line w-60"></div>
          <div class="skeleton-line w-80"></div>
        </div>
      </div>
      <div class="skeleton-card">
        <div class="skeleton-dot"></div>
        <div class="skeleton-time"></div>
        <div class="skeleton-details">
          <div class="skeleton-line w-60"></div>
          <div class="skeleton-line w-80"></div>
        </div>
      </div>
    `;
  }

  // === Fetch Schedules ===
  async function fetchSchedules() {
    if (!currentCaregiver) return;
    showScheduleSkeleton();
    try {
      const response = await fetch(`/schedules/${currentCaregiver.id}`);
      if (!response.ok) throw new Error('Failed to load schedules');
      schedules = await response.json();
      renderSchedules();
    } catch (err) {
      console.error('Error loading schedules:', err);
      renderSchedules(); // Show empty state
    }
  }

  // === Empty State SVG ===
  const emptyStateSVG = `
    <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="40" y="20" width="120" height="160" rx="12" stroke="#6366f1" stroke-width="2" fill="none" opacity="0.4"/>
      <rect x="55" y="45" width="90" height="8" rx="4" fill="#6366f1" opacity="0.2"/>
      <rect x="55" y="65" width="70" height="8" rx="4" fill="#6366f1" opacity="0.15"/>
      <rect x="55" y="85" width="80" height="8" rx="4" fill="#6366f1" opacity="0.2"/>
      <rect x="55" y="105" width="60" height="8" rx="4" fill="#6366f1" opacity="0.15"/>
      <circle cx="100" cy="150" r="15" stroke="#6366f1" stroke-width="2" fill="none" opacity="0.3"/>
      <line x1="93" y1="150" x2="100" y2="157" stroke="#6366f1" stroke-width="2" opacity="0.3" stroke-linecap="round"/>
      <line x1="100" y1="157" x2="112" y2="143" stroke="#6366f1" stroke-width="2" opacity="0.3" stroke-linecap="round"/>
      <circle cx="155" cy="35" r="20" fill="#6366f1" opacity="0.08"/>
      <text x="148" y="42" font-size="20" fill="#6366f1" opacity="0.3">💊</text>
    </svg>
  `;

  function renderSchedules() {
    if (schedules.length === 0) {
      scheduleList.innerHTML = `
        <div class="empty-state-illustration">
          ${emptyStateSVG}
          <p>No medication schedules added yet.</p>
          <p class="empty-hint">Click "+ Add Schedule" to set up the first reminder.</p>
        </div>
      `;
      scheduleCount.textContent = 'No schedules yet';
      return;
    }

    scheduleCount.textContent = `${schedules.length} active schedule${schedules.length > 1 ? 's' : ''}`;

    scheduleList.innerHTML = schedules.map(s => {
      const isPaused = !s.is_active;
      const pausedClass = isPaused ? 'schedule-item-paused' : '';
      const pausedBadge = isPaused ? '<span class="paused-badge">PAUSED</span>' : '';
      const bottleThumb = s.bottle_image_url
        ? `<img src="${escapeHtml(s.bottle_image_url)}" class="schedule-bottle-thumb" alt="Bottle">`
        : '';

      return `
        <div class="schedule-item ${pausedClass}" data-schedule-id="${s.id}">
          <div class="schedule-status-dot"></div>
          <div class="schedule-time">${formatTime(s.time_str)}</div>
          ${bottleThumb}
          <div class="schedule-details">
            <div class="schedule-med">${escapeHtml(s.med_name)}${pausedBadge}</div>
            <div class="schedule-meta">
              <span>💊 ${escapeHtml(s.quantity || '1 Tablet')}</span>
              <span>🍽️ ${escapeHtml(s.food_instruction || 'Any Time')}</span>
              <span>🏷️ ${escapeHtml(s.tactile_marker)}</span>
            </div>
          </div>
          <button class="schedule-context-btn" data-id="${s.id}" title="Options">⋯</button>
        </div>
      `;
    }).join('');

    // Attach context menu listeners
    document.querySelectorAll('.schedule-context-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const scheduleId = parseInt(btn.dataset.id);
        toggleContextMenu(btn, scheduleId);
      });
    });
  }

  // === Context Menu ===
  function toggleContextMenu(btnEl, scheduleId) {
    closeAllContextMenus();
    const schedule = schedules.find(s => s.id === scheduleId);
    if (!schedule) return;

    const isPaused = !schedule.is_active;
    const pauseLabel = isPaused ? '▶️ Resume' : '⏸ Pause';
    const pauseAction = isPaused ? 'resume' : 'pause';

    const menu = document.createElement('div');
    menu.className = 'context-menu-dropdown';
    menu.innerHTML = `
      <button class="context-menu-item" data-action="edit">✏️ Edit</button>
      <button class="context-menu-item" data-action="${pauseAction}">${pauseLabel}</button>
      <div class="context-menu-divider"></div>
      <button class="context-menu-item danger" data-action="delete">🗑️ Delete</button>
    `;

    btnEl.closest('.schedule-item').appendChild(menu);
    activeContextMenu = menu;

    menu.querySelectorAll('.context-menu-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = item.dataset.action;
        closeAllContextMenus();

        if (action === 'edit') editSchedule(scheduleId);
        else if (action === 'pause') pauseSchedule(scheduleId, false);
        else if (action === 'resume') pauseSchedule(scheduleId, true);
        else if (action === 'delete') deleteSchedule(scheduleId);
      });
    });
  }

  function closeAllContextMenus() {
    document.querySelectorAll('.context-menu-dropdown').forEach(m => m.remove());
    activeContextMenu = null;
  }

  // Close context menus when clicking outside
  document.addEventListener('click', () => closeAllContextMenus());

  // === Edit Schedule ===
  function editSchedule(scheduleId) {
    const schedule = schedules.find(s => s.id === scheduleId);
    if (!schedule) return;

    panelTitle.textContent = 'Edit Medication Schedule';
    editScheduleId.value = scheduleId;
    btnSaveSchedule.textContent = 'Update Schedule';

    // Pre-fill form
    document.getElementById('med_name').value = schedule.med_name;
    document.getElementById('time_str').value = schedule.time_str;
    document.getElementById('quantity').value = schedule.quantity || '1 Tablet';
    document.getElementById('food_instruction').value = schedule.food_instruction || 'Any Time';
    document.getElementById('tactile_marker').value = schedule.tactile_marker;

    // Pre-fill photo if exists
    if (schedule.bottle_image_url) {
      bottleImageUrlInput.value = schedule.bottle_image_url;
      photoPreview.src = schedule.bottle_image_url;
      uploadPlaceholder.classList.add('hidden');
      photoPreviewRow.classList.remove('hidden');
    } else {
      resetPhotoUpload();
    }

    updateTimeIndicator();
    openPanel();
  }

  // === Pause/Resume Schedule ===
  async function pauseSchedule(scheduleId, setActive) {
    try {
      const response = await fetch(`/schedules/${scheduleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: setActive })
      });
      if (!response.ok) throw new Error('Failed to update schedule');
      fetchSchedules();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  }

  // === Delete Schedule ===
  async function deleteSchedule(scheduleId) {
    const schedule = schedules.find(s => s.id === scheduleId);
    const name = schedule ? schedule.med_name : 'this schedule';
    if (!confirm(`Permanently delete "${name}" and all its adherence logs?`)) return;

    try {
      const response = await fetch(`/schedules/${scheduleId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete schedule');
      fetchSchedules();
      fetchLogs();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  }

  // === Slide-Out Schedule Panel ===
  btnAddSchedule.addEventListener('click', () => {
    if (!currentCaregiver.is_premium && schedules.length >= 1) {
      alert('Free tier allows 1 schedule. Subscribe to ₹199/month for unlimited schedules!');
      return;
    }
    resetScheduleForm();
    openPanel();
  });

  btnClosePanel.addEventListener('click', closePanel);
  scheduleOverlay.addEventListener('click', closePanel);

  function openPanel() {
    scheduleOverlay.classList.remove('hidden');
    schedulePanel.classList.remove('hidden');
    requestAnimationFrame(() => {
      scheduleOverlay.classList.add('visible');
      schedulePanel.classList.add('visible');
    });
  }

  function closePanel() {
    scheduleOverlay.classList.remove('visible');
    schedulePanel.classList.remove('visible');
    setTimeout(() => {
      scheduleOverlay.classList.add('hidden');
      schedulePanel.classList.add('hidden');
    }, 350);
  }

  function resetScheduleForm() {
    panelTitle.textContent = 'Add Medication Schedule';
    editScheduleId.value = '';
    btnSaveSchedule.textContent = 'Save Schedule';
    scheduleForm.reset();
    resetPhotoUpload();
    updateTimeIndicator();
  }

  // =============================================
  // PHOTO UPLOAD
  // =============================================

  if (bottlePhotoInput) {
    bottlePhotoInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      // Validate size (5 MB)
      if (file.size > 5 * 1024 * 1024) {
        alert('File too large. Maximum size is 5 MB.');
        bottlePhotoInput.value = '';
        return;
      }

      // Show local preview immediately
      const reader = new FileReader();
      reader.onload = (ev) => {
        photoPreview.src = ev.target.result;
        uploadPlaceholder.classList.add('hidden');
        photoPreviewRow.classList.remove('hidden');
      };
      reader.readAsDataURL(file);
    });
  }

  if (btnRemovePhoto) {
    btnRemovePhoto.addEventListener('click', () => {
      resetPhotoUpload();
    });
  }

  function resetPhotoUpload() {
    if (bottlePhotoInput) bottlePhotoInput.value = '';
    if (bottleImageUrlInput) bottleImageUrlInput.value = '';
    if (photoPreview) photoPreview.src = '';
    if (uploadPlaceholder) uploadPlaceholder.classList.remove('hidden');
    if (photoPreviewRow) photoPreviewRow.classList.add('hidden');
  }

  async function uploadBottlePhoto() {
    const file = bottlePhotoInput.files[0];
    if (!file) return bottleImageUrlInput.value || null;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/uploads/bottle-photo', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Photo upload failed');
      const result = await response.json();
      return result.url;
    } catch (err) {
      console.error('Photo upload error:', err);
      return null;
    }
  }

  // =============================================
  // AM/PM VISUAL INDICATOR + 24HR TOGGLE
  // =============================================

  if (timeInput) {
    timeInput.addEventListener('input', updateTimeIndicator);
    timeInput.addEventListener('change', updateTimeIndicator);
  }

  function updateTimeIndicator() {
    const val = timeInput.value;
    if (!val) {
      timeIndicator.className = 'time-indicator';
      timeIndicatorIcon.textContent = '🕐';
      timeIndicatorLabel.textContent = '--';
      return;
    }

    const [h] = val.split(':').map(Number);
    const isAM = h < 12;
    const isDaytime = h >= 6 && h < 18;

    if (use24hr) {
      timeIndicatorIcon.textContent = isDaytime ? '☀️' : '🌙';
      timeIndicatorLabel.textContent = isDaytime ? 'Day' : 'Night';
      timeIndicator.className = `time-indicator ${isDaytime ? 'am' : 'pm'}`;
    } else {
      timeIndicatorIcon.textContent = isAM ? '☀️' : '🌙';
      timeIndicatorLabel.textContent = isAM ? 'AM' : 'PM';
      timeIndicator.className = `time-indicator ${isAM ? 'am' : 'pm'}`;
    }
  }

  if (toggle24hr) {
    toggle24hr.addEventListener('click', () => {
      use24hr = !use24hr;
      localStorage.setItem('medassist_24hr', use24hr.toString());
      toggle24hr.classList.toggle('active', use24hr);
      updateTimeIndicator();
      renderSchedules(); // Re-render with new time format
    });
  }

  // =============================================
  // POLYPHARMACY SAFETY WARNING
  // =============================================

  function checkPolypharmacySafety(quantity) {
    // Check if quantity >= 5 tablets/capsules
    const match = quantity.match(/^(\d+)/);
    if (match) {
      const num = parseInt(match[1]);
      if (num >= 5) return true;
    }
    // Check if user has 4+ active schedules already
    const activeCount = schedules.filter(s => s.is_active).length;
    if (activeCount >= 4) return true;

    return false;
  }

  function showSafetyWarning() {
    return new Promise((resolve) => {
      pendingSafetyResolve = resolve;
      openModal(safetyOverlay, safetyModal);
    });
  }

  if (btnCancelSafety) {
    btnCancelSafety.addEventListener('click', () => {
      closeModal(safetyOverlay, safetyModal);
      if (pendingSafetyResolve) pendingSafetyResolve(false);
      pendingSafetyResolve = null;
    });
  }

  if (btnConfirmSafety) {
    btnConfirmSafety.addEventListener('click', () => {
      closeModal(safetyOverlay, safetyModal);
      if (pendingSafetyResolve) pendingSafetyResolve(true);
      pendingSafetyResolve = null;
    });
  }

  // =============================================
  // SAVE / UPDATE SCHEDULE
  // =============================================

  scheduleForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentCaregiver) return;

    const quantity = document.getElementById('quantity').value;
    const isEditing = !!editScheduleId.value;

    // Polypharmacy safety check (skip for edits unless quantity changed)
    if (!isEditing && checkPolypharmacySafety(quantity)) {
      const confirmed = await showSafetyWarning();
      if (!confirmed) return;
    }

    // Upload photo if new file selected
    const photoUrl = await uploadBottlePhoto();

    const data = {
      med_name: document.getElementById('med_name').value.trim(),
      time_str: document.getElementById('time_str').value,
      quantity: quantity,
      food_instruction: document.getElementById('food_instruction').value,
      tactile_marker: document.getElementById('tactile_marker').value,
      bottle_image_url: photoUrl || null
    };

    try {
      let response;
      if (isEditing) {
        response = await fetch(`/schedules/${editScheduleId.value}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      } else {
        data.caregiver_id = currentCaregiver.id;
        response = await fetch('/schedules/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      }

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `Failed (${response.status})`);
      }

      const successMsg = isEditing
        ? 'Schedule updated successfully!'
        : 'Schedule created! Reminder calls will trigger at the set time.';
      showAlert(scheduleAlert, successMsg, 'success');
      resetScheduleForm();
      setTimeout(closePanel, 1500);
      fetchSchedules();
    } catch (err) {
      showAlert(scheduleAlert, err.message, 'error');
    }
  });

  // =============================================
  // ADHERENCE LOGS WITH HIGHLIGHTING + ACKNOWLEDGE
  // =============================================

  async function fetchLogs() {
    if (!currentCaregiver) return;
    try {
      const response = await fetch(`/logs/${currentCaregiver.id}`);
      if (!response.ok) throw new Error('Failed to load logs');
      const logs = await response.json();
      renderLogs(logs);
    } catch (err) {
      console.error('Error loading logs:', err);
    }
  }

  function renderLogs(logs) {
    if (logs.length === 0) {
      logsTableBody.innerHTML = '<tr><td colspan="6" class="empty-state">Adherence logs will appear here after reminders trigger.</td></tr>';
      return;
    }

    // Sort: unacknowledged missed first (pinned to top)
    const sortedLogs = [...logs].sort((a, b) => {
      const aUrgent = a.status === 'Missed' && !a.acknowledged_by_caregiver;
      const bUrgent = b.status === 'Missed' && !b.acknowledged_by_caregiver;
      if (aUrgent && !bUrgent) return -1;
      if (!aUrgent && bUrgent) return 1;
      return 0; // Keep existing order (already sorted by timestamp desc from API)
    });

    logsTableBody.innerHTML = sortedLogs.map(log => {
      const isMissed = log.status === 'Missed';
      const isUnack = isMissed && !log.acknowledged_by_caregiver;
      const statusClass = log.status === 'Confirmed' ? 'confirmed' :
                           isMissed ? 'missed' : 'pending';
      const statusIcon = log.status === 'Confirmed' ? '✅' :
                          isMissed ? '🚨' : '⏳';
      const rowClass = isUnack ? 'log-row-missed-unack' : (isMissed ? 'log-row-missed' : '');
      const ackButton = isUnack
        ? `<button class="btn-acknowledge" data-log-id="${log.id}" title="Acknowledge this missed dose">⚡ Acknowledge</button>`
        : (isMissed ? '<span style="font-size:0.78rem;color:var(--text-muted)">Acknowledged ✓</span>' : '—');

      return `
        <tr class="${rowClass}">
          <td>${formatTimestamp(log.timestamp)}</td>
          <td>${escapeHtml(log.med_name || '—')}</td>
          <td>${escapeHtml(log.quantity || '—')} ${escapeHtml(log.food_instruction || '')}</td>
          <td><span class="badge badge-${statusClass}">${statusIcon} ${log.status}</span></td>
          <td>${log.retry_count}</td>
          <td>${ackButton}</td>
        </tr>
      `;
    }).join('');

    // Attach acknowledge button listeners
    document.querySelectorAll('.btn-acknowledge').forEach(btn => {
      btn.addEventListener('click', async () => {
        const logId = btn.dataset.logId;
        try {
          const response = await fetch(`/logs/${logId}/acknowledge`, { method: 'POST' });
          if (!response.ok) throw new Error('Failed to acknowledge');
          fetchLogs(); // Refresh
        } catch (err) {
          alert('Error: ' + err.message);
        }
      });
    });
  }

  // === Refresh Logs ===
  btnRefreshLogs.addEventListener('click', fetchLogs);
  setInterval(fetchLogs, 15000);

  // =============================================
  // DOCTOR'S REPORT EXPORT
  // =============================================

  if (btnExportReport) {
    btnExportReport.addEventListener('click', () => {
      if (!currentCaregiver) return;

      // Update print subtitle with patient name and date range
      const printSub = document.getElementById('print-report-subtitle');
      if (printSub) {
        const now = new Date();
        const thirtyDaysAgo = new Date(now - 30 * 24 * 60 * 60 * 1000);
        printSub.textContent = `Patient: ${currentCaregiver.patient_name} | Period: ${thirtyDaysAgo.toLocaleDateString()} — ${now.toLocaleDateString()} | Caregiver: ${currentCaregiver.caregiver_name}`;
      }

      window.print();
    });
  }

  // =============================================
  // RAZORPAY SUBSCRIPTION
  // =============================================

  if (btnSubscribe) {
    btnSubscribe.addEventListener('click', async () => {
      if (!currentCaregiver) return;

      try {
        const orderRes = await fetch('/subscriptions/create-order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ caregiver_id: currentCaregiver.id })
        });

        if (!orderRes.ok) throw new Error('Failed to create order');
        const order = await orderRes.json();

        const options = {
          key: order.razorpay_key_id,
          amount: order.amount,
          currency: 'INR',
          name: 'MedAssist AI',
          description: 'Premium Subscription — 30 Days',
          order_id: order.razorpay_order_id,
          handler: async function (response) {
            const verifyRes = await fetch('/subscriptions/verify', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                caregiver_id: currentCaregiver.id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature
              })
            });

            if (verifyRes.ok) {
              currentCaregiver.is_premium = true;
              localStorage.setItem('medassist_caregiver', JSON.stringify(currentCaregiver));
              updateSubscriptionBanner();
              alert('🎉 Payment successful! You now have premium access for 30 days.');
            } else {
              alert('Payment verification failed. Please contact support.');
            }
          },
          prefill: {
            contact: currentCaregiver.caregiver_phone
          },
          theme: { color: '#6366f1' }
        };

        const rzp = new Razorpay(options);
        rzp.open();
      } catch (err) {
        alert('Error: ' + err.message);
      }
    });
  }

  // =============================================
  // UTILITY FUNCTIONS
  // =============================================

  function formatTime(timeStr) {
    if (!timeStr) return '—';
    const [h, m] = timeStr.split(':');
    const hour = parseInt(h, 10);

    if (use24hr) {
      return `${h.padStart(2, '0')}:${m}`;
    }

    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${m} ${ampm}`;
  }

  function formatTimestamp(ts) {
    const d = new Date(ts);
    const day = d.getDate().toString().padStart(2, '0');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const month = months[d.getMonth()];
    const time = formatTime(`${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`);
    return `${day} ${month} ${time}`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // === Boot ===
  initApp();
});

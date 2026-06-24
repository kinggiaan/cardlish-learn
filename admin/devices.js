/* ═══════════════════════════════════════════════════════════
   Cardlish Device Manager — Admin UI Logic
   ═══════════════════════════════════════════════════════════ */

const API_BASE = window.CARDLISH_API_BASE || '';

// ── State ────────────────────────────────────────────────
const state = {
    masterKey: sessionStorage.getItem('cardlish_master_key') || '',
    devices: [],
    revokeTarget: null, // { key, name }
};

// ── DOM Cache ────────────────────────────────────────────
const dom = {};
function cacheDom() {
    dom.loginSection = document.getElementById('login-section');
    dom.devicesSection = document.getElementById('devices-section');
    dom.loginForm = document.getElementById('login-form');
    dom.masterKeyInput = document.getElementById('master-key-input');
    dom.loginError = document.getElementById('login-error');
    dom.btnLogout = document.getElementById('btn-logout');
    dom.btnAddDevice = document.getElementById('btn-add-device');
    dom.devicesLoading = document.getElementById('devices-loading');
    dom.devicesContent = document.getElementById('devices-content');
    dom.listError = document.getElementById('list-error');

    // Add device modal
    dom.modalAddDevice = document.getElementById('modal-add-device');
    dom.deviceNameInput = document.getElementById('device-name-input');
    dom.addDeviceError = document.getElementById('add-device-error');
    dom.btnCancelAdd = document.getElementById('btn-cancel-add');
    dom.btnConfirmAdd = document.getElementById('btn-confirm-add');

    // Key created modal
    dom.modalKeyCreated = document.getElementById('modal-key-created');
    dom.createdKeyValue = document.getElementById('created-key-value');
    dom.btnCopyKey = document.getElementById('btn-copy-key');
    dom.btnCloseKeyModal = document.getElementById('btn-close-key-modal');

    // Revoke modal
    dom.modalConfirmRevoke = document.getElementById('modal-confirm-revoke');
    dom.revokeDeviceName = document.getElementById('revoke-device-name');
    dom.revokeError = document.getElementById('revoke-error');
    dom.btnCancelRevoke = document.getElementById('btn-cancel-revoke');
    dom.btnConfirmRevoke = document.getElementById('btn-confirm-revoke');

    dom.toastContainer = document.getElementById('toast-container');
}

// ── API Helpers ──────────────────────────────────────────
async function apiFetch(method, path, body = null) {
    const url = `${API_BASE}${path}`;
    const headers = {
        'Authorization': `Bearer ${state.masterKey}`,
    };
    if (body) {
        headers['Content-Type'] = 'application/json';
    }
    const opts = { method, headers };
    if (body) {
        opts.body = JSON.stringify(body);
    }

    let res;
    try {
        res = await fetch(url, opts);
    } catch (err) {
        throw new Error('Không thể kết nối đến server. Kiểm tra lại kết nối mạng.');
    }

    if (res.status === 401 || res.status === 403) {
        // Auth failure — clear stored key and force re-login
        sessionStorage.removeItem('cardlish_master_key');
        state.masterKey = '';
        showLogin();
        throw new Error('Master key không hợp lệ hoặc đã hết hạn.');
    }

    if (!res.ok) {
        let msg = `Lỗi server (${res.status})`;
        try {
            const data = await res.json();
            if (data.error) msg = data.error;
        } catch (_) {}
        throw new Error(msg);
    }

    // 204 No Content
    if (res.status === 204) return null;

    return res.json();
}

// ── UI Transitions ───────────────────────────────────────
function showLogin() {
    dom.loginSection.style.display = '';
    dom.devicesSection.style.display = 'none';
    dom.btnLogout.style.display = 'none';
    dom.masterKeyInput.value = '';
    dom.masterKeyInput.focus();
}

function showDevices() {
    dom.loginSection.style.display = 'none';
    dom.devicesSection.style.display = '';
    dom.btnLogout.style.display = '';
}

function showError(el, msg) {
    el.textContent = msg;
    el.classList.add('visible');
    el.style.display = 'block';
}

function hideError(el) {
    el.classList.remove('visible');
    el.style.display = 'none';
}

function showModal(el) {
    el.classList.add('visible');
}

function hideModal(el) {
    el.classList.remove('visible');
}

// ── Toast ────────────────────────────────────────────────
function toast(message, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    dom.toastContainer.appendChild(el);
    setTimeout(() => {
        el.classList.add('toast-out');
        el.addEventListener('animationend', () => el.remove());
    }, 3500);
}

// ── Date Formatting ──────────────────────────────────────
function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return '—';
        return d.toLocaleDateString('vi-VN', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return '—';
    }
}

function maskKey(key) {
    if (!key || key.length < 12) return key || '';
    // dk_a1b2...g7h8
    return key.slice(0, 7) + '...' + key.slice(-4);
}

// ── Load Devices ─────────────────────────────────────────
async function loadDevices() {
    dom.devicesLoading.classList.add('visible');
    hideError(dom.listError);
    dom.devicesContent.innerHTML = '';

    try {
        const data = await apiFetch('GET', '/api/admin/devices');
        state.devices = data.devices || data || [];
        renderDevices();
    } catch (err) {
        showError(dom.listError, err.message);
    } finally {
        dom.devicesLoading.classList.remove('visible');
    }
}

function renderDevices() {
    if (state.devices.length === 0) {
        dom.devicesContent.innerHTML = `
            <div class="empty-devices">
                <div class="empty-icon">📱</div>
                <p>Chưa có thiết bị nào được đăng ký</p>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-top:8px;">
                    Nhấn "Thêm thiết bị" để tạo API key mới
                </p>
            </div>
        `;
        return;
    }

    const rows = state.devices.map(d => {
        const isBlocked = d.status === 'blocked';
        const statusBadge = isBlocked
            ? '<span style="color:#ef4444;font-weight:600;">🔴 Chặn</span>'
            : '<span style="color:#22c55e;font-weight:600;">🟢 Active</span>';
        const regType = d.registeredBy === 'self' ? '📱 Tự đăng ký' : '👤 Admin tạo';
        const ipInfo = d.ip ? `<span style="font-size:0.75rem;color:var(--text-muted);">${escapeHtml(d.ip)}</span>` : '';
        const blockBtnText = isBlocked ? '🔓 Bỏ chặn' : '🔒 Chặn';
        const blockBtnClass = isBlocked ? 'btn-unblock' : 'btn-block';

        return `
        <tr style="${isBlocked ? 'opacity: 0.6;' : ''}">
            <td><strong>${escapeHtml(d.name || 'Không tên')}</strong><br>${ipInfo}</td>
            <td><code class="device-key">${escapeHtml(maskKey(d.key))}</code></td>
            <td>${statusBadge}</td>
            <td>${regType}</td>
            <td class="device-date">${formatDate(d.lastUsed || d.last_used)}</td>
            <td class="device-date">${formatDate(d.createdAt || d.created_at)}</td>
            <td>
                <button class="${blockBtnClass}" data-key="${escapeHtml(d.key)}" data-status="${isBlocked ? 'active' : 'blocked'}" style="margin-right:4px;padding:4px 8px;border:none;border-radius:4px;cursor:pointer;font-size:0.8rem;background:${isBlocked ? '#3b82f6' : '#f59e0b'};color:white;">
                    ${blockBtnText}
                </button>
                <button class="btn-revoke" data-key="${escapeHtml(d.key)}" data-name="${escapeHtml(d.name || 'Không tên')}">
                    🗑️ Xóa
                </button>
            </td>
        </tr>`;
    }).join('');

    dom.devicesContent.innerHTML = `
        <div class="device-count">${state.devices.length} thiết bị</div>
        <table class="device-table">
            <thead>
                <tr>
                    <th>Tên thiết bị</th>
                    <th>API Key</th>
                    <th>Trạng thái</th>
                    <th>Đăng ký</th>
                    <th>Lần dùng cuối</th>
                    <th>Ngày tạo</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;

    // Attach block/unblock handlers
    dom.devicesContent.querySelectorAll('.btn-block, .btn-unblock').forEach(btn => {
        btn.addEventListener('click', () => {
            toggleBlock(btn.dataset.key, btn.dataset.status);
        });
    });

    // Attach revoke handlers
    dom.devicesContent.querySelectorAll('.btn-revoke').forEach(btn => {
        btn.addEventListener('click', () => {
            state.revokeTarget = {
                key: btn.dataset.key,
                name: btn.dataset.name,
            };
            dom.revokeDeviceName.textContent = btn.dataset.name;
            hideError(dom.revokeError);
            showModal(dom.modalConfirmRevoke);
        });
    });
}

// ── Add Device ───────────────────────────────────────────
async function addDevice(name) {
    dom.btnConfirmAdd.disabled = true;
    dom.btnConfirmAdd.textContent = 'Đang tạo...';
    hideError(dom.addDeviceError);

    try {
        const data = await apiFetch('POST', '/api/admin/devices', { name });
        hideModal(dom.modalAddDevice);

        // Show the created key
        dom.createdKeyValue.textContent = data.key;
        showModal(dom.modalKeyCreated);

        // Refresh device list
        await loadDevices();
        toast(`Đã tạo thiết bị "${name}"`, 'success');
    } catch (err) {
        showError(dom.addDeviceError, err.message);
    } finally {
        dom.btnConfirmAdd.disabled = false;
        dom.btnConfirmAdd.textContent = 'Tạo thiết bị';
    }
}

// ── Revoke Device ────────────────────────────────────────
async function revokeDevice(key) {
    dom.btnConfirmRevoke.disabled = true;
    dom.btnConfirmRevoke.textContent = 'Đang thu hồi...';
    hideError(dom.revokeError);

    try {
        await apiFetch('DELETE', `/api/admin/devices/${encodeURIComponent(key)}`);
        hideModal(dom.modalConfirmRevoke);
        await loadDevices();
        toast(`Đã thu hồi thiết bị "${state.revokeTarget?.name || ''}"`, 'success');
        state.revokeTarget = null;
    } catch (err) {
        showError(dom.revokeError, err.message);
    } finally {
        dom.btnConfirmRevoke.disabled = false;
        dom.btnConfirmRevoke.textContent = 'Thu hồi';
    }
}

// ── Toggle Block/Unblock ─────────────────────────────────
async function toggleBlock(key, newStatus) {
    try {
        await apiFetch('PATCH', `/api/admin/devices/${encodeURIComponent(key)}`, { status: newStatus });
        await loadDevices();
        const action = newStatus === 'blocked' ? 'Đã chặn' : 'Đã bỏ chặn';
        toast(`${action} thiết bị`, 'success');
    } catch (err) {
        toast(`Lỗi: ${err.message}`, 'error');
    }
}

// ── Login ────────────────────────────────────────────────
async function login(key) {
    state.masterKey = key;
    hideError(dom.loginError);

    try {
        // Validate the key by attempting to list devices
        await apiFetch('GET', '/api/admin/devices');
        sessionStorage.setItem('cardlish_master_key', key);
        showDevices();
        await loadDevices();
    } catch (err) {
        state.masterKey = '';
        sessionStorage.removeItem('cardlish_master_key');
        showError(dom.loginError, err.message);
    }
}

function logout() {
    state.masterKey = '';
    sessionStorage.removeItem('cardlish_master_key');
    state.devices = [];
    showLogin();
    toast('Đã đăng xuất', 'info');
}

// ── Escape HTML ──────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Event Binding ────────────────────────────────────────
function bindEvents() {
    // Login
    dom.loginForm.addEventListener('submit', e => {
        e.preventDefault();
        const key = dom.masterKeyInput.value.trim();
        if (!key) return;
        login(key);
    });

    // Logout
    dom.btnLogout.addEventListener('click', logout);

    // Add device — open modal
    dom.btnAddDevice.addEventListener('click', () => {
        dom.deviceNameInput.value = '';
        hideError(dom.addDeviceError);
        showModal(dom.modalAddDevice);
        setTimeout(() => dom.deviceNameInput.focus(), 100);
    });

    // Add device — cancel
    dom.btnCancelAdd.addEventListener('click', () => {
        hideModal(dom.modalAddDevice);
    });

    // Add device — confirm
    dom.btnConfirmAdd.addEventListener('click', () => {
        const name = dom.deviceNameInput.value.trim();
        if (!name) {
            showError(dom.addDeviceError, 'Vui lòng nhập tên thiết bị.');
            return;
        }
        addDevice(name);
    });

    // Add device — enter key
    dom.deviceNameInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            dom.btnConfirmAdd.click();
        }
    });

    // Key created — copy
    dom.btnCopyKey.addEventListener('click', async () => {
        const key = dom.createdKeyValue.textContent;
        try {
            await navigator.clipboard.writeText(key);
            dom.btnCopyKey.textContent = '✅ Đã copy!';
            setTimeout(() => { dom.btnCopyKey.textContent = '📋 Copy key'; }, 2000);
        } catch {
            // Fallback: select text
            const range = document.createRange();
            range.selectNodeContents(dom.createdKeyValue);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            toast('Không thể tự động copy. Hãy nhấn Ctrl+C.', 'info');
        }
    });

    // Key created — close
    dom.btnCloseKeyModal.addEventListener('click', () => {
        hideModal(dom.modalKeyCreated);
    });

    // Revoke — cancel
    dom.btnCancelRevoke.addEventListener('click', () => {
        hideModal(dom.modalConfirmRevoke);
        state.revokeTarget = null;
    });

    // Revoke — confirm
    dom.btnConfirmRevoke.addEventListener('click', () => {
        if (state.revokeTarget) {
            revokeDevice(state.revokeTarget.key);
        }
    });

    // Close modals on overlay click
    [dom.modalAddDevice, dom.modalConfirmRevoke, dom.modalKeyCreated].forEach(modal => {
        modal.addEventListener('click', e => {
            if (e.target === modal) {
                hideModal(modal);
            }
        });
    });

    // Close modals on Escape
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            hideModal(dom.modalAddDevice);
            hideModal(dom.modalConfirmRevoke);
            hideModal(dom.modalKeyCreated);
        }
    });
}

// ── Init ─────────────────────────────────────────────────
function init() {
    cacheDom();
    bindEvents();

    // Auto-login if key was stored in sessionStorage
    if (state.masterKey) {
        showDevices();
        loadDevices();
    } else {
        showLogin();
    }
}

document.addEventListener('DOMContentLoaded', init);

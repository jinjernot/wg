// ===========================
// Toast Notification System
// ===========================
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || icons.info}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===========================
// Release Confirmation Modal
// ===========================
function showReleaseModal({ tradeHash, accountName, buyer, amount, hasAttachment }) {
    return new Promise((resolve) => {
        const existing = document.getElementById('release-modal-overlay');
        if (existing) existing.remove();

        const noProof = !hasAttachment;
        const overlay = document.createElement('div');
        overlay.id = 'release-modal-overlay';
        overlay.innerHTML = `
            <div class="release-modal">
                <div class="release-modal-header ${noProof ? 'danger' : ''}">
                    <span class="release-modal-icon">${noProof ? '⚠️' : '🔒'}</span>
                    <h3>${noProof ? 'WARNING — No Proof Uploaded' : 'Confirm Trade Release'}</h3>
                </div>
                <div class="release-modal-body">
                    <div class="release-modal-row"><span>Trade</span><code>${tradeHash}</code></div>
                    <div class="release-modal-row"><span>Buyer</span><strong>${buyer || 'N/A'}</strong></div>
                    <div class="release-modal-row"><span>Amount</span><strong>${amount || 'N/A'}</strong></div>
                    ${noProof
                        ? `<p class="release-modal-warning">🚨 No receipt has been uploaded. Are you sure you want to release without verifying proof of payment?</p>`
                        : `<p class="release-modal-ok">✅ Receipt uploaded. Confirm release below.</p>`
                    }
                </div>
                <div class="release-modal-footer">
                    <button class="release-modal-cancel">Cancel</button>
                    <button class="release-modal-confirm ${noProof ? 'danger' : ''}">Confirm Release</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        overlay.querySelector('.release-modal-cancel').addEventListener('click', () => {
            overlay.remove();
            resolve(false);
        });
        overlay.querySelector('.release-modal-confirm').addEventListener('click', () => {
            overlay.remove();
            resolve(true);
        });
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) { overlay.remove(); resolve(false); }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const tradesContainer = document.getElementById('active-trades-container');
    const saveAllBtn = document.getElementById('save-all-btn');
    const offersCheckbox = document.getElementById('offers-checkbox');
    const settingToggles = document.querySelectorAll('.setting-toggle');
    const offersContainer = document.getElementById('offers-container');
    const generateChartsBtn = document.getElementById('generate-charts-btn');
    const generateMarketReportBtn = document.getElementById('generate-market-report-btn');
    const balancesContainer = document.getElementById('wallet-balances-container');
    const toggleOffersBtn = document.getElementById('toggle-offers-visibility-btn');

    // --- Offers panel: persist visibility in localStorage ---
    const OFFERS_VISIBLE_KEY = 'offersVisible';
    if (offersContainer) {
        const savedVisible = localStorage.getItem(OFFERS_VISIBLE_KEY) === 'true';
        offersContainer.style.display = savedVisible ? 'block' : 'none';
        if (toggleOffersBtn) toggleOffersBtn.textContent = savedVisible ? 'Hide' : 'Show All';
    }

    // --- Event Listeners ---
    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            startBtn.classList.add('loading');
            const response = await fetch('/start_trading', { method: 'POST' });
            const result = await response.json();
            startBtn.classList.remove('loading');
            showToast('Bot Started', result.message, result.success ? 'success' : 'error');
            updateStatus();
            setLastAction('Bot Started');
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', async () => {
            stopBtn.classList.add('loading');
            const response = await fetch('/stop_trading', { method: 'POST' });
            const result = await response.json();
            stopBtn.classList.remove('loading');
            showToast('Bot Stopped', result.message, result.success ? 'success' : 'error');
            updateStatus();
            setLastAction('Bot Stopped');
        });
    }

    if (generateChartsBtn) {
        generateChartsBtn.addEventListener('click', async () => {
            generateChartsBtn.disabled = true;
            generateChartsBtn.textContent = 'Generating...';
            try {
                const response = await fetch('/generate_charts', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    showToast('Reports Generated', 'Reports saved successfully on the server.', 'success');
                } else {
                    showToast('Error', result.error || 'Unknown error generating reports.', 'error');
                }
            } catch (error) {
                console.error('Failed to generate reports:', error);
                showToast('Error', 'An unexpected error occurred while generating reports.', 'error');
            } finally {
                generateChartsBtn.disabled = false;
                generateChartsBtn.textContent = '📊 Reports';
            }
        });
    }

    // Generate Client Profitability Report Button
    const generateClientReportBtn = document.getElementById('generate-client-report-btn');
    if (generateClientReportBtn) {
        generateClientReportBtn.addEventListener('click', async () => {
            generateClientReportBtn.disabled = true;
            generateClientReportBtn.textContent = 'Generating...';
            try {
                const response = await fetch('/generate_client_report', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    showToast('Report Ready', 'Client Profitability Report generated.', 'success');
                    const link = document.createElement('a');
                    link.href = `/charts/${result.filename}`;
                    link.setAttribute('download', result.filename);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    showToast('Error', result.error || 'Unknown error generating report.', 'error');
                }
            } catch (error) {
                console.error('Failed to generate client profitability report:', error);
                showToast('Error', 'An unexpected error occurred.', 'error');
            } finally {
                generateClientReportBtn.disabled = false;
                generateClientReportBtn.textContent = 'Download Client Profitability Report';
            }
        });
    }

    if (generateMarketReportBtn) {
        generateMarketReportBtn.addEventListener('click', async () => {
            generateMarketReportBtn.disabled = true;
            generateMarketReportBtn.textContent = 'Generating... (this may take a minute)';
            try {
                const response = await fetch('/generate_market_report', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    showToast('Report Ready', 'MXN Market Report generated. Downloading now.', 'success');
                    const link = document.createElement('a');
                    link.href = `/charts/${result.filename}`;
                    link.setAttribute('download', result.filename);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    showToast('Error', result.error || 'Unknown error generating report.', 'error');
                }
            } catch (error) {
                console.error('Failed to generate market report:', error);
                showToast('Error', 'An unexpected error occurred.', 'error');
            } finally {
                generateMarketReportBtn.disabled = false;
                generateMarketReportBtn.textContent = '📈 MXN Market Report';
            }
        });
    }

    if (toggleOffersBtn) {
        toggleOffersBtn.addEventListener('click', () => {
            const isHidden = offersContainer.style.display === 'none';
            offersContainer.style.display = isHidden ? 'block' : 'none';
            toggleOffersBtn.textContent = isHidden ? 'Hide' : 'Show All';
            localStorage.setItem(OFFERS_VISIBLE_KEY, isHidden ? 'true' : 'false');
        });
    }

    // Helper to save a setting to the server
    async function saveSetting(key, isEnabled) {
        const response = await fetch('/update_setting', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: key, enabled: isEnabled })
        });
        return response.json();
    }

    // Keys that are mutually exclusive (only one can be on at a time)
    const exclusiveKeys = ['night_mode_enabled', 'afk_mode_enabled'];

    // Consolidated handler for all settings toggles
    settingToggles.forEach(toggle => {
        toggle.addEventListener('change', async () => {
            const key = toggle.dataset.key;
            const isEnabled = toggle.checked;
            try {
                const result = await saveSetting(key, isEnabled);
                if (!result.success) {
                    showToast('Error', result.error, 'error');
                    toggle.checked = !isEnabled;
                    return;
                }

                if (isEnabled && exclusiveKeys.includes(key)) {
                    for (const otherKey of exclusiveKeys) {
                        if (otherKey === key) continue;
                        const otherToggle = document.querySelector(`.setting-toggle[data-key="${otherKey}"]`);
                        if (otherToggle && otherToggle.checked) {
                            otherToggle.checked = false;
                            const otherResult = await saveSetting(otherKey, false);
                            if (!otherResult.success) {
                                console.error(`Failed to disable ${otherKey}: ${otherResult.error}`);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error(`Failed to update setting ${key}:`, error);
                showToast('Error', 'An unexpected error occurred.', 'error');
                toggle.checked = !isEnabled;
            }
        });
    });

    // Specific handler for the main offers toggle
    if (offersCheckbox) {
        offersCheckbox.addEventListener('change', async () => {
            const isEnabled = offersCheckbox.checked;
            try {
                const response = await fetch('/offer/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: isEnabled })
                });
                const result = await response.json();
                if (!result.success) {
                    showToast('Error', result.message, 'error');
                    offersCheckbox.checked = !isEnabled;
                } else {
                    showToast('Offers Updated', result.message, 'success');
                    fetchOffers();
                }
            } catch (error) {
                console.error('Failed to update offers status:', error);
                showToast('Error', 'An unexpected error occurred.', 'error');
                offersCheckbox.checked = !isEnabled;
            }
        });
    }

    if (saveAllBtn) {
        saveAllBtn.addEventListener('click', async () => {
            const forms = document.querySelectorAll('.account-form');
            const selections = [];
            forms.forEach(form => {
                const formData = new FormData(form);
                selections.push({
                    filename: formData.get('filename'),
                    owner_username: formData.get('owner_username'),
                    payment_method: formData.get('payment_method'),
                    selected_id: formData.get('selected_id')
                });
            });
            try {
                const response = await fetch('/update_all_selections', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(selections)
                });
                const result = await response.json();
                if (result.success) {
                    showToast('Saved', 'All account selections saved successfully.', 'success');
                } else {
                    showToast('Error', result.error, 'error');
                }
            } catch (error) {
                console.error('Failed to save all selections:', error);
                showToast('Error', 'An unexpected error occurred while saving selections.', 'error');
            }
        });
    }

    if (tradesContainer) {
        tradesContainer.addEventListener('click', async (event) => {
            // --- Send Manual Message ---
            if (event.target.classList.contains('send-manual-message-btn')) {
                const button = event.target;
                const tradeHash = button.dataset.tradeHash;
                const accountName = button.dataset.accountName;
                const input = button.previousElementSibling;
                const message = input.value.trim();

                if (!message) {
                    showToast('Missing Message', 'Please type a message to send.', 'warning');
                    return;
                }

                button.disabled = true;
                button.textContent = '...';

                try {
                    const response = await fetch('/send_manual_message', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ trade_hash: tradeHash, account_name: accountName, message })
                    });
                    const result = await response.json();
                    if (result.success) {
                        showToast('Message Sent', result.message, 'success');
                        input.value = '';
                    } else {
                        showToast('Error', result.error, 'error');
                    }
                } catch (error) {
                    console.error('Failed to send manual message:', error);
                    showToast('Error', 'An unexpected error occurred.', 'error');
                } finally {
                    button.disabled = false;
                    button.textContent = 'Send';
                }
            }

            // --- Release Trade (styled modal) ---
            if (event.target.classList.contains('release-trade-btn')) {
                const button = event.target;
                const tradeHash = button.dataset.tradeHash;
                const accountName = button.dataset.accountName;
                const buyer = button.dataset.buyer;
                const amount = button.dataset.amount;
                const hasAttachment = button.dataset.hasAttachment === 'true';

                const confirmed = await showReleaseModal({ tradeHash, accountName, buyer, amount, hasAttachment });
                if (!confirmed) return;

                button.disabled = true;
                button.textContent = '...';

                try {
                    const response = await fetch('/release_trade', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ trade_hash: tradeHash, account_name: accountName })
                    });
                    const result = await response.json();
                    if (result.success) {
                        showToast('Released', result.message, 'success');
                        fetchActiveTrades();
                    } else {
                        showToast('Error', result.error, 'error');
                    }
                } catch (error) {
                    console.error('Failed to release trade:', error);
                    showToast('Error', 'An unexpected error occurred.', 'error');
                } finally {
                    button.disabled = false;
                    button.textContent = 'Release';
                }
            }
        });
    }

    if (offersContainer) {
        offersContainer.addEventListener('change', async (event) => {
            if (event.target.classList.contains('offer-toggle-checkbox')) {
                const checkbox = event.target;
                const offerHash = checkbox.dataset.offerHash;
                const accountName = checkbox.dataset.accountName;
                const isEnabled = checkbox.checked;
                const statusCell = checkbox.closest('tr').querySelector('.status-indicator');

                checkbox.disabled = true;
                try {
                    const response = await fetch('/offer/toggle_single', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ offer_hash: offerHash, account_name: accountName, enabled: isEnabled })
                    });
                    const result = await response.json();
                    if (!result.success) {
                        showToast('Error', result.error, 'error');
                        checkbox.checked = !isEnabled;
                    } else {
                        statusCell.textContent = isEnabled ? 'Enabled' : 'Disabled';
                        statusCell.className = `status-indicator ${isEnabled ? 'running' : 'stopped'}`;
                    }
                } catch (error) {
                    console.error('Failed to toggle offer:', error);
                    showToast('Error', 'An unexpected error occurred.', 'error');
                    checkbox.checked = !isEnabled;
                } finally {
                    checkbox.disabled = false;
                }
            }
        });
    }

    // --- Last-action tracker ---
    function setLastAction(label) {
        const el = document.getElementById('hero-last-action');
        if (!el) return;
        const t = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        el.textContent = `${label} at ${t}`;
    }

    // --- KPI Strip ---
    function updateKpiStrip(trades) {
        if (!trades) return;
        const active   = trades.filter(t => t.trade_status !== 'Paid' && t.trade_status !== 'Dispute open').length;
        const paid     = trades.filter(t => t.trade_status === 'Paid').length;
        const noRcpt   = trades.filter(t => t.trade_status === 'Paid' && !t.has_attachment).length;
        const disputed = trades.filter(t => t.trade_status === 'Dispute open').length;
        const exposure = trades.reduce((s, t) => {
            const a = parseFloat(t.fiat_amount_requested);
            return (t.fiat_currency_code || '').toUpperCase() === 'MXN' && !isNaN(a) ? s + a : s;
        }, 0);
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set('kpi-active',    active);
        set('kpi-paid',      paid);
        set('kpi-noreceipt', noRcpt);
        set('kpi-disputed',  disputed);
        set('kpi-exposure',  exposure > 0 ? '$' + exposure.toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' MXN' : '$0');
        // Trades summary pill
        const pill = document.getElementById('dash-trades-pill');
        if (pill) {
            pill.textContent = `${trades.length} trade${trades.length !== 1 ? 's' : ''} live`;
            pill.style.display = trades.length > 0 ? 'inline-block' : 'none';
        }
    }

    // --- Data Fetching and UI Update Functions ---
    async function updateStatus() {
        try {
            const response = await fetch('/trading_status');
            const result = await response.json();
            if (statusIndicator) {
                statusIndicator.textContent = result.status;
                statusIndicator.className = result.status.toLowerCase();
            }
        } catch (error) {
            if (statusIndicator) {
                statusIndicator.textContent = 'Error';
                statusIndicator.className = 'error';
            }
        }
    }

    // "Last updated" counter
    let lastTradesFetchTime = null;
    let lastUpdatedInterval = null;

    function startLastUpdatedCounter(labelEl) {
        if (lastUpdatedInterval) clearInterval(lastUpdatedInterval);
        lastTradesFetchTime = Date.now();
        lastUpdatedInterval = setInterval(() => {
            if (!lastTradesFetchTime) return;
            const secs = Math.floor((Date.now() - lastTradesFetchTime) / 1000);
            let text = secs < 60 ? `${secs}s ago` : `${Math.floor(secs / 60)}m ${secs % 60}s ago`;
            if (labelEl) labelEl.textContent = `Last updated: ${text}`;
        }, 1000);
    }

    async function fetchActiveTrades() {
        try {
            const response = await fetch('/get_active_trades');
            const trades = await response.json();
            updateTradesTable(trades);
        } catch (error) {
            if (tradesContainer) {
                tradesContainer.innerHTML = '<p>Error fetching active trades.</p>';
            }
            console.error(error);
        }
    }

    function updateTradesTable(trades) {
        if (!tradesContainer) return;
        updateKpiStrip(trades);
        tradesContainer.innerHTML = '';

        if (!trades || trades.length === 0) {
            tradesContainer.innerHTML = '<p>No active trades found.</p>';
            return;
        }

        // Header with "last updated" counter
        const headerRow = document.createElement('div');
        headerRow.className = 'trades-table-header';
        const lastUpdatedEl = document.createElement('span');
        lastUpdatedEl.className = 'trades-last-updated';
        lastUpdatedEl.textContent = 'Last updated: just now';
        headerRow.appendChild(lastUpdatedEl);
        tradesContainer.appendChild(headerRow);
        startLastUpdatedCounter(lastUpdatedEl);

        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Account</th>
                    <th>Trade Hash</th>
                    <th>Buyer</th>
                    <th>Amount</th>
                    <th>Payment Method</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tbody = table.querySelector('tbody');

        trades.forEach(trade => {
            const row = document.createElement('tr');

            const isNewTrade = () => {
                if (trade.started_at) {
                    const diffMinutes = (new Date() - new Date(trade.started_at)) / (1000 * 60);
                    return diffMinutes <= 30;
                }
                return false;
            };

            const isOldPaidTrade = () => {
                if (trade.trade_status === 'Paid' && trade.started_at) {
                    const diffHours = (new Date() - new Date(trade.started_at)) / (1000 * 60 * 60);
                    return diffHours > 3;
                }
                return false;
            };

            // Status cell with optional "No Receipt" badge
            const noReceipt = trade.trade_status === 'Paid' && !trade.has_attachment;
            const statusBadge = noReceipt
                ? `${trade.trade_status || 'N/A'} <span class="no-receipt-badge">⚠️ No Receipt</span>`
                : (trade.trade_status || 'N/A');

            const amountStr = `${trade.fiat_amount_requested || 'N/A'} ${trade.fiat_currency_code || ''}`.trim();

            row.innerHTML = `
                <td>${trade.account_name_source || 'N/A'}</td>
                <td>${trade.trade_hash || 'N/A'}</td>
                <td>${trade.responder_username || 'N/A'}</td>
                <td>${amountStr}</td>
                <td>${trade.payment_method_name || 'N/A'}</td>
                <td>${statusBadge}</td>
                <td class="message-cell">
                    <input type="text" class="manual-message-input" placeholder="Type a message...">
                    <button class="send-manual-message-btn"
                        data-trade-hash="${trade.trade_hash}"
                        data-account-name="${trade.account_name_source}">Send</button>
                    <button class="release-trade-btn"
                        data-trade-hash="${trade.trade_hash}"
                        data-account-name="${trade.account_name_source}"
                        data-buyer="${trade.responder_username || ''}"
                        data-amount="${amountStr}"
                        data-has-attachment="${trade.has_attachment ? 'true' : 'false'}">Release</button>
                </td>
            `;

            // Row colour coding
            if (isNewTrade() && trade.trade_status !== 'Paid' && trade.trade_status !== 'Dispute open') {
                row.classList.add('status-new');
            } else if (noReceipt) {
                row.classList.add('status-paid-no-attachment');
            } else if (trade.trade_status === 'Paid' && trade.has_attachment && isOldPaidTrade()) {
                row.classList.add('status-paid-old');
            } else if (trade.trade_status === 'Paid') {
                row.classList.add('status-paid');
            } else if (trade.trade_status === 'Dispute open') {
                row.classList.add('status-disputed');
            }

            // High-value highlight
            const amount = parseFloat(trade.fiat_amount_requested);
            if (!isNaN(amount) && amount > 3000 && (trade.fiat_currency_code || '').toUpperCase() === 'MXN') {
                row.classList.add('high-value');
            }

            tbody.appendChild(row);
        });

        tradesContainer.appendChild(table);
    }

    async function fetchOffers() {
        if (!offersContainer) return;
        try {
            const response = await fetch('/get_offers');
            const offers = await response.json();
            updateOffersTable(offers);
        } catch (error) {
            offersContainer.innerHTML = '<p>Error fetching offers.</p>';
            console.error(error);
        }
    }

    function updateOffersTable(offers) {
        if (!offersContainer) return;
        offersContainer.innerHTML = '';
        if (!offers || offers.length === 0) {
            offersContainer.innerHTML = '<p>No offers found.</p>';
            return;
        }

        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Account</th>
                    <th>Payment Method</th>
                    <th>Margin</th>
                    <th>Range</th>
                    <th>Status</th>
                    <th>Enable/Disable</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tbody = table.querySelector('tbody');
        offers.forEach(offer => {
            const isEnabled = offer.enabled;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${offer.account_name || 'N/A'}</td>
                <td>${offer.payment_method_name || 'N/A'}</td>
                <td>${offer.margin || 'N/A'}%</td>
                <td>${offer.fiat_amount_range_min || 'N/A'} - ${offer.fiat_amount_range_max || 'N/A'} ${offer.fiat_currency_code || ''}</td>
                <td><span class="status-indicator ${isEnabled ? 'running' : 'stopped'}">${isEnabled ? 'Enabled' : 'Disabled'}</span></td>
                <td>
                    <label class="switch">
                        <input type="checkbox"
                               class="offer-toggle-checkbox"
                               data-offer-hash="${offer.offer_hash}"
                               data-account-name="${offer.account_name}"
                               ${isEnabled ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                </td>
            `;
            tbody.appendChild(row);
        });
        offersContainer.appendChild(table);
    }

    // --- Wallet Balances (dynamic — no hardcoded account names) ---
    async function fetchWalletBalances() {
        if (!balancesContainer) return;
        try {
            const response = await fetch('/get_wallet_balances');
            const balances = await response.json();
            updateBalancesDashboard(balances);
        } catch (error) {
            balancesContainer.innerHTML = '<p style="color: #e53e3e;">Error fetching wallet balances.</p>';
            console.error('Failed to fetch wallet balances:', error);
        }
    }

    const FUND_METER_MAX = 60000;
    const FUND_METER_ALERT = 10000;

    function buildFundMeter(amount) {
        const pct = Math.min(amount / FUND_METER_MAX, 1) * 100;
        const alertPct = (FUND_METER_ALERT / FUND_METER_MAX) * 100;

        let zone = 'zone-ok';
        if (amount < FUND_METER_ALERT) zone = 'zone-danger';
        else if (amount < FUND_METER_MAX / 2) zone = 'zone-warning';

        const formatted = amount >= 1000
            ? `${(amount / 1000).toFixed(1)}K`
            : amount.toFixed(0);

        return `
            <div class="fund-meter-wrap">
                <div class="fund-meter-track">
                    <div class="fund-meter-fill ${zone}" style="width:${pct.toFixed(2)}%"></div>
                </div>
                <div class="fund-meter-marker" style="left:${alertPct.toFixed(2)}%" data-label="10K ⚠️"></div>
            </div>
            <div class="fund-meter-labels">
                <span>$0</span>
                <span style="color:${zone === 'zone-danger' ? 'var(--red)' : zone === 'zone-warning' ? 'var(--amber)' : 'var(--green)'}">
                    $${formatted} MXN &nbsp;·&nbsp; ${pct.toFixed(1)}%
                </span>
                <span>$60K</span>
            </div>
        `;
    }

    function updateBalancesDashboard(balances) {
        const davidContainer = document.getElementById('david-balances-col');
        const joeContainer = document.getElementById('joe-balances-col');
        if (!davidContainer || !joeContainer) return;

        davidContainer.innerHTML = '';
        joeContainer.innerHTML = '';

        const accounts = Object.keys(balances).filter(
            name => !name.toLowerCase().includes('paxful')
        );

        if (accounts.length === 0) {
            davidContainer.innerHTML = '<p>No balance data found.</p>';
            return;
        }

        accounts.forEach((accountName, idx) => {
            const accountData = balances[accountName];
            let content = `<div class="balance-account-container">`;
            content += `<h4 class="balance-account-name">${accountName.replace(/_/g, ' ')}</h4>`;

            if (accountData.error) {
                content += `<p style="color: #e53e3e;">Error: ${accountData.error}</p>`;
            } else {
                let hasBalance = false;
                let balanceContent = '<ul class="balance-list">';
                for (const currency in accountData) {
                    const rawVal = accountData[currency];
                    if (parseFloat(rawVal) !== 0) {
                        hasBalance = true;
                        const currencyUpper = currency.toUpperCase();
                        if (currencyUpper === 'MXN') {
                            const amount = parseFloat(rawVal);
                            balanceContent += `
                                <li>
                                    ${buildFundMeter(amount)}
                                    <div class="balance-list-row">
                                        <strong>${currencyUpper}</strong>
                                        <span style="font-size:0.88rem;font-weight:600;">${parseFloat(rawVal).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}</span>
                                    </div>
                                </li>`;
                        } else {
                            balanceContent += `
                                <li>
                                    <div class="balance-list-row">
                                        <strong>${currencyUpper}</strong>
                                        <span>${rawVal}</span>
                                    </div>
                                </li>`;
                        }
                    }
                }
                if (!hasBalance) balanceContent += '<li><div class="balance-list-row"><span>No active balances.</span></div></li>';
                balanceContent += '</ul>';
                content += balanceContent;
            }
            content += '</div>';

            const target = idx % 2 === 0 ? davidContainer : joeContainer;
            target.innerHTML += content;
        });

        // Combined MXN badge
        const totalMXN = accounts.reduce((sum, name) => {
            const data = balances[name];
            if (!data || data.error) return sum;
            for (const k in data) {
                if (k.toUpperCase() === 'MXN') {
                    const v = parseFloat(data[k]);
                    return !isNaN(v) ? sum + v : sum;
                }
            }
            return sum;
        }, 0);
        const badge = document.getElementById('wallet-total-badge');
        if (badge) {
            badge.textContent = totalMXN > 0
                ? '$' + totalMXN.toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' MXN'
                : '';
            badge.style.display = totalMXN > 0 ? 'inline-block' : 'none';
        }
    }

    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    fetchOffers();
    fetchWalletBalances();
    setInterval(updateStatus, 30000);
    setInterval(fetchActiveTrades, 15000);
    setInterval(fetchOffers, 120000);
    setInterval(fetchWalletBalances, 300000);
});
// static/script.js
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

    // --- Event Listeners ---
    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            const response = await fetch('/start_trading', { method: 'POST' });
            const result = await response.json();
            alert(result.message);
            updateStatus();
        });
    }

    if(stopBtn) {
        stopBtn.addEventListener('click', async () => {
            const response = await fetch('/stop_trading', { method: 'POST' });
            const result = await response.json();
            alert(result.message);
            updateStatus();
        });
    }

    // Consolidated handler for all settings toggles
    settingToggles.forEach(toggle => {
        toggle.addEventListener('change', async () => {
            const key = toggle.dataset.key;
            const isEnabled = toggle.checked;

            try {
                const response = await fetch('/update_setting', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: key, enabled: isEnabled })
                });
                const result = await response.json();
                if (!result.success) {
                    alert(`Error: ${result.error}`);
                    toggle.checked = !isEnabled; // Revert on error
                } else {
                    console.log(result.message);
                }
            } catch (error) {
                console.error(`Failed to update setting ${key}:`, error);
                alert('An unexpected error occurred.');
                toggle.checked = !isEnabled; // Revert on error
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
                    alert(`Error: ${result.message}`);
                    offersCheckbox.checked = !isEnabled;
                } else {
                    alert(result.message);
                    fetchOffers(); // Refresh the individual offers list
                }
            } catch (error) {
                console.error('Failed to update offers status:', error);
                alert('An unexpected error occurred.');
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
                const data = {
                    filename: formData.get('filename'),
                    owner_username: formData.get('owner_username'),
                    payment_method: formData.get('payment_method'),
                    selected_id: formData.get('selected_id')
                };
                selections.push(data);
            });

            try {
                const response = await fetch('/update_all_selections', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(selections)
                });
                const result = await response.json();
                if (result.success) {
                    alert('All selections saved successfully!');
                } else {
                    alert(`Error: ${result.error}`);
                }
            } catch (error) {
                console.error('Failed to save all selections:', error);
                alert('An unexpected error occurred while saving selections.');
            }
        });
    }
    
    if (tradesContainer) {
        tradesContainer.addEventListener('click', async (event) => {
            if (event.target.classList.contains('send-manual-message-btn')) {
                const button = event.target;
                const tradeHash = button.dataset.tradeHash;
                const accountName = button.dataset.accountName;
                const input = button.previousElementSibling;
                const message = input.value.trim();

                if (!message) {
                    alert('Please type a message to send.');
                    return;
                }

                button.disabled = true;
                button.textContent = '...';

                try {
                    const response = await fetch('/send_manual_message', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            trade_hash: tradeHash,
                            account_name: accountName,
                            message: message
                        })
                    });

                    const result = await response.json();

                    if (result.success) {
                        alert(result.message);
                        input.value = ''; // Clear input on success
                    } else {
                        alert(`Error: ${result.error}`);
                    }
                } catch (error) {
                    console.error('Failed to send manual message:', error);
                    alert('An unexpected error occurred.');
                } finally {
                    button.disabled = false;
                    button.textContent = 'Send';
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
                        body: JSON.stringify({
                            offer_hash: offerHash,
                            account_name: accountName,
                            enabled: isEnabled
                        })
                    });
                    const result = await response.json();
                    if (!result.success) {
                        alert(`Error updating offer: ${result.error}`);
                        checkbox.checked = !isEnabled; // Revert on error
                    } else {
                        // Update status text and color on success
                        statusCell.textContent = isEnabled ? 'Enabled' : 'Disabled';
                        statusCell.className = `status-indicator ${isEnabled ? 'running' : 'stopped'}`;
                    }
                } catch (error) {
                    console.error('Failed to toggle offer:', error);
                    alert('An unexpected error occurred.');
                    checkbox.checked = !isEnabled; // Revert on error
                } finally {
                    checkbox.disabled = false;
                }
            }
        });
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
        tradesContainer.innerHTML = '';
        if (!trades || trades.length === 0) {
            tradesContainer.innerHTML = '<p>No active trades found.</p>';
            return;
        }
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
                    <th>Send Message</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tbody = table.querySelector('tbody');
        trades.forEach(trade => {
            const row = document.createElement('tr');
            if (trade.trade_status === 'Paid') {
                row.classList.add('status-paid');
            } else if (trade.trade_status === 'Dispute open') {
                row.classList.add('status-disputed');
            }
            row.innerHTML = `
                <td>${trade.account_name_source || 'N/A'}</td>
                <td>${trade.trade_hash || 'N/A'}</td>
                <td>${trade.responder_username || 'N/A'}</td>
                <td>${trade.fiat_amount_requested || 'N/A'} ${trade.fiat_currency_code || ''}</td>
                <td>${trade.payment_method_name || 'N/A'}</td>
                <td>${trade.trade_status || 'N/A'}</td>
                <td class="message-cell">
                    <input type="text" class="manual-message-input" placeholder="Type a message...">
                    <button class="send-manual-message-btn" data-trade-hash="${trade.trade_hash}" data-account-name="${trade.account_name_source}">Send</button>
                </td>
            `;
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
            const row = document.createElement('tr');
            const isEnabled = offer.enabled;
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

    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    fetchOffers();
    setInterval(updateStatus, 60000);
    setInterval(fetchActiveTrades, 60000);
    setInterval(fetchOffers, 120000); 
});
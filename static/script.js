document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const tradesContainer = document.getElementById('active-trades-container');
    const nightModeCheckbox = document.getElementById('night-mode-checkbox');
    const afkModeCheckbox = document.getElementById('afk-mode-checkbox');
    const saveAllBtn = document.getElementById('save-all-btn');
    const offersCheckbox = document.getElementById('offers-checkbox');

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

    if (nightModeCheckbox) {
        nightModeCheckbox.addEventListener('change', async () => {
            const isEnabled = nightModeCheckbox.checked;
            try {
                const response = await fetch('/update_night_mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 'night_mode_enabled': isEnabled })
                });
                const result = await response.json();
                if (!result.success) {
                    alert(`Error: ${result.error}`);
                } else {
                    console.log(result.message);
                }
                if (isEnabled && afkModeCheckbox.checked) {
                    afkModeCheckbox.checked = false;
                    const afkResponse = await fetch('/update_afk_mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 'afk_mode_enabled': false })
                    });
                    const afkResult = await afkResponse.json();
                    if (!afkResult.success) {
                        console.error(`Error disabling AFK mode: ${afkResult.error}`);
                    } else {
                        console.log(afkResult.message);
                    }
                }
            } catch (error) {
                console.error('Failed to update night mode:', error);
                alert('An unexpected error occurred while updating night mode.');
            }
        });
    }

    if (afkModeCheckbox) {
        afkModeCheckbox.addEventListener('change', async () => {
            const isEnabled = afkModeCheckbox.checked;
            try {
                const response = await fetch('/update_afk_mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 'afk_mode_enabled': isEnabled })
                });
                const result = await response.json();
                if (!result.success) {
                    alert(`Error: ${result.error}`);
                } else {
                    console.log(result.message);
                }
                if (isEnabled && nightModeCheckbox.checked) {
                    nightModeCheckbox.checked = false;
                    const nightResponse = await fetch('/update_night_mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 'night_mode_enabled': false })
                    });
                    const nightResult = await nightResponse.json();
                    if (!nightResult.success) {
                        console.error(`Error disabling nighttime mode: ${nightResult.error}`);
                    } else {
                        console.log(nightResult.message);
                    }
                }
            } catch (error) {
                console.error('Failed to update AFK mode:', error);
                alert('An unexpected error occurred while updating AFK mode.');
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

    if (offersCheckbox) {
        offersCheckbox.addEventListener('change', async () => {
            const isEnabled = offersCheckbox.checked;
            const endpoint = isEnabled ? '/offer/turn-on' : '/offer/turn-off';
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });
                const result = await response.json();
                if (!result.success) {
                    alert(`Error: ${result.message}`);
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Failed to update offers status:', error);
                alert('An unexpected error occurred while updating offers status.');
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

    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    setInterval(updateStatus, 60000);
    setInterval(fetchActiveTrades, 60000);
});
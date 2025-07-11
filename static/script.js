document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const tradesContainer = document.getElementById('active-trades-container');
    const statsContainer = document.getElementById('performance-stats-container'); // New element
    const nightModeCheckbox = document.getElementById('night-mode-checkbox');
    const afkModeCheckbox = document.getElementById('afk-mode-checkbox');

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

    document.querySelectorAll('.account-form').forEach(form => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(form);
            const data = {
                filename: formData.get('filename'),
                owner_username: formData.get('owner_username'),
                payment_method: formData.get('payment_method'),
                selected_id: formData.get('selected_id')
            };
            if (!data.selected_id) {
                alert('Please select an account.');
                return;
            }
            try {
                const response = await fetch('/update_selection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                if (result.success) {
                    alert('Selection saved successfully!');
                } else {
                    alert(`Error: ${result.error}`);
                }
            } catch (error) {
                console.error('Failed to save selection:', error);
                alert('An unexpected error occurred.');
            }
        });
    });

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
            `;
            tbody.appendChild(row);
        });
        tradesContainer.appendChild(table);
    }

    async function fetchTradeStats() {
        if (!statsContainer) return;
        try {
            const response = await fetch('/get_trade_stats');
            const stats = await response.json();
            statsContainer.innerHTML = `
                <div class="stat-item">
                    <h4>Trades Today</h4>
                    <p>${stats.trades_today}</p>
                </div>
                <div class="stat-item">
                    <h4>Volume Today</h4>
                    <p>$${stats.volume_today.toLocaleString()} MXN</p>
                </div>
                <div class="stat-item">
                    <h4>Success Rate</h4>
                    <p>${stats.success_rate}%</p>
                </div>
                <div class="stat-item">
                    <h4>Top Payment Method</h4>
                    <p>${stats.top_payment_method}</p>
                </div>
            `;
        } catch (error) {
            statsContainer.innerHTML = '<p>Error fetching stats.</p>';
            console.error(error);
        }
    }

    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    fetchTradeStats();
    setInterval(updateStatus, 60000);
    setInterval(fetchActiveTrades, 60000);
    setInterval(fetchTradeStats, 60000);
});
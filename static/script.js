document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const tradesContainer = document.getElementById('active-trades-container');
    const telegramContainer = document.getElementById('telegram-alerts-container');
    const nightModeCheckbox = document.getElementById('night-mode-checkbox');

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

    // Event listener for the new checkbox
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
                    console.log(result.message); // Log success to console
                }
            } catch (error) {
                console.error('Failed to update night mode:', error);
                alert('An unexpected error occurred while updating night mode.');
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

    async function fetchTelegramAlerts() {
        if (!telegramContainer) return;
        try {
            const response = await fetch('/get_telegram_messages');
            const messages = await response.json();
            
            telegramContainer.innerHTML = '';

            if (!messages || messages.length === 0) {
                telegramContainer.innerHTML = '<p>No recent alerts.</p>';
                return;
            }

            messages.reverse().forEach(msg => {
                const p = document.createElement('p');
                p.className = 'telegram-message';
                p.textContent = msg;
                telegramContainer.appendChild(p);
            });

        } catch (error) {
            telegramContainer.innerHTML = '<p>Error fetching alerts.</p>';
            console.error(error);
        }
    }

    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    fetchTelegramAlerts();
    setInterval(updateStatus, 60000);
    setInterval(fetchActiveTrades, 60000);
    setInterval(fetchTelegramAlerts, 60000);
});
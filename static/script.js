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
    // --- NEW ---
    const generateMarketReportBtn = document.getElementById('generate-market-report-btn');
    // --- END NEW ---
    const balancesContainer = document.getElementById('wallet-balances-container');
    const toggleOffersBtn = document.getElementById('toggle-offers-visibility-btn');

    // --- Initial State ---
    if (offersContainer) {
        offersContainer.style.display = 'none';
    }

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

    if (generateChartsBtn) {
        generateChartsBtn.addEventListener('click', async () => {
            generateChartsBtn.disabled = true;
            generateChartsBtn.textContent = 'Generating...';

            try {
                const response = await fetch('/generate_charts', { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    alert('Reports generated and saved successfully on the server!');
                } else {
                    alert(`Error generating reports: ${result.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Failed to generate reports:', error);
                alert('An unexpected error occurred while generating reports.');
            } finally {
                generateChartsBtn.disabled = false;
                generateChartsBtn.textContent = 'Generate Reports';
            }
        });
    }

// Generate Client Profitability Report Button
const generateClientReportBtn = document.getElementById('generate-client-report-btn');
if (generateClientReportBtn) {
    generateClientReportBtn.addEventListener('click', async () => {
        generateClientReportBtn.disabled = true;
        generateClientReportBtn.textContent = 'Generating Report...';

        try {
            const response = await fetch('/generate_client_report', { method: 'POST' });
            const result = await response.json();

            if (result.success) {
                alert('Client Profitability Report generated! Your download will begin.');
                const downloadUrl = `/charts/${result.filename}`;
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.setAttribute('download', result.filename);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else {
                alert(`Error generating report: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Failed to generate client profitability report:', error);
            alert('An unexpected error occurred while generating the report.');
        } finally {
            generateClientReportBtn.disabled = false;
            generateClientReportBtn.textContent = 'Download Client Profitability Report';
        }
    });
}


    // --- NEW LISTENER ---
    if (generateMarketReportBtn) {
        generateMarketReportBtn.addEventListener('click', async () => {
            generateMarketReportBtn.disabled = true;
            generateMarketReportBtn.textContent = 'Generating Report... (this may take a minute)';

            try {
                // Set a long timeout, as this request can take a while
                const response = await fetch('/generate_market_report', { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    alert('Report generated! Your download will begin.');
                    // Create a temporary link to trigger the download
                    const downloadUrl = `/charts/${result.filename}`;
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.setAttribute('download', result.filename); // This forces download
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    alert(`Error generating report: ${result.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Failed to generate market report:', error);
                alert('An unexpected error occurred while generating the report.');
            } finally {
                generateMarketReportBtn.disabled = false;
                generateMarketReportBtn.textContent = 'Download MXN Market Report';
            }
        });
    }
    // --- END NEW LISTENER ---

    if (toggleOffersBtn) {
        toggleOffersBtn.addEventListener('click', () => {
            const isHidden = offersContainer.style.display === 'none';
            offersContainer.style.display = isHidden ? 'block' : 'none';
            toggleOffersBtn.textContent = isHidden ? 'Hide' : 'Show All';
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
            } else if (event.target.classList.contains('release-trade-btn')) {
                const button = event.target;
                const tradeHash = button.dataset.tradeHash;
                const accountName = button.dataset.accountName;

                if (!confirm(`Are you sure you want to release the trade ${tradeHash}?`)) {
                    return;
                }

                button.disabled = true;
                button.textContent = '...';

                try {
                    const response = await fetch('/release_trade', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            trade_hash: tradeHash,
                            account_name: accountName
                        })
                    });

                    const result = await response.json();

                    if (result.success) {
                        alert(result.message);
                        fetchActiveTrades(); // Refresh the trades table
                    } else {
                        alert(`Error: ${result.error}`);
                    }
                } catch (error) {
                    console.error('Failed to release trade:', error);
                    alert('An unexpected error occurred.');
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
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tbody = table.querySelector('tbody');
        trades.forEach(trade => {
            const row = document.createElement('tr');
            
            // Check if trade is newly created (within 30 minutes)
            const isNewTrade = () => {
                if (trade.created_at) {
                    const createdTime = new Date(trade.created_at);
                    const now = new Date();
                    const diffMinutes = (now - createdTime) / (1000 * 60);
                    return diffMinutes <= 30;
                }
                return false;
            };
            
            // Apply color coding based on status (priority order)
            if (isNewTrade() && trade.trade_status !== 'Paid' && trade.trade_status !== 'Dispute open') {
                row.classList.add('status-new');
            } else if (trade.trade_status === 'Paid' && !trade.has_attachment) {
                row.classList.add('status-paid-no-attachment');
            } else if (trade.trade_status === 'Paid') {
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
                    <button class="release-trade-btn" data-trade-hash="${trade.trade_hash}" data-account-name="${trade.account_name_source}">Release</button>
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

    // --- NEW FUNCTIONS FOR WALLET BALANCES ---
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

function updateBalancesDashboard(balances) {
        const davidContainer = document.getElementById('david-balances-col');
        const joeContainer = document.getElementById('joe-balances-col');

        if (!davidContainer || !joeContainer) return;

        // --- UPDATED: Clear previous content without adding titles ---
        davidContainer.innerHTML = ''; 
        joeContainer.innerHTML = '';

        if (Object.keys(balances).length === 0) {
            davidContainer.innerHTML += '<p>No balance data found.</p>';
            joeContainer.innerHTML += '<p>No balance data found.</p>';
            return;
        }
        
        for (const accountName in balances) {
            // Skip Paxful accounts
            if (accountName.toLowerCase().includes('paxful')) {
                continue;
            }
            
            const accountData = balances[accountName];
            
            let content = `<div class="balance-account-container">`;
            content += `<h4 class="balance-account-name">${accountName.replace(/_/g, ' ')}</h4>`;

            if (accountData.error) {
                content += `<p style="color: #e53e3e;">Error: ${accountData.error}</p>`;
            } else {
                let hasPositiveBalance = false;
                let balanceContent = '<ul class="balance-list">';
                
                if (Object.keys(accountData).length > 0) {
                    for (const currency in accountData) {
                        const balanceValue = parseFloat(accountData[currency]);
                        if (balanceValue !== 0) {
                            balanceContent += `<li><strong>${currency.toUpperCase()}:</strong> ${accountData[currency]}</li>`;
                            hasPositiveBalance = true;
                        }
                    }
                }

                if (!hasPositiveBalance) {
                    balanceContent += '<li>No active balances.</li>';
                }
                
                balanceContent += '</ul>';
                content += balanceContent;
            }
            content += `</div>`;

            if (accountName.toLowerCase().startsWith('david')) {
                davidContainer.innerHTML += content;
            } else if (accountName.toLowerCase().startsWith('joe')) {
                joeContainer.innerHTML += content;
            }
        }
    }
    // --- Initial and Periodic Updates ---
    updateStatus();
    fetchActiveTrades();
    fetchOffers();
    fetchWalletBalances(); // Initial fetch
    setInterval(updateStatus, 60000);
    setInterval(fetchActiveTrades, 60000);
    setInterval(fetchOffers, 120000); 
    setInterval(fetchWalletBalances, 300000);
});
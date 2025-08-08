document.addEventListener('DOMContentLoaded', () => {
    const ws = new WebSocket(`ws://${window.location.host}/ws`);

    // --- DOM Elements ---
    const btnLoadErg = document.getElementById('btn-load-erg');
    const btnScan = document.getElementById('btn-scan');
    const btnConnect = document.getElementById('btn-connect');
    const btnDisconnect = document.getElementById('btn-disconnect');
    const btnStart = document.getElementById('btn-start');

    const deviceGrid = document.getElementById('device-grid');
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');

    const valTargetPower = document.getElementById('val-target-power');
    const valPower = document.getElementById('val-power');
    const valHr = document.getElementById('val-hr');
    const valCadence = document.getElementById('val-cadence');

    let deviceLists = {};
    let selectedDevices = {};

    // --- Chart.js Setup ---
    const ctx = document.getElementById('training-chart').getContext('2d');
    const trainingChart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                { label: 'Target Power', borderColor: 'rgba(255, 159, 64, 0.8)', yAxisID: 'yPower', data: [] },
                { label: 'Power', borderColor: 'rgba(255, 99, 132, 1)', yAxisID: 'yPower', data: [] },
                { label: 'Heart Rate', borderColor: 'rgba(54, 162, 235, 1)', yAxisID: 'yHR', data: [] },
                { label: 'Cadence', borderColor: 'rgba(75, 192, 192, 1)', yAxisID: 'yCadence', data: [] },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Time (s)' } },
                yPower: { type: 'linear', position: 'left', title: { display: true, text: 'Watts' } },
                yHR: { type: 'linear', position: 'right', title: { display: true, text: 'BPM' }, grid: { drawOnChartArea: false } },
                yCadence: { type: 'linear', position: 'right', title: { display: true, text: 'RPM' }, grid: { drawOnChartArea: false } },
            }
        }
    });

    // --- WebSocket Handlers ---
    ws.onopen = () => statusText.textContent = 'Status: Connected to server.';
    ws.onclose = () => statusText.textContent = 'Status: Disconnected from server.';
    ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
        statusText.textContent = 'Status: Connection error.';
    };
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
    };

    function sendMessage(message) {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
        }
    }

    // --- UI Event Listeners ---
    btnScan.addEventListener('click', () => sendMessage({ command: 'scan' }));
    btnDisconnect.addEventListener('click', () => sendMessage({ command: 'disconnect' }));
    btnStart.addEventListener('click', () => sendMessage({ command: 'start_workout' }));

    btnLoadErg.addEventListener('click', () => {
        // pywebview file dialog is better, this is a placeholder for browser use
        const path = prompt("Enter path to ERG file (e.g., erg_files/sample.erg):");
        if (path) {
            sendMessage({ command: 'load_erg', filepath: path });
        }
    });

    btnConnect.addEventListener('click', () => {
        const devicesToConnect = [];
        for (const role in selectedDevices) {
            if (selectedDevices[role]) {
                devicesToConnect.push({ role: role, address: selectedDevices[role] });
            }
        }
        sendMessage({ command: 'connect', devices: devicesToConnect });
    });

    // --- Message Handling Logic ---
    function handleMessage(message) {
        const { type, ...data } = message;

        switch (type) {
            case 'scan_complete':
                updateDeviceLists(data.devices_by_role);
                break;
            case 'status_update':
                statusText.textContent = `Status: ${data.message}`;
                break;
            case 'connection_status':
                statusText.textContent = `Status: ${data.device_type.toUpperCase()} ${data.status}`;
                break;
            case 'workout_update':
                valTargetPower.textContent = `${data.target_power} W`;
                progressBar.value = data.progress;
                addDataToChart('Target Power', data.progress / 100 * total_duration, data.target_power);
                break;
            case 'workout_finished':
                statusText.textContent = `Status: ${data.message}`;
                progressBar.value = 100;
                break;
            case 'hr_update':
                valHr.textContent = `${data.value} BPM`;
                addDataToChart('Heart Rate', (Date.now() - workoutStartTime) / 1000, data.value);
                break;
            case 'power_update':
                valPower.textContent = `${data.value} W`;
                addDataToChart('Power', (Date.now() - workoutStartTime) / 1000, data.value);
                break;
            case 'csc_update':
                valCadence.textContent = `${data.crank_rev} RPM`;
                addDataToChart('Cadence', (Date.now() - workoutStartTime) / 1000, data.crank_rev);
                break;
        }
    }

    function updateDeviceLists(devicesByRole) {
        deviceGrid.innerHTML = '';
        deviceLists = {};
        selectedDevices = {};

        for (const role in devicesByRole) {
            const container = document.createElement('div');
            container.innerHTML = `<h3>${role.toUpperCase()}</h3>`;
            const listEl = document.createElement('div');
            listEl.className = 'device-list';
            deviceLists[role] = listEl;

            devicesByRole[role].forEach(device => {
                const item = document.createElement('div');
                item.textContent = `${device.name} (${device.address})`;
                item.dataset.address = device.address;
                item.addEventListener('click', () => {
                    // Deselect previous
                    if (selectedDevices[role]) {
                        const prevSelected = listEl.querySelector(`[data-address="${selectedDevices[role]}"]`);
                        if(prevSelected) prevSelected.classList.remove('selected');
                    }
                    // Select new
                    item.classList.add('selected');
                    selectedDevices[role] = device.address;
                });
                listEl.appendChild(item);
            });
            container.appendChild(listEl);
            deviceGrid.appendChild(container);
        }
    }

    let workoutStartTime = 0;
    let total_duration = 0; // Will be set when workout starts
    function addDataToChart(label, x, y) {
        const dataset = trainingChart.data.datasets.find(ds => ds.label === label);
        if (dataset) {
            dataset.data.push({ x, y });
            trainingChart.update('none');
        }
    }

    // This is a simplified logic for workout start time and duration
    btnStart.addEventListener('click', () => {
        workoutStartTime = Date.now();
        // A better implementation would get duration from backend after loading ERG
        // For now, let's assume a duration for charting purposes
        const workoutData = workout_manager.workout; // This is pseudo-code
        if(workoutData && workoutData.length > 0){
            total_duration = workoutData[workoutData.length - 1][0];
            trainingChart.options.scales.x.max = total_duration;
        }
    });
});

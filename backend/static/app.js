/**
 * F1 Race Strategy Simulator — Dashboard Application
 * =====================================================
 * Professional analytics dashboard with Chart.js visualizations.
 * Connects to the Flask backend for Monte Carlo simulation results.
 */

// ---- State ----
let currentResults = null;
let charts = {};
let trackData = {};

// ---- Chart.js Global Config ----
Chart.defaults.color = '#8b8b9e';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 14;
Chart.defaults.animation.duration = 600;
Chart.defaults.animation.easing = 'easeOutQuart';

const COMPOUND_COLORS = {
    soft: { bg: 'rgba(255, 23, 68, 0.7)', border: '#FF1744' },
    medium: { bg: 'rgba(255, 214, 0, 0.7)', border: '#FFD600' },
    hard: { bg: 'rgba(236, 239, 241, 0.6)', border: '#ECEFF1' },
};

const STRATEGY_COLORS = [
    'rgba(225, 6, 0, 0.8)',
    'rgba(41, 121, 255, 0.8)',
    'rgba(255, 107, 53, 0.8)',
    'rgba(0, 200, 83, 0.8)',
    'rgba(0, 229, 255, 0.8)',
    'rgba(255, 215, 0, 0.8)',
    'rgba(156, 39, 176, 0.8)',
    'rgba(255, 82, 82, 0.8)',
    'rgba(100, 255, 218, 0.8)',
    'rgba(255, 167, 38, 0.8)',
];

// ---- DOM Elements ----
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    loadTracks();
    bindControls();
});

// Global error handler
window.addEventListener('error', (e) => {
    console.error('Global Error:', e.message);
    setStatus('error', 'Initialization Error');
});

// ---- Load Track Data ----
async function loadTracks() {
    try {
        const res = await fetch(`/api/tracks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        trackData = data.tracks;
        updateTrackInfo();
    } catch (e) {
        console.error('Could not load tracks from API, using defaults:', e);
    }
}

function updateTrackInfo() {
    const track = $('#trackSelect').value;
    const info = trackData[track];
    if (!info) return;
    $('#trackLaps').textContent = info.laps;
    $('#trackPitLoss').textContent = info.pit_stop_loss + 's';
    $('#trackDeg').textContent = info.degradation_factor.toFixed(2);
}

// ---- Bind Controls ----
function bindControls() {
    // Range sliders
    $('#simCount').addEventListener('input', (e) => {
        $('#simCountVal').textContent = e.target.value;
    });
    $('#scProb').addEventListener('input', (e) => {
        $('#scProbVal').textContent = (parseFloat(e.target.value) * 100).toFixed(1) + '%';
    });
    $('#aggressionSlider').addEventListener('input', (e) => {
        $('#aggressionVal').textContent = parseFloat(e.target.value).toFixed(2);
    });

    // Track change
    $('#trackSelect').addEventListener('change', () => {
        updateTrackInfo();
    });

    // Run simulation
    $('#runSimBtn').addEventListener('click', runSimulation);

    // Sensitivity analysis
    $('#sensitivityBtn').addEventListener('click', runSensitivity);
}

// ---- Run Simulation ----
async function runSimulation() {
    const btn = $('#runSimBtn');
    btn.disabled = true;
    showLoading(true, 'Running Monte Carlo Simulation...', 'Evaluating all strategy permutations');

    const payload = {
        track: $('#trackSelect').value,
        n_simulations: parseInt($('#simCount').value),
        sc_probability: parseFloat($('#scProb').value),
        weather: $('#weatherSelect').value,
        aggression: parseFloat($('#aggressionSlider').value),
    };

    try {
        setStatus('running', 'Simulating...');
        const res = await fetch(`/api/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error(`API error: ${res.status}`);
        
        currentResults = await res.json();
        renderResults(currentResults);

        // Load degradation curves
        loadDegradationCurves(payload.track);

        setStatus('ready', 'Complete');
        $('#computeTime').textContent = `${currentResults.computation_time}s`;
    } catch (err) {
        console.error('Simulation error:', err);
        setStatus('error', 'Error');
        alert('Simulation failed. Make sure the backend is running on port 5000.');
    } finally {
        btn.disabled = false;
        showLoading(false);
    }
}

// ---- Render Results ----
function renderResults(data) {
    const strategies = filterStrategies(data.strategies);
    if (!strategies.length) return;

    const optimal = strategies[0];

    // Update metrics
    updateMetrics(optimal, data);

    // Update strategy selectors
    updateStrategySelectors(strategies);

    // Render charts
    renderHistogram(optimal);
    renderStrategyComparison(strategies);
    renderRiskReward(strategies);
    renderLapTraces(optimal);

    // Render table
    renderTable(strategies);

    // Render insights
    renderInsights(data.insights);
}

function filterStrategies(strategies) {
    const show1 = $('#show1Stop').checked;
    const show2 = $('#show2Stop').checked;
    const show3 = $('#show3Stop').checked;
    return strategies.filter(s => {
        if (s.stops === 1 && !show1) return false;
        if (s.stops === 2 && !show2) return false;
        if (s.stops === 3 && !show3) return false;
        return true;
    });
}

// ---- Metrics ----
function updateMetrics(optimal, data) {
    $('#optimalStrategy').textContent = optimal.name;
    $('#optimalStops').textContent = `${optimal.stops}-stop | Score: ${optimal.score.toFixed(1)}`;

    const mins = Math.floor(optimal.mean_time / 60);
    const secs = (optimal.mean_time % 60).toFixed(1);
    $('#expectedTime').textContent = `${mins}:${secs.padStart(4, '0')}`;
    $('#expectedTimeSub').textContent = `σ = ${optimal.std_time.toFixed(1)}s`;

    $('#riskScore').textContent = optimal.risk_score.toFixed(1);
    const bestCase = Math.floor(optimal.best_case / 60);
    const bestSec = (optimal.best_case % 60).toFixed(1);
    const worstCase = Math.floor(optimal.worst_case / 60);
    const worstSec = (optimal.worst_case % 60).toFixed(1);
    $('#riskScoreSub').textContent = `${bestCase}:${bestSec.padStart(4,'0')} — ${worstCase}:${worstSec.padStart(4,'0')}`;

    $('#avgSC').textContent = optimal.avg_safety_cars.toFixed(1);
    $('#avgSCSub').textContent = `per ${data.n_simulations} sims`;

    // Animate cards
    $$('.metric-card').forEach((card, i) => {
        card.style.animation = 'none';
        card.offsetHeight; // reflow
        card.style.animation = `fadeIn 0.4s ${i * 0.08}s var(--ease-out) forwards`;
    });
}

// ---- Strategy Selectors ----
function updateStrategySelectors(strategies) {
    const selectors = ['#histogramStrategy', '#traceStrategy'];
    selectors.forEach(sel => {
        const el = $(sel);
        el.innerHTML = '';
        strategies.forEach((s, i) => {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = s.name;
            if (i === 0) opt.textContent += ' ★';
            el.appendChild(opt);
        });
        el.addEventListener('change', () => {
            const idx = parseInt(el.value);
            if (sel === '#histogramStrategy') renderHistogram(strategies[idx]);
            if (sel === '#traceStrategy') renderLapTraces(strategies[idx]);
        });
    });
}

// ---- Charts ----
function destroyChart(key) {
    if (charts[key]) {
        charts[key].destroy();
        delete charts[key];
    }
}

function renderHistogram(strategy) {
    destroyChart('histogram');
    const ctx = $('#histogramChart').getContext('2d');

    const bins = strategy.total_times_bins;
    const counts = strategy.total_times_histogram;
    const labels = [];
    for (let i = 0; i < counts.length; i++) {
        const mins = Math.floor(bins[i] / 60);
        const secs = (bins[i] % 60).toFixed(0);
        labels.push(`${mins}:${secs.padStart(2, '0')}`);
    }

    const maxCount = Math.max(...counts);
    const colors = counts.map((c, i) => {
        const binCenter = (bins[i] + bins[i + 1]) / 2;
        if (binCenter <= strategy.p5) return 'rgba(0, 200, 83, 0.65)';
        if (binCenter >= strategy.p95) return 'rgba(225, 6, 0, 0.65)';
        return 'rgba(41, 121, 255, 0.55)';
    });

    charts.histogram = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: counts,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace(/[\d.]+\)$/, '1)')),
                borderWidth: 1,
                borderRadius: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `Race Time: ${items[0].label}`,
                        label: (item) => `${item.raw} simulations`,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Total Race Time', color: '#5a5a6e', font: { size: 10 } },
                    ticks: { maxTicksLimit: 12, font: { size: 9 } },
                    grid: { display: false },
                },
                y: {
                    title: { display: true, text: 'Frequency', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
            },
        },
    });
}

function renderStrategyComparison(strategies) {
    destroyChart('stratComp');
    const ctx = $('#strategyChart').getContext('2d');
    const top = strategies.slice(0, 10);

    charts.stratComp = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top.map(s => s.name),
            datasets: [
                {
                    label: 'Mean Time',
                    data: top.map(s => s.mean_time),
                    backgroundColor: top.map((_, i) => STRATEGY_COLORS[i % STRATEGY_COLORS.length]),
                    borderRadius: 3,
                    barPercentage: 0.7,
                },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const s = top[item.dataIndex];
                            const m = Math.floor(s.mean_time / 60);
                            const sec = (s.mean_time % 60).toFixed(1);
                            return `${m}:${sec.padStart(4,'0')} ± ${s.std_time.toFixed(1)}s`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Total Race Time (s)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
                y: {
                    ticks: { font: { size: 9, family: "'JetBrains Mono', monospace" } },
                    grid: { display: false },
                },
            },
        },
    });
}

function renderRiskReward(strategies) {
    destroyChart('riskReward');
    const ctx = $('#riskRewardChart').getContext('2d');
    const top = strategies.slice(0, 15);

    const datasets = [];
    const stopColors = {
        1: { bg: 'rgba(41, 121, 255, 0.7)', border: '#2979FF' },
        2: { bg: 'rgba(255, 107, 53, 0.7)', border: '#FF6B35' },
        3: { bg: 'rgba(0, 200, 83, 0.7)', border: '#00C853' },
    };

    [1, 2, 3].forEach(stops => {
        const filtered = top.filter(s => s.stops === stops);
        if (!filtered.length) return;
        datasets.push({
            label: `${stops}-Stop`,
            data: filtered.map(s => ({ x: s.std_time, y: s.mean_time, name: s.name })),
            backgroundColor: stopColors[stops].bg,
            borderColor: stopColors[stops].border,
            borderWidth: 1.5,
            pointRadius: 7,
            pointHoverRadius: 10,
        });
    });

    charts.riskReward = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const d = item.raw;
                            return `${d.name}: μ=${d.y.toFixed(1)}s, σ=${d.x.toFixed(1)}s`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Risk (Std Dev, s)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
                y: {
                    title: { display: true, text: 'Reward (Mean Time, s)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
            },
        },
    });
}

function renderLapTraces(strategy) {
    destroyChart('lapTrace');
    const ctx = $('#lapTraceChart').getContext('2d');

    const traces = strategy.sample_lap_times || [];
    if (!traces.length) return;

    const datasets = traces.slice(0, 8).map((trace, i) => ({
        label: `Sim ${i + 1}`,
        data: trace,
        borderColor: STRATEGY_COLORS[i % STRATEGY_COLORS.length],
        borderWidth: 1,
        pointRadius: 0,
        tension: 0.3,
        fill: false,
    }));

    charts.lapTrace = new Chart(ctx, {
        type: 'line',
        data: {
            labels: traces[0].map((_, i) => i + 1),
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { display: true, position: 'top', labels: { font: { size: 9 } } },
                tooltip: {
                    callbacks: {
                        title: (items) => `Lap ${items[0].label}`,
                        label: (item) => `${item.dataset.label}: ${item.raw.toFixed(2)}s`,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Lap', color: '#5a5a6e', font: { size: 10 } },
                    grid: { display: false },
                    ticks: { maxTicksLimit: 15 },
                },
                y: {
                    title: { display: true, text: 'Lap Time (s)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
            },
        },
    });
}

async function loadDegradationCurves(track) {
    try {
        const res = await fetch(`/api/degradation_curves`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ track }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderTyreDegradation(data);
    } catch (e) {
        console.error('Failed to load degradation curves:', e);
    }
}

function renderTyreDegradation(data) {
    destroyChart('tyre');
    const ctx = $('#tyreChart').getContext('2d');

    const laps = Array.from({ length: data.laps }, (_, i) => i + 1);

    charts.tyre = new Chart(ctx, {
        type: 'line',
        data: {
            labels: laps,
            datasets: Object.entries(data.curves).map(([compound, curve]) => ({
                label: compound.charAt(0).toUpperCase() + compound.slice(1),
                data: curve,
                borderColor: COMPOUND_COLORS[compound].border,
                backgroundColor: COMPOUND_COLORS[compound].bg,
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.4,
                fill: false,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: (items) => `Lap ${items[0].label}`,
                        label: (item) => `${item.dataset.label}: +${item.raw.toFixed(2)}s`,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Tyre Age (laps)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12 },
                },
                y: {
                    title: { display: true, text: 'Degradation (s)', color: '#5a5a6e', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
            },
        },
    });
}

// ---- Strategy Table ----
function renderTable(strategies) {
    const tbody = $('#strategyTableBody');
    const top = strategies.slice(0, 20);
    
    tbody.innerHTML = top.map(s => {
        const rankClass = s.rank <= 3 ? `rank-${s.rank}` : '';
        const deltaClass = s.delta_to_best === 0 ? 'delta-zero' : 'delta-positive';
        const mean_m = Math.floor(s.mean_time / 60);
        const mean_s = (s.mean_time % 60).toFixed(1);
        const best_m = Math.floor(s.best_case / 60);
        const best_s = (s.best_case % 60).toFixed(1);
        const worst_m = Math.floor(s.worst_case / 60);
        const worst_s = (s.worst_case % 60).toFixed(1);

        return `<tr>
            <td class="rank-cell ${rankClass}">${s.rank}</td>
            <td>${s.name}</td>
            <td>${s.stops}</td>
            <td>${mean_m}:${mean_s.padStart(4, '0')}</td>
            <td>${s.std_time.toFixed(1)}s</td>
            <td>${best_m}:${best_s.padStart(4, '0')}</td>
            <td>${worst_m}:${worst_s.padStart(4, '0')}</td>
            <td>${s.score.toFixed(1)}</td>
            <td class="${deltaClass}">+${s.delta_to_best.toFixed(1)}s</td>
        </tr>`;
    }).join('');

    $('#stratCount').textContent = `${strategies.length} strategies`;
}

// ---- Insights ----
function renderInsights(insights) {
    const list = $('#insightsList');
    if (!insights || !insights.length) {
        list.innerHTML = '<p class="insight-placeholder">No insights generated.</p>';
        return;
    }
    list.innerHTML = insights.map(text => 
        `<div class="insight-item">${text}</div>`
    ).join('');
}

// ---- Sensitivity Analysis ----
async function runSensitivity() {
    if (!currentResults || !currentResults.optimal) {
        alert('Run a simulation first to get an optimal strategy.');
        return;
    }

    const btn = $('#sensitivityBtn');
    btn.disabled = true;
    showLoading(true, 'Running Sensitivity Analysis...', 'Testing parameter variations');

    try {
        const payload = {
            track: $('#trackSelect').value,
            n_simulations: Math.min(parseInt($('#simCount').value), 1000),
            aggression: parseFloat($('#aggressionSlider').value),
            strategy: currentResults.optimal.strategy,
        };

        const res = await fetch(`/api/sensitivity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data = await res.json();
        renderSensitivity(data);
        $('#sensitivitySection').classList.remove('hidden');
    } catch (err) {
        console.error('Sensitivity error:', err);
        alert('Sensitivity analysis failed.');
    } finally {
        btn.disabled = false;
        showLoading(false);
    }
}

function renderSensitivity(data) {
    // Degradation sensitivity
    destroyChart('sensDeg');
    const degCtx = $('#sensDegChart').getContext('2d');
    charts.sensDeg = new Chart(degCtx, {
        type: 'line',
        data: {
            labels: data.degradation.map(d => `${d.degradation_multiplier}x`),
            datasets: [{
                label: 'Score',
                data: data.degradation.map(d => d.score),
                borderColor: '#FF6B35',
                backgroundColor: 'rgba(255, 107, 53, 0.1)',
                borderWidth: 2,
                pointRadius: 4,
                pointBackgroundColor: '#FF6B35',
                fill: true,
                tension: 0.3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { title: { display: true, text: 'Degradation Multiplier', color: '#5a5a6e', font: { size: 9 } }, grid: { display: false } },
                y: { title: { display: true, text: 'Strategy Score', color: '#5a5a6e', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
            },
        },
    });

    // Safety car sensitivity
    destroyChart('sensSC');
    const scCtx = $('#sensSCChart').getContext('2d');
    charts.sensSC = new Chart(scCtx, {
        type: 'line',
        data: {
            labels: data.safety_car.map(d => `${(d.sc_probability * 100).toFixed(0)}%`),
            datasets: [{
                label: 'Score',
                data: data.safety_car.map(d => d.score),
                borderColor: '#2979FF',
                backgroundColor: 'rgba(41, 121, 255, 0.1)',
                borderWidth: 2,
                pointRadius: 4,
                pointBackgroundColor: '#2979FF',
                fill: true,
                tension: 0.3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { title: { display: true, text: 'SC Probability', color: '#5a5a6e', font: { size: 9 } }, grid: { display: false } },
                y: { title: { display: true, text: 'Strategy Score', color: '#5a5a6e', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
            },
        },
    });

    // Weather sensitivity
    destroyChart('sensWx');
    const wxCtx = $('#sensWxChart').getContext('2d');
    charts.sensWx = new Chart(wxCtx, {
        type: 'bar',
        data: {
            labels: data.weather.map(d => d.condition.replace('_', ' ')),
            datasets: [{
                label: 'Score',
                data: data.weather.map(d => d.score),
                backgroundColor: ['rgba(0, 200, 83, 0.6)', 'rgba(255, 214, 0, 0.6)', 'rgba(41, 121, 255, 0.6)', 'rgba(225, 6, 0, 0.6)'],
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { title: { display: true, text: 'Strategy Score', color: '#5a5a6e', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
            },
        },
    });
}

// ---- Utility ----
function showLoading(show, text, sub) {
    const overlay = $('#loadingOverlay');
    if (show) {
        overlay.classList.remove('hidden');
        if (text) $('.loading-text').textContent = text;
        if (sub) $('#loadingSub').textContent = sub;
    } else {
        overlay.classList.add('hidden');
    }
}

function setStatus(state, text) {
    const indicator = $('#statusIndicator');
    indicator.className = `status-indicator ${state}`;
    indicator.querySelector('.status-text').textContent = text;
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = (seconds % 60).toFixed(1);
    return `${m}:${s.padStart(4, '0')}`;
}

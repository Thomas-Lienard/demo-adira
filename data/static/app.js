let chatChartCount = 0;
let semanticData = null;
let semanticEnabled = false;
let callsEnabled = false;

// ===== Init =====
document.addEventListener('DOMContentLoaded', async () => {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
    document.querySelector('.nav-brand').addEventListener('click', () => switchTab('chat'));

    const input = document.getElementById('questionInput');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitQuestion();
        }
    });
    input.addEventListener('input', autoResize);

    try {
        const semanticRes = await fetch('/semantic');
        if (semanticRes.ok) {
            semanticData = await semanticRes.json();
            initCatalog(semanticData);
            initSuggestions(semanticData.suggested_questions || []);
        }
    } catch (err) {
        console.error('Failed to load semantic data:', err);
    }

    try {
        await loadDocumentsList();
    } catch (err) {
        console.error('Failed to load documents:', err);
    }
});

// ===== Tabs =====
function switchTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(`tab-${tabId}`).classList.add('active');
}

// ===== Toggle selector =====
function toggleOption(option) {
    if (option === 'semantic') {
        semanticEnabled = !semanticEnabled;
        if (!semanticEnabled) callsEnabled = false;
    } else {
        callsEnabled = !callsEnabled;
        if (callsEnabled) semanticEnabled = true;
    }
    document.getElementById('toggleSemantic').classList.toggle('active', semanticEnabled);
    document.getElementById('toggleCalls').classList.toggle('active', callsEnabled);
}

// ===== Catalog =====
function initCatalog(data) {
    const metricsGrid = document.getElementById('metricsGrid');
    const dimsGrid = document.getElementById('dimensionsGrid');
    const rulesGrid = document.getElementById('rulesGrid');

    Object.entries(data.metrics || {}).forEach(([key, m]) => {
        metricsGrid.innerHTML += `
            <div class="catalog-card">
                <div class="catalog-card-header">
                    <div class="catalog-card-icon metric">◇</div>
                    <span class="catalog-card-title">${escapeHtml(m.label)}</span>
                </div>
                <div class="catalog-card-desc">${escapeHtml(m.description)}</div>
                <code class="catalog-card-sql">${escapeHtml(m.sql)}</code>
                <div class="catalog-card-tags">
                    ${(m.concepts || []).map(c => `<span class="catalog-tag">${escapeHtml(c)}</span>`).join('')}
                    ${m.unit ? `<span class="catalog-tag">${escapeHtml(m.unit)}</span>` : ''}
                </div>
            </div>`;
    });

    Object.entries(data.dimensions || {}).forEach(([key, d]) => {
        dimsGrid.innerHTML += `
            <div class="catalog-card">
                <div class="catalog-card-header">
                    <div class="catalog-card-icon dimension">▦</div>
                    <span class="catalog-card-title">${escapeHtml(d.label)}</span>
                </div>
                <code class="catalog-card-sql">GROUP BY ${escapeHtml(d.group_by)}</code>
                <div class="catalog-card-tags">
                    ${(d.concepts || []).map(c => `<span class="catalog-tag">${escapeHtml(c)}</span>`).join('')}
                </div>
            </div>`;
    });

    (data.business_rules || []).forEach(r => {
        rulesGrid.innerHTML += `
            <div class="catalog-card">
                <div class="catalog-card-header">
                    <div class="catalog-card-icon rule">✓</div>
                    <span class="catalog-card-title">${escapeHtml(r.name)}</span>
                </div>
                <div class="catalog-card-desc">${escapeHtml(r.description)}</div>
                ${r.filter ? `<code class="catalog-card-sql">WHERE ${escapeHtml(r.filter)}</code>` : ''}
            </div>`;
    });
}

// ===== Suggestions =====
function initSuggestions(questions) {
    const container = document.getElementById('suggestions');
    questions.forEach(q => {
        const chip = document.createElement('button');
        chip.className = 'suggestion-chip';
        chip.textContent = q;
        chip.onclick = () => {
            document.getElementById('questionInput').value = q;
            switchTab('chat');
            setTimeout(() => submitQuestion(), 200);
        };
        container.appendChild(chip);
    });
}

// ===== Documents (before/after) =====
async function loadDocumentsList() {
    const res = await fetch('/documents');
    if (!res.ok) return;
    const docs = await res.json();
    const list = document.getElementById('documentsList');
    list.innerHTML = '';
    docs.forEach(doc => {
        const icon = doc.type === 'transcription' ? '📞' : '🎫';
        const el = document.createElement('div');
        el.className = 'doc-list-item';
        el.innerHTML = `
            <span class="doc-icon">${icon}</span>
            <div>
                <div class="doc-id">${doc.id}</div>
                <div class="doc-meta">${doc.metadata.client || ''} - ${doc.metadata.region || ''}</div>
            </div>`;
        el.onclick = (e) => loadDocument(doc.id, e);
        list.appendChild(el);
    });
}

async function loadDocument(docId, evt) {
    const res = await fetch(`/documents/${docId}`);
    if (!res.ok) return;
    const doc = await res.json();
    const viewer = document.getElementById('documentsViewer');

    const fieldsHtml = Object.entries(doc.extracted_fields || {}).map(([k, v]) => `
        <tr><td class="field-name">${k}</td><td class="field-value">${v === null ? '—' : v}</td></tr>
    `).join('');

    viewer.innerHTML = `
        <div class="viewer-split">
            <div class="viewer-pane viewer-raw">
                <div class="viewer-pane-header">Document brut</div>
                <pre class="raw-text">${escapeHtml(doc.raw_text)}</pre>
            </div>
            <div class="viewer-arrow">→</div>
            <div class="viewer-pane viewer-extracted">
                <div class="viewer-pane-header">Champs extraits par le pipeline IA</div>
                <table class="extracted-table">
                    <thead><tr><th>Champ</th><th>Valeur extraite</th></tr></thead>
                    <tbody>${fieldsHtml}</tbody>
                </table>
            </div>
        </div>`;

    document.querySelectorAll('.doc-list-item').forEach(el => el.classList.remove('active'));
    evt.currentTarget.classList.add('active');
}

// ===== Chat =====
function autoResize() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}

function detectWarnings(sql) {
    const warnings = [];
    if (!sql) return [{ text: 'Aucun SQL genere' }];
    const sqlLower = (sql || '').toLowerCase();
    if (sqlLower.includes('tbl_') || sqlLower.includes('_cd') || sqlLower.includes('_nm')) {
        warnings.push({ text: 'Utilise des noms de colonnes cryptiques (schema brut)' });
    }
    if (!sqlLower.includes(' as ')) {
        warnings.push({ text: "Pas d'aliases lisibles pour les colonnes" });
    }
    warnings.push({ text: 'Pas de concepts metier identifies' });
    warnings.push({ text: 'Pas de regles metier appliquees' });
    return warnings;
}

function buildNoSemanticHtml(res) {
    const chartId = `chart-nosem-${++chatChartCount}`;
    let html = '<div class="chat-msg chat-msg-ai">';


    if (res.error) {
        html += `<div class="indicator indicator-error">⚠ Erreur SQL : ${escapeHtml(res.error)}</div>`;
    }

    if (res.explanation) {
        html += `<div class="chat-bubble">${escapeHtml(res.explanation)}</div>`;
    }

    const hasChart = res.results?.length && res.chart_type && res.chart_type !== 'table' && res.chart_type !== 'number';
    if (hasChart) {
        html += `<div class="chat-chart-card"><div class="chat-chart-title">${escapeHtml(res.chart_config?.title || '')}</div><div class="chat-chart-container"><canvas id="${chartId}"></canvas></div></div>`;
    }

    if (res.sql) {
        html += `<details><summary class="chat-sql-toggle">◆ Voir la requete SQL</summary><div class="chat-sql-block">${escapeHtml(res.sql)}</div></details>`;
    }

    if (res.results != null) {
        const tableOpen = res.chart_type === 'table' || res.chart_type === 'number' || !(res.results || []).length ? ' open' : '';
        html += `<details${tableOpen}><summary class="chat-sql-toggle">◆ Voir les donnees (${(res.results || []).length} lignes)</summary>${buildTable(res.results || [])}</details>`;
    }

    html += '</div>';
    return { html, chartId: hasChart ? chartId : null, chartData: hasChart ? res : null };
}

function buildCrossAnalysisHtml(data) {
    let html = '<div class="chat-msg chat-msg-ai cross-analysis">';

    // Synthesis
    html += `<div class="cross-synthesis">${escapeHtml(data.synthesis).replace(/\n/g, '<br>')}</div>`;

    // Sources
    if (data.sources && data.sources.length) {
        html += '<div class="cross-sources">';
        const icons = { structured: '📊', calls: '📞', tickets: '🎫' };
        data.sources.forEach(s => {
            html += `<div class="source-card source-${s.type}">
                <div class="source-header"><span class="source-icon">${icons[s.type] || '📊'}</span> ${escapeHtml(s.label)}</div>
                <div class="source-finding">${escapeHtml(s.finding)}</div>
            </div>`;
        });
        html += '</div>';
    }

    // Individual query details
    if (data.queries && data.queries.length) {
        html += '<details><summary class="chat-sql-toggle">◆ Detail des requetes executees</summary>';
        data.queries.forEach(q => {
            html += `<div class="query-detail">
                <div class="query-source">${escapeHtml(q.source)}</div>
                <div class="chat-sql-block">${escapeHtml(q.sql)}</div>
                ${q.results ? buildTable(q.results) : ''}
            </div>`;
        });
        html += '</details>';
    }

    // Chart from first structured query results
    const chartId = `cross-chart-${++chatChartCount}`;
    const firstResults = data.results || [];
    if (firstResults.length && data.chart_type && data.chart_type !== 'table') {
        html += `<div class="chat-chart-card"><div class="chat-chart-title">${escapeHtml(data.chart_config?.title || '')}</div><div class="chat-chart-container"><canvas id="${chartId}"></canvas></div></div>`;
    }

    html += '</div>';
    return { html, chartId: firstResults.length ? chartId : null, chartData: firstResults.length ? data : null };
}

function fetchSSE(url, question) {
    return new Promise((resolve, reject) => {
        const loadingId = 'loading-' + Date.now();
        const messages = document.getElementById('chatMessages');
        messages.innerHTML += `<div class="chat-msg chat-msg-ai" id="${loadingId}"><div class="chat-loading"><div class="dot-pulse"><span></span><span></span><span></span></div><span class="loading-step">Demarrage...</span></div></div>`;
        scrollToBottom();

        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        }).then(response => {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processEvents(text) {
                const parts = text.split('\n\n');
                const remainder = parts.pop();
                for (const part of parts) {
                    const lines = part.split('\n');
                    let eventType = '';
                    let eventData = '';
                    for (const line of lines) {
                        if (line.startsWith('event: ')) eventType = line.slice(7);
                        else if (line.startsWith('data: ')) eventData = line.slice(6);
                    }

                    if (eventType === 'step') {
                        const stepEl = document.querySelector(`#${loadingId} .loading-step`);
                        if (stepEl) {
                            const step = JSON.parse(eventData);
                            stepEl.textContent = step.message;
                            scrollToBottom();
                        }
                    } else if (eventType === 'result') {
                        document.getElementById(loadingId)?.remove();
                        resolve(JSON.parse(eventData));
                        return true;
                    }
                }
                return remainder;
            }

            function pump() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        buffer += decoder.decode();
                        if (buffer.trim()) {
                            const found = processEvents(buffer + '\n\n');
                            if (found === true) return;
                        }
                        document.getElementById(loadingId)?.remove();
                        reject(new Error('Stream ended without result'));
                        return;
                    }
                    buffer += decoder.decode(value, { stream: true });
                    const result = processEvents(buffer);
                    if (result === true) return;
                    buffer = result;
                    pump();
                }).catch(err => {
                    document.getElementById(loadingId)?.remove();
                    reject(err);
                });
            }
            pump();
        }).catch(err => {
            document.getElementById(loadingId)?.remove();
            reject(err);
        });
    });
}

async function submitQuestion() {
    const input = document.getElementById('questionInput');
    const question = input.value.trim();
    if (!question) return;

    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    input.value = '';
    input.style.height = 'auto';

    const welcome = document.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const messages = document.getElementById('chatMessages');
    messages.innerHTML += `<div class="chat-msg chat-msg-user"><div class="chat-bubble">${escapeHtml(question)}</div></div>`;
    scrollToBottom();

    try {
        if (semanticEnabled && callsEnabled) {
            const data = await fetchSSE('/query/cross', question);
            const { html, chartId, chartData } = buildCrossAnalysisHtml(data);
            messages.innerHTML += html;
            if (chartId) setTimeout(() => renderChart(chartId, chartData), 50);

        } else if (semanticEnabled) {
            const res = await fetchSSE('/query', question);

            const chartId = `chart-${++chatChartCount}`;
            let html = '<div class="chat-msg chat-msg-ai">';
            if (res.matched_concepts?.length) {
                html += `<div class="concepts-row">${res.matched_concepts.map(c => `<span class="concept-pill">${c}</span>`).join('')}</div>`;
            }
            html += `<div class="chat-bubble">${escapeHtml(res.summary)}</div>`;
            if (res.results?.length && res.chart_type !== 'table' && res.chart_type !== 'number') {
                html += `<div class="chat-chart-card"><div class="chat-chart-title">${escapeHtml(res.chart_config?.title || '')}</div><div class="chat-chart-container"><canvas id="${chartId}"></canvas></div></div>`;
            }
            html += `<details><summary class="chat-sql-toggle">◆ Voir la requete SQL</summary><div class="chat-sql-block">${escapeHtml(res.sql)}</div></details>`;
            if (res.results != null) {
                const tableOpen = res.chart_type === 'table' || res.chart_type === 'number' || !res.results.length ? ' open' : '';
                html += `<details${tableOpen}><summary class="chat-sql-toggle">◆ Voir les donnees (${res.results.length} lignes)</summary>${buildTable(res.results)}</details>`;
            }
            html += '</div>';
            messages.innerHTML += html;
            if (res.results?.length && res.chart_type !== 'table' && res.chart_type !== 'number') {
                setTimeout(() => renderChart(chartId, res), 50);
            }

        } else {
            const res = await fetchSSE('/query/no-semantic', question);
            const { html, chartId, chartData } = buildNoSemanticHtml(res);
            messages.innerHTML += html;
            if (chartId) setTimeout(() => renderChart(chartId, chartData), 50);
        }
    } catch (err) {
        messages.innerHTML += `<div class="chat-msg chat-msg-ai"><div class="chat-bubble" style="color:var(--pink)">Erreur : ${escapeHtml(err.message)}</div></div>`;
    }

    scrollToBottom();
    btn.disabled = false;
}

function scrollToBottom() {
    const el = document.getElementById('chatMessages');
    el.scrollTop = el.scrollHeight;
}

// ===== Chart =====
function renderChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const results = data.results || [];
    if (!results.length) return;
    const config = data.chart_config || {};
    const chartType = data.chart_type || 'bar';
    const keys = Object.keys(results[0]);
    const xKey = config.x || keys[0];
    const yKey = config.y || keys[keys.length - 1];
    const labels = results.map(r => formatLabel(r[xKey]));
    const values = results.map(r => parseFloat(r[yKey]) || 0);
    const colors = ['#a78bfa', '#60a5fa', '#f472b6', '#4ade80', '#fb923c', '#22d3ee', '#fbbf24', '#e879f9', '#34d399', '#f87171'];

    new Chart(ctx, {
        type: chartType === 'line' ? 'line' : chartType === 'pie' ? 'pie' : 'bar',
        data: {
            labels,
            datasets: [{
                label: config.title || yKey,
                data: values,
                backgroundColor: chartType === 'pie' ? colors.slice(0, values.length) : 'rgba(167, 139, 250, 0.5)',
                borderColor: chartType === 'line' ? '#a78bfa' : 'transparent',
                borderWidth: chartType === 'line' ? 2 : 0,
                borderRadius: chartType === 'bar' ? 6 : 0,
                tension: 0.35, fill: chartType === 'line',
                pointRadius: chartType === 'line' ? 3 : 0, pointBackgroundColor: '#a78bfa',
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: chartType === 'pie', labels: { color: '#52525b', font: { family: 'Inter', size: 11 } } }, title: { display: false } },
            scales: chartType === 'pie' ? {} : {
                x: { ticks: { color: '#71717a', font: { size: 10 }, maxRotation: 45 }, grid: { color: 'rgba(212,212,216,0.5)' } },
                y: { ticks: { color: '#71717a', font: { size: 10 }, callback: v => formatNumber(v) }, grid: { color: 'rgba(212,212,216,0.5)' } }
            }
        }
    });
}

// ===== Table =====
function buildTable(results) {
    if (!results || !results.length) return '<p class="text-muted">Aucun resultat</p>';
    const keys = Object.keys(results[0]);
    const maxRows = 15;
    let html = '<table class="chat-data-table"><thead><tr>';
    keys.forEach(k => html += `<th>${k}</th>`);
    html += '</tr></thead><tbody>';
    results.slice(0, maxRows).forEach(row => {
        html += '<tr>';
        keys.forEach(k => html += `<td>${formatValue(row[k])}</td>`);
        html += '</tr>';
    });
    html += '</tbody></table>';
    if (results.length > maxRows) html += `<p class="text-muted" style="padding:8px">... et ${results.length - maxRows} lignes de plus</p>`;
    return html;
}

// ===== Utils =====
function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function formatLabel(v) { if (v == null) return '—'; const s = String(v); return s.length > 25 ? s.substring(0, 22) + '...' : s; }
function formatValue(v) { if (v == null) return '—'; if (typeof v === 'number') return formatNumber(v); return String(v); }
function formatNumber(n) {
    if (typeof n !== 'number') return n;
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    if (Number.isInteger(n)) return n.toLocaleString('fr-FR');
    return n.toFixed(2);
}

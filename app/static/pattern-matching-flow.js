const PatternMatchingFlow = {
    tree: null,
    bunsetsuList: null,
    patterns: null,

    async init(tree, bunsetsuList) {
        this.tree = tree;
        this.bunsetsuList = bunsetsuList;

        this.patterns = await this.fetchPatterns();
        if (!this.patterns) {
            this.showError('パターン情報の取得に失敗しました');
            return;
        }

        const result = await this.callMatchingAPI(null);
        const patternStatus = result.pattern_status || {};

        this.renderPatternPanel(patternStatus);
        document.getElementById('matching-results-content').innerHTML =
            '<p class="empty-state">パターンを選択してください</p>';
    },

    async fetchPatterns() {
        try {
            const response = await fetch('/api/patterns');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return (await response.json()).patterns || {};
        } catch (error) {
            console.error('[PatternMatching] Error fetching patterns:', error);
            return null;
        }
    },

    async callMatchingAPI(selectedPatternIds) {
        const requestBody = {
            tree: this.tree,
            bunsetsu_list: this.bunsetsuList
        };

        if (selectedPatternIds && selectedPatternIds.length > 0) {
            requestBody.selected_patterns = selectedPatternIds.map(id => parseInt(id));
        }

        try {
            const response = await fetch('/api/matching', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[PatternMatching] API error:', error);
            return { status: 'error', triples: [], matched_patterns: [] };
        }
    },

    renderPatternPanel(patternStatus) {
        const section = document.getElementById('pattern-matching-section');
        if (!section) return;

        const byStatus = { light: [], disabled: [] };
        for (const [id, pattern] of Object.entries(this.patterns)) {
            const status = patternStatus[id] || 'dark_gray';
            const key = status === 'light' ? 'light' : 'disabled';
            byStatus[key].push([id, pattern]);
        }

        for (const key of ['light', 'disabled']) {
            byStatus[key].sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
        }

        let html = '<div class="section"><h2>Pattern Matching</h2>';
        html += '<div id="cell-matching-section"><div class="pattern-matching-layout">';

        html += '<div class="pattern-selector-panel">';
        html += '<div class="panel-header"><h3>Pattern Selection</h3><div class="status-badge">Check Complete</div></div>';
        html += '<div class="pattern-controls">';
        html += '<button class="control-btn" onclick="PatternMatchingFlow.selectMatched()">Select Matched</button>';
        html += '<button class="control-btn" onclick="PatternMatchingFlow.deselectAll()">Deselect All</button>';
        html += '</div><div class="pattern-list">';

        for (const [status, label] of [['light', '✓ Matched'], ['disabled', '✗ Not Matched']]) {
            const items = byStatus[status];
            if (items.length === 0) continue;

            html += `<div class="pattern-group" data-status="${status}"><h4>${label} (${items.length})</h4>`;
            for (const [id, pattern] of items) {
                const patternStr = pattern.representative_pattern || pattern;
                html += `<label class="pattern-checkbox ${status}" data-pattern-id="${id}">`;
                html += `<input type="checkbox" value="${id}" onchange="PatternMatchingFlow.onCheckboxChange()" />`;
                html += `<span class="status-indicator"></span>`;
                html += `<span class="pattern-text">${this.escapeHtml(patternStr)}</span>`;
                html += `</label>`;
            }
            html += '</div>';
        }

        html += '</div></div>';
        html += '<div class="matching-results-panel"><h3>Matching Results</h3>';
        html += '<div id="matching-results-content"><p class="empty-state">Pattern Select</p></div>';
        html += '</div></div></div></div>';

        section.innerHTML = html;
        section.style.display = 'block';
    },

    async onCheckboxChange() {
        const selectedIds = Array.from(
            document.querySelectorAll('.pattern-checkbox input:checked')
        ).map(cb => cb.value);

        if (selectedIds.length === 0) {
            document.getElementById('matching-results-content').innerHTML =
                '<p class="empty-state">Pattern Select</p>';
            return;
        }

        const result = await this.callMatchingAPI(selectedIds);
        this.renderResults(result);
    },

    deselectAll() {
        document.querySelectorAll('.pattern-checkbox input:checked').forEach(cb => cb.checked = false);
        document.getElementById('matching-results-content').innerHTML =
            '<p class="empty-state">Pattern Select</p>';
    },

    selectMatched() {
        document.querySelectorAll('.pattern-checkbox.light input').forEach(cb => cb.checked = true);
        this.onCheckboxChange();
    },

    renderResults(result) {
        const content = document.getElementById('matching-results-content');
        if (!content) return;

        const triples = result.triples || [];
        if (triples.length === 0) {
            content.innerHTML = '<p class="empty-state">No matching triples found</p>';
            return;
        }

        const ontology = window.getOntologyEditorState ? window.getOntologyEditorState() : null;
        if (window.initializeSemanticVerify) {
            window.initializeSemanticVerify(triples, ontology?.relations || []);
        }

        let html = `<div class="triples-summary"><p>Extracted Triples: <strong>${triples.length}</strong></p></div>`;
        html += '<div class="triples-list">';

        triples.forEach((triple, idx) => {
            const subject = triple.subject || triple[0] || '';
            const predicate = triple.predicate || triple[1] || '';
            const object = triple.object || triple[2] || '';
            const pattern = triple.pattern || '';
            const patternId = triple.pattern_id || '';
            const bindings = triple.bindings || {};

            const coreSlots = {};
            for (const key in bindings) {
                if (/^[XY]\d+$/.test(key)) coreSlots[key] = bindings[key];
            }

            html += '<div class="triple-item">';
            html += '<div class="triple-source-info">';
            html += `<span class="pattern-label">Pattern:</span>`;
            html += `<span class="pattern-id">P${this.escapeHtml(String(patternId))}</span>`;
            html += `<span class="pattern-text">${this.escapeHtml(pattern)}</span>`;
            html += '</div>';

            if (Object.keys(coreSlots).length > 0) {
                html += '<div class="slots-row">';
                for (const [name, value] of Object.entries(coreSlots)) {
                    html += `<div class="slot"><span class="slot-name">${this.escapeHtml(name)}</span><span class="slot-value">${this.escapeHtml(value)}</span></div>`;
                }
                html += '</div>';
            }

            html += '<div class="triple-values-row">';
            html += `<span class="triple-val label-s">S</span><span class="triple-val">${this.escapeHtml(subject || '-')}</span>`;
            html += `<span class="triple-val label-p">P</span><span class="triple-val">${this.escapeHtml(predicate || '-')}</span>`;
            html += `<span class="triple-val label-o">O</span><span class="triple-val">${this.escapeHtml(object || '-')}</span>`;
            const tripleJson = JSON.stringify({subject, predicate, object});
            html += `<button class="btn-verify" onclick="window.selectTripleForVerification(${tripleJson.replace(/"/g, '&quot;')})">検証</button>`;
            html += '</div></div>';
        });

        html += '</div>';
        content.innerHTML = html;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    showError(message) {
        const container = document.getElementById('cell-matching-section');
        if (container) {
            container.innerHTML = `<div style="padding: 20px; color: #cc0000;"><strong>エラー:</strong> ${this.escapeHtml(message)}</div>`;
        }
    }
};

window.PatternMatchingFlow = PatternMatchingFlow;
window.displayMatchingPanel = (tree, bunsetsuList) => PatternMatchingFlow.init(tree, bunsetsuList);

let state = {
    sentences: [],
    currentSentenceIndex: 0,
    selectedBunsetuIndex: null
};

function getCurrentSentenceData() {
    return state.sentences.length > 0 ? state.sentences[state.currentSentenceIndex] : null;
}

function getCurrentData() {
    const sent = getCurrentSentenceData();
    return sent ? sent.data : null;
}

function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function setState(patch, render = true) {
    state = typeof patch === 'function' ? patch(state) : Object.assign({}, state, patch);
    if (render) renderAll();
}

function updateCurrentSentence(updater) {
    const idx = state.currentSentenceIndex;
    if (idx < 0 || idx >= state.sentences.length) return;
    const sentences = deepClone(state.sentences);
    sentences[idx] = typeof updater === 'function' ? updater(sentences[idx]) : Object.assign({}, sentences[idx], updater);
    setState({ sentences }, false);
}

function renderAll() {
    renderSentenceSelector();
    renderBunsetsuList();
    renderEditor();
}

async function apiBunsetuWithRetry(text, attempts = 3) {
    if (!text || String(text).trim().length === 0) throw new Error('送信テキストが空です');
    let lastErr = new Error('API エラー');
    for (let i = 0; i < attempts; i++) {
        try {
            const resp = await API.bunsetu(text);
            if (resp && Array.isArray(resp) && resp.length > 0) return resp;
            lastErr = new Error('空のレスポンス');
        } catch (err) {
            lastErr = err;
        }
        if (i < attempts - 1) await new Promise(r => setTimeout(r, 600));
    }
    throw lastErr;
}

function init() {
    DOM.on('#submit-btn', 'click', handleSubmit);
    DOM.on('#editor-area', 'click', handleEditorClick);
    DOM.on('#send-to-cky-btn', 'click', handleSendToCKY);
    renderAll();
}

function handleEditorClick(e) {
    const morphBtn = e.target.closest('.morph-btn');
    if (morphBtn) {
        const bunsetuIdx = parseInt(morphBtn.dataset.bunsetuIndex);
        const morphIdx = parseInt(morphBtn.dataset.morphIndex);
        if (morphIdx > 0) splitBunsetsuAt(bunsetuIdx, morphIdx);
        return;
    }

    const ctrl = e.target.closest('.control-btn');
    if (ctrl) {
        e.stopPropagation();
        const bunsetuIdx = parseInt(ctrl.dataset.bunsetsuIndex);
        const action = ctrl.dataset.action;
        if (action === 'merge-prev') mergePrev(bunsetuIdx);
        else if (action === 'merge-next') mergeNext(bunsetuIdx);
        else if (action === 'split') splitBunsetsu(bunsetuIdx);
    }
}

async function handleSubmit() {
    const text = DOM.get('#input-text').value.trim();
    if (!text) return;

    try {
        const sentenceTexts = text.split('。').filter(s => s.trim().length > 0);
        const newSentences = [];

        for (const sentText of sentenceTexts) {
            try {
                const resp = await apiBunsetuWithRetry(sentText.trim(), 3);
                const originalData = deepClone(resp);
                const data = deepClone(resp);
                data.forEach(item => {
                    item.bunsetu.forEach(m => { m.originalType = m.type; });
                });
                newSentences.push({ text: sentText, originalData, data, status: 'ready' });
            } catch (err) {
                newSentences.push({ text: sentText, originalData: null, data: null, status: 'pending' });
            }
        }

        setState({ sentences: newSentences, currentSentenceIndex: 0, selectedBunsetuIndex: null }, false);
        commitChanges();
    } catch (error) {
        console.error('送信エラー');
    }
}

function renderBunsetsuList() {
    const list = DOM.get('#bunsetsu-list');
    const data = getCurrentData();

    if (!data || data.length === 0) {
        list.innerHTML = '<li class="empty-state">Not Parsed</li>';
        return;
    }

    list.innerHTML = '';
    data.forEach((item, index) => {
        const li = document.createElement('li');
        li.className = 'bunsetsu-item' + (state.selectedBunsetuIndex === index ? ' active' : '');
        const text = item.bunsetu.map(m => m.text).join('');
        li.innerHTML = `<span class="token-label">${index}:</span> ${text}`;
        li.addEventListener('click', () => selectBunsetsu(index));
        list.appendChild(li);
    });
}

function renderSentenceSelector() {
    const selector = DOM.get('#sentence-selector');
    if (!selector) return;

    selector.innerHTML = '';
    state.sentences.forEach((sent, index) => {
        const btn = document.createElement('button');
        btn.className = 'sentence-btn' + (index === state.currentSentenceIndex ? ' active' : '');
        btn.textContent = `${index + 1}. ${sent.text.substring(0, 15)}${sent.text.length > 15 ? '...' : ''}`;
        btn.addEventListener('click', () => selectSentence(index));
        selector.appendChild(btn);
    });
}

function selectBunsetsu(index) {
    setState({ selectedBunsetuIndex: index }, false);
    commitChanges();
}

async function selectSentence(index) {
    if (index < 0 || index >= state.sentences.length) return;

    setState({ currentSentenceIndex: index, selectedBunsetuIndex: null }, false);
    const sent = state.sentences[index];

    if (!sent.data || sent.data.length === 0) {
        try {
            const resp = await apiBunsetuWithRetry(sent.text, 3);
            updateCurrentSentence(s => {
                const copy = deepClone(s);
                copy.originalData = deepClone(resp);
                copy.data = deepClone(resp);
                copy.status = 'ready';
                copy.data.forEach(item => {
                    item.bunsetu.forEach(m => { m.originalType = m.type; });
                });
                return copy;
            });
            commitChanges();
        } catch (error) {
            DOM.get('#bunsetsu-list').innerHTML = '<li class="empty-state">Not Parsed</li>';
            renderAll();
        }
        return;
    }

    commitChanges();
}

function renderEditor() {
    const area = DOM.get('#editor-area');
    const data = getCurrentData();

    if (!data || data.length === 0) {
        area.innerHTML = '<div class="empty-state">Please enter text</div>';
        return;
    }

    let html = '<div class="editor-grid">';

    data.forEach((item, bunsetuIndex) => {
        const isActive = bunsetuIndex === state.selectedBunsetuIndex ? 'active' : '';

        html += `<div class="bunsetsu-editor ${isActive}" data-bunsetsu-index="${bunsetuIndex}">
            <div class="bunsetsu-header"><h3>#${bunsetuIndex}</h3></div>
            <div class="morphs-group">`;

        item.bunsetu.forEach((morph, morphIndex) => {
            const typeClass = morph.type === 'func' ? 'func' : morph.type === 'sahen' ? 'sahen' : '';
            html += `<button class="morph-btn ${typeClass}" data-bunsetsu-index="${bunsetuIndex}" data-morph-index="${morphIndex}">${morph.text}</button>`;
        });

        html += `</div>
            <div class="grouping-controls">
                <button class="control-btn" data-bunsetsu-index="${bunsetuIndex}" data-action="merge-prev">Merge (Previous)</button>
                <button class="control-btn" data-bunsetsu-index="${bunsetuIndex}" data-action="merge-next">Merge (Next)</button>
                <button class="control-btn" data-bunsetsu-index="${bunsetuIndex}" data-action="split">Split</button>
            </div>
        </div>`;
    });

    html += '</div>';
    area.innerHTML = html;
}

function splitBunsetsu(bunsetuIdx) {
    const data = getCurrentData();
    if (!data || !data[bunsetuIdx] || data[bunsetuIdx].bunsetu.length <= 1) return;

    const item = data[bunsetuIdx];
    const newItems = item.bunsetu.map(m => ({ bunsetu: [m] }));
    const newData = deepClone(data);
    newData.splice(bunsetuIdx, 1, ...newItems);

    updateCurrentSentence(s => Object.assign({}, s, { data: newData }));
    setState({ selectedBunsetuIndex: bunsetuIdx }, false);
    commitChanges();
}

function splitBunsetsuAt(bunsetuIdx, morphIdx) {
    const data = getCurrentData();
    if (!data || !Number.isFinite(bunsetuIdx) || bunsetuIdx < 0 || bunsetuIdx >= data.length) return;

    const item = data[bunsetuIdx];
    if (!item || !Array.isArray(item.bunsetu) || morphIdx <= 0 || morphIdx >= item.bunsetu.length) return;

    const left = item.bunsetu.slice(0, morphIdx);
    const right = item.bunsetu.slice(morphIdx);
    const newData = deepClone(data);
    newData.splice(bunsetuIdx, 1, { bunsetu: left }, { bunsetu: right });

    updateCurrentSentence(s => Object.assign({}, s, { data: newData }));
    setState({ selectedBunsetuIndex: bunsetuIdx + 1 }, false);
    commitChanges();
}

function mergePrev(bunsetuIdx) {
    const data = getCurrentData();
    if (!data || bunsetuIdx <= 0) return;

    const newData = deepClone(data);
    newData[bunsetuIdx - 1].bunsetu = newData[bunsetuIdx - 1].bunsetu.concat(newData[bunsetuIdx].bunsetu);
    newData.splice(bunsetuIdx, 1);

    updateCurrentSentence(s => Object.assign({}, s, { data: newData }));
    setState({ selectedBunsetuIndex: bunsetuIdx - 1 }, false);
    commitChanges();
}

function mergeNext(bunsetuIdx) {
    const data = getCurrentData();
    if (!data || bunsetuIdx >= data.length - 1) return;

    const newData = deepClone(data);
    newData[bunsetuIdx].bunsetu = newData[bunsetuIdx].bunsetu.concat(newData[bunsetuIdx + 1].bunsetu);
    newData.splice(bunsetuIdx + 1, 1);

    updateCurrentSentence(s => Object.assign({}, s, { data: newData }));
    setState({ selectedBunsetuIndex: bunsetuIdx }, false);
    commitChanges();
}

function determineType(morph, bunsetuIndex, morphIndex) {
    const data = getCurrentData();
    if (!data) return morph.type;

    if (morph.originalType === 'core') return 'core';

    const bunsetu = data[bunsetuIndex].bunsetu;
    const hasPrevCore = morphIndex > 0 && bunsetu[morphIndex - 1].type === 'core';
    const hasNextCore = morphIndex < bunsetu.length - 1 && bunsetu[morphIndex + 1].type === 'core';

    if (morph.originalType === 'func' && hasPrevCore && hasNextCore) return 'core';
    return morph.originalType;
}

function updateAllMorphTypes() {
    const data = getCurrentData();
    if (!data) return;

    data.forEach((item, bunsetuIndex) => {
        item.bunsetu.forEach((morph, morphIndex) => {
            morph.type = determineType(morph, bunsetuIndex, morphIndex);
        });
    });
}

function commitChanges() {
    updateAllMorphTypes();
    renderAll();
}

async function handleSendToCKY() {
    const data = getCurrentData();
    if (!data || data.length === 0) return;

    try {
        const resp = await API.cky(data);
        if (resp?.status === 'success') {
            displayCKYResult(resp);
        } else {
            displayCKYError(resp?.message || '不明なエラー');
        }
    } catch (err) {
        displayCKYError(err.message || 'API エラー');
    }
}

document.addEventListener('DOMContentLoaded', init);

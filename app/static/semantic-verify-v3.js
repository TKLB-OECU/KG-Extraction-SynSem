let semanticVerifyState = {
    selectedTriple: null,
    step1Result: null,
    step2Result: null,
    step3Result: null,
    extractedTriples: [],
    relations: []
};

window.initializeSemanticVerify = function(triples, relations) {
    semanticVerifyState.extractedTriples = triples || [];
    semanticVerifyState.relations = relations || [];

    displayOntologyAndTriples(triples, relations);
};

function displayOntologyAndTriples(triples, relations) {
    const selector = document.getElementById('triples-selector-section');
    if (!selector) return;

    let html = '';

    if (relations && relations.length > 0) {
        html += `
            <div class="ontology-compact">
                <h3>オントロジー定義</h3>
        `;

        relations.forEach(rel => {
            html += `
                <div class="relation-item-compact">
                    <div class="label">${escapeHtml(rel.label)}</div>
                    <div class="domain-range">
                        ${escapeHtml(rel.domain)} → ${escapeHtml(rel.object_class)}
                    </div>
                </div>
            `;
        });

        html += `</div>`;
    }

    html += `
        <div class="triples-selector">
            <h3>抽出トリプル (${triples?.length || 0} 件)</h3>
            <div class="triples-list">
    `;

    if (!triples || triples.length === 0) {
        html += '<div class="empty-state">トリプルがありません</div>';
    } else {
        triples.forEach((triple, idx) => {
            const subject = triple.subject || triple[0] || '';
            const predicate = triple.predicate || triple[1] || '';
            const object = triple.object || triple[2] || '';
            const tripleStr = `(${subject}, ${predicate}, ${object})`;

            html += `
                <div class="triple-card" onclick="window.selectTripleForVerification({
                    subject: '${escapeQuote(subject)}',
                    predicate: '${escapeQuote(predicate)}',
                    object: '${escapeQuote(object)}'
                })">
                    <div class="triple-text">${escapeHtml(tripleStr)}</div>
                    <div class="triple-detail">#${idx + 1}</div>
                </div>
            `;
        });
    }

    html += `
            </div>
        </div>
    `;

    selector.innerHTML = html;
}

window.selectTripleForVerification = function(triple) {
    semanticVerifyState.selectedTriple = triple;

    window.performSemanticVerify();
};

window.performSemanticVerify = async function() {
    const triple = semanticVerifyState.selectedTriple;
    if (!triple) {
        return;
    }

    const container = document.getElementById('semantic-verify-section');
    container.innerHTML = '<div class="loading">検証実行中...</div>';

    try {
        const ontology = window.getOntologyEditorState ? window.getOntologyEditorState() : null;
        if (!ontology || !ontology.relations || ontology.relations.length === 0) {
            container.innerHTML = '<div class="error">オントロジーが未定義です</div>';
            return;
        }

        const step1Result = await performStep1_DefinitionCheck(triple, ontology.relations);
        semanticVerifyState.step1Result = step1Result;

        if (!step1Result.matched) {
            displayVerificationResults(container, step1Result, null, null);
            return;
        }

        const step2Result = await performStep2_DirectionDetection(triple, step1Result.matchedRelation);
        semanticVerifyState.step2Result = step2Result;

        if (!step2Result.valid) {
            displayVerificationResults(container, step1Result, step2Result, null);
            return;
        }

        const step3Result = await performStep3_ParaphraseVerification(
            triple,
            step2Result.pattern,
            step1Result.matchedRelation
        );
        semanticVerifyState.step3Result = step3Result;

        displayVerificationResults(container, step1Result, step2Result, step3Result);

    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<div class="error">エラー: ${error.message}</div>`;
    }
};

async function performStep1_DefinitionCheck(triple, relations) {
    try {
        const response = await fetch('/api/verify/stage1', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                triple: triple,
                relations: relations
            })
        });

        const result = await response.json();

        if (result.matched) {
            return {
                matched: true,
                matchedRelation: result.matchedRelation,
                message: result.message,
                prompt: result.prompt,
                gemini_response: result.gemini_response,
                reasoning: result.reasoning
            };
        } else {
            return {
                matched: false,
                message: result.message
            };
        }
    } catch (error) {
        return {
            matched: false,
            message: `エラー: ${error.message}`
        };
    }
}

async function performStep2_DirectionDetection(triple, relation) {
    try {
        const response = await fetch('/api/verify/stage2', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                triple: triple,
                relation: relation
            })
        });

        const result = await response.json();

        if (result.valid !== false) {
            return {
                valid: true,
                pattern: result.pattern || 'A',
                reasoning: result.reasoning || '',
                prompt: result.prompt,
                gemini_response: result.gemini_response
            };
        } else {
            return {
                valid: false,
                reasoning: result.reasoning || 'エラー'
            };
        }
    } catch (error) {
        return {
            valid: false,
            reasoning: `エラー: ${error.message}`
        };
    }
}

async function performStep3_ParaphraseVerification(triple, pattern, relation) {
    try {
        const response = await fetch('/api/verify/stage3', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                triple: triple,
                pattern: pattern,
                relation: relation
            })
        });

        const result = await response.json();

        return {
            valid: result.valid === true,
            paraphrase: result.paraphrase || '',
            reasoning: result.reasoning || '',
            conditions: result.conditions || {},
            prompt: result.prompt,
            gemini_response: result.gemini_response
        };
    } catch (error) {
        return {
            valid: false,
            paraphrase: '',
            reasoning: `エラー: ${error.message}`,
            conditions: {}
        };
    }
}

function displayVerificationResults(container, step1Result, step2Result, step3Result) {
    let html = '<div class="verify-process">';

    html += `
        <div class="step step-1 ${step1Result.matched ? 'success' : 'failure'}">
            <div class="step-header">
                <span class="step-title">Step 1: 述語定義判定</span>
                <span class="step-status ${step1Result.matched ? 'pass' : 'fail'}">
                    ${step1Result.matched ? 'PASS' : 'FAIL'}
                </span>
            </div>
            <div class="step-content">
                ${step1Result.message ? `<div class="step-info">${escapeHtml(step1Result.message)}</div>` : ''}
                ${step1Result.matchedRelation ? `
                    <div class="step-info">
                        <span class="label">マッチ:</span>
                        <span class="value">${escapeHtml(step1Result.matchedRelation.label)}
                            (${escapeHtml(step1Result.matchedRelation.domain)} → ${escapeHtml(step1Result.matchedRelation.object_class)})</span>
                    </div>
                ` : ''}
                ${step1Result.prompt ? `<button class="debug-toggle" onclick="toggleDebug(this)">プロンプト表示</button>` : ''}
            </div>
        </div>
    `;

    if (!step1Result.matched) {
        html += '</div>';
        container.innerHTML = html;
        return;
    }

    if (step2Result) {
        html += `
            <div class="step step-2 ${step2Result.valid ? 'success' : 'failure'}">
                <div class="step-header">
                    <span class="step-title">Step 2: 方向判定</span>
                    <span class="step-status ${step2Result.valid ? 'pass' : 'fail'}">
                        ${step2Result.valid ? 'PASS (P' + step2Result.pattern + ')' : 'FAIL'}
                    </span>
                </div>
                <div class="step-content">
                    ${step2Result.valid ? `
                        <div class="step-info">
                            <span class="label">パターン:</span>
                            <span class="value">${step2Result.pattern}</span>
                        </div>
                        <div class="step-info">
                            <span class="label">理由:</span>
                            <span class="value">${escapeHtml(step2Result.reasoning)}</span>
                        </div>
                    ` : `
                        <div class="step-info error">${escapeHtml(step2Result.reasoning)}</div>
                    `}
                    ${step2Result.prompt ? `<button class="debug-toggle" onclick="toggleDebug(this)">プロンプト表示</button>` : ''}
                </div>
            </div>
        `;
    }

    if (step3Result) {
        html += `
            <div class="step step-3 ${step3Result.valid ? 'success' : 'failure'}">
                <div class="step-header">
                    <span class="step-title">Step 3: パラフレーズ検証</span>
                    <span class="step-status ${step3Result.valid ? 'pass' : 'fail'}">
                        ${step3Result.valid ? 'VALID' : 'INVALID'}
                    </span>
                </div>
                <div class="step-content">
                    <div class="step-info">
                        <span class="label">言い換え:</span>
                        <span class="value">"${escapeHtml(step3Result.paraphrase)}"</span>
                    </div>
                    <div class="conditions-check">
                        <div class="condition-item ${step3Result.conditions.subject_class ? 'pass' : 'fail'}">
                            <span class="condition-icon">${step3Result.conditions.subject_class ? '✓' : '✗'}</span>
                            <span class="condition-text">主語クラス確認</span>
                        </div>
                        <div class="condition-item ${step3Result.conditions.object_class ? 'pass' : 'fail'}">
                            <span class="condition-icon">${step3Result.conditions.object_class ? '✓' : '✗'}</span>
                            <span class="condition-text">目的語クラス確認</span>
                        </div>
                        <div class="condition-item ${step3Result.conditions.world_knowledge ? 'pass' : 'fail'}">
                            <span class="condition-icon">${step3Result.conditions.world_knowledge ? '✓' : '✗'}</span>
                            <span class="condition-text">世界知識確認</span>
                        </div>
                    </div>
                    <div class="step-info">
                        <span class="label">理由:</span>
                        <span class="value">${escapeHtml(step3Result.reasoning)}</span>
                    </div>
                    ${step3Result.prompt ? `<button class="debug-toggle" onclick="toggleDebug(this)">プロンプト表示</button>` : ''}
                </div>
            </div>
        `;
    }

    const finalValid = step1Result.matched &&
                       step2Result?.valid &&
                       step3Result?.valid;
    html += `
        <div class="final-verdict ${finalValid ? 'valid' : 'invalid'}">
            ${finalValid ? '✓ トリプルは有効です' : '✗ トリプルは無効です'}
        </div>
    `;

    html += '</div>';
    container.innerHTML = html;
}

window.toggleDebug = function(button) {
    const next = button.nextElementSibling;
    if (next && next.classList.contains('debug-section')) {
        next.classList.toggle('open');
        button.textContent = next.classList.contains('open') ? 'プロンプト非表示' : 'プロンプト表示';
    }
};

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function escapeQuote(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'");
}

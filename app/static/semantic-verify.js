let semanticVerifyState = {
    selectedTriple: null,
    step1Result: null,
    step2Result: null,
    step3Result: null,
    step4Result: null,
    extractedTriples: [],
    relations: [],
    registeredTriples: [],
    nextTripleId: 1
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

    if (triples && triples.length > 0) {
        const firstTriple = triples[0];
        const subject = firstTriple.subject || firstTriple[0] || '';
        const predicate = firstTriple.predicate || firstTriple[1] || '';
        const object = firstTriple.object || firstTriple[2] || '';

        semanticVerifyState.extractedTriples = triples;
        semanticVerifyState.relations = relations || [];
        semanticVerifyState.selectedTriple = {
            subject: subject,
            predicate: predicate,
            object: object
        };
    }

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
            displayVerificationResults();
            return;
        }

        const step2Result = await performStep2_DirectionDetection(triple, step1Result.matchedRelation);
        semanticVerifyState.step2Result = step2Result;

        if (!step2Result.valid) {
            displayVerificationResults();
            return;
        }

        const step3Result = await performStep3_SampleGeneration(step1Result.matchedRelation);
        semanticVerifyState.step3Result = step3Result;

        if (step3Result.error) {
            displayVerificationResults();
            return;
        }

        const step4Result = await performStep4_ParaphraseVerification(
            triple,
            step2Result.pattern,
            step1Result.matchedRelation,
            step3Result
        );
        semanticVerifyState.step4Result = step4Result;

        displayVerificationResults();

    } catch (error) {
        console.error('Error:', error);
        const flowContainer = document.querySelector('.verify-process-flow');
        if (flowContainer) {
            flowContainer.innerHTML = `<div class="error">エラー: ${error.message}</div>`;
        }
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

async function performStep3_SampleGeneration(relation) {
    try {
        const response = await fetch('/api/verify/step3', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                relation: relation
            })
        });

        const result = await response.json();

        return {
            sample_domain: result.sample_domain || '',
            sample_object_class: result.sample_object_class || '',
            error: result.error || null,
            prompt: result.prompt,
            gemini_response: result.gemini_response
        };
    } catch (error) {
        return {
            sample_domain: '',
            sample_object_class: '',
            error: `エラー: ${error.message}`
        };
    }
}

async function performStep4_ParaphraseVerification(triple, pattern, relation, step3Result) {
    try {
        const response = await fetch('/api/verify/step4', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                triple: triple,
                pattern: pattern,
                relation: relation,
                sample_domain: step3Result.sample_domain,
                sample_object_class: step3Result.sample_object_class
            })
        });

        const result = await response.json();

        return {
            valid: result.valid === true,
            subject_class: result.subject_class === true,
            object_class: result.object_class === true,
            prompt: result.prompt,
            gemini_response: result.gemini_response,
            error: result.error || null
        };
    } catch (error) {
        return {
            valid: false,
            subject_class: false,
            object_class: false,
            error: `エラー: ${error.message}`
        };
    }
}

function displayVerificationResults() {
    const flowContainer = document.querySelector('.verify-process-flow');
    const promptsContainer = document.getElementById('semantic-prompts-section');

    if (!flowContainer || !promptsContainer) return;

    const step1Result = semanticVerifyState.step1Result;
    const step2Result = semanticVerifyState.step2Result;
    const step3Result = semanticVerifyState.step3Result;
    const step4Result = semanticVerifyState.step4Result;

    let flowHtml = '<h3>検証プロセス</h3>';
    let promptsHtml = '<h3>詳細プロンプト</h3>';

    if (step1Result) {
        flowHtml += `
            <div class="step step-1 ${step1Result.matched ? 'success' : 'failure'}">
                <div class="step-header">
                    <span class="step-title">Step 1: 述語定義判定</span>
                    <span class="step-status ${step1Result.matched ? 'pass' : 'fail'}">
                        [${step1Result.matched ? 'OK' : 'NG'}]
                    </span>
                </div>
                <div class="step-content">
                    ${step1Result.message ? `<div class="step-info">${escapeHtml(step1Result.message)}</div>` : ''}
                    ${step1Result.matchedRelation ? `
                    <div class="step-info">
                        <span class="label">述語:</span>
                        <span class="value">${escapeHtml(step1Result.matchedRelation.label)}</span>
                    </div>
                    <div class="step-info">
                        <span class="label">Domain:</span>
                        <span class="value">${escapeHtml(step1Result.matchedRelation.domain)}</span>
                    </div>
                    <div class="step-info">
                        <span class="label">Range:</span>
                        <span class="value">${escapeHtml(step1Result.matchedRelation.object_class)}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;

        if (step1Result.prompt) {
            promptsHtml += `
                <div class="prompt-section">
                    <div class="prompt-label">Step 1: 述語定義判定</div>
                    <div class="prompt-text">${escapeHtml(step1Result.prompt)}</div>
                    ${step1Result.gemini_response ? `<div class="response-text">応答:\n${escapeHtml(step1Result.gemini_response)}</div>` : ''}
                </div>
            `;
        }
    }

    if (!step1Result?.matched) {
        flowContainer.innerHTML = flowHtml;
        promptsContainer.innerHTML = promptsHtml;
        return;
    }

    if (step2Result) {
        const patternDescription = step2Result.pattern === 'A'
            ? '主語 → Domain, 目的語 → Range'
            : '主語 → Range, 目的語 → Domain (入れ替わり)';

        flowHtml += `
            <div class="step step-2 ${step2Result.valid ? 'success' : 'failure'}">
                <div class="step-header">
                    <span class="step-title">Step 2: 方向判定</span>
                    <span class="step-status ${step2Result.valid ? 'pass' : 'fail'}">
                        [${step2Result.valid ? 'Pattern ' + step2Result.pattern : 'NG'}]
                    </span>
                </div>
                <div class="step-content">
                    ${step2Result.valid ? `
                        <div class="step-info">
                            <span class="label">パターン:</span>
                            <span class="value">Pattern ${step2Result.pattern}</span>
                        </div>
                        <div class="step-info">
                            <span class="label">意味:</span>
                            <span class="value">${patternDescription}</span>
                        </div>
                        ${step2Result.reasoning ? `
                        <div class="step-info">
                            <span class="label">理由:</span>
                            <span class="value">${escapeHtml(step2Result.reasoning)}</span>
                        </div>
                        ` : ''}
                    ` : `
                        <div class="step-info error">${escapeHtml(step2Result.reasoning)}</div>
                    `}
                </div>
            </div>
        `;

        if (step2Result.prompt) {
            promptsHtml += `
                <div class="prompt-section">
                    <div class="prompt-label">Step 2: 方向判定</div>
                    <div class="prompt-text">${escapeHtml(step2Result.prompt)}</div>
                    ${step2Result.gemini_response ? `<div class="response-text">応答:\n${escapeHtml(step2Result.gemini_response)}</div>` : ''}
                </div>
            `;
        }
    }

    if (!step2Result?.valid) {
        flowContainer.innerHTML = flowHtml;
        promptsContainer.innerHTML = promptsHtml;
        return;
    }

    if (step3Result) {
        flowHtml += `
            <div class="step step-3 ${step3Result.error ? 'failure' : 'success'}">
                <div class="step-header">
                    <span class="step-title">Step 3: サンプル生成</span>
                    <span class="step-status ${step3Result.error ? 'fail' : 'pass'}">
                        [${step3Result.error ? 'NG' : 'OK'}]
                    </span>
                </div>
                <div class="step-content">
                    ${step3Result.error ? `
                        <div class="step-info error">${escapeHtml(step3Result.error)}</div>
                    ` : `
                        <div class="step-info">
                            <span class="label">${escapeHtml(step1Result.matchedRelation.domain)}のサンプル:</span>
                        </div>
                        <div class="step-info" style="margin-left: 20px; padding: 8px; background: #f5f5f5; border-radius: 4px;">
                            <span class="value">${escapeHtml(step3Result.sample_domain)}</span>
                        </div>
                        <div class="step-info">
                            <span class="label">${escapeHtml(step1Result.matchedRelation.object_class)}のサンプル:</span>
                        </div>
                        <div class="step-info" style="margin-left: 20px; padding: 8px; background: #f5f5f5; border-radius: 4px;">
                            <span class="value">${escapeHtml(step3Result.sample_object_class)}</span>
                        </div>
                    `}
                </div>
            </div>
        `;

        if (step3Result.prompt) {
            promptsHtml += `
                <div class="prompt-section">
                    <div class="prompt-label">Step 3: サンプル生成</div>
                    <div class="prompt-text">${escapeHtml(step3Result.prompt)}</div>
                    ${step3Result.gemini_response ? `<div class="response-text">応答:\n${escapeHtml(step3Result.gemini_response)}</div>` : ''}
                </div>
            `;
        }
    }

    if (step3Result?.error) {
        flowContainer.innerHTML = flowHtml;
        promptsContainer.innerHTML = promptsHtml;
        return;
    }

    if (step4Result) {
        let condition1_text = '';
        let condition2_text = '';
        let condition1_result = '';
        let condition2_result = '';

        if (step2Result.pattern === 'B') {
            condition1_text = `主語「${escapeHtml(semanticVerifyState.selectedTriple.subject)}」が「${escapeHtml(step1Result.matchedRelation.object_class)}」クラスに属する`;
            condition2_text = `目的語「${escapeHtml(semanticVerifyState.selectedTriple.object)}」が「${escapeHtml(step1Result.matchedRelation.domain)}」クラスに属する`;
            condition1_result = step4Result.subject_class;
            condition2_result = step4Result.object_class;
        } else {
            condition1_text = `主語「${escapeHtml(semanticVerifyState.selectedTriple.subject)}」が「${escapeHtml(step1Result.matchedRelation.domain)}」クラスに属する`;
            condition2_text = `目的語「${escapeHtml(semanticVerifyState.selectedTriple.object)}」が「${escapeHtml(step1Result.matchedRelation.object_class)}」クラスに属する`;
            condition1_result = step4Result.subject_class;
            condition2_result = step4Result.object_class;
        }

        flowHtml += `
            <div class="step step-4 ${step4Result.valid ? 'success' : 'failure'}">
                <div class="step-header">
                    <span class="step-title">Step 4: パラフレーズ判定</span>
                    <span class="step-status ${step4Result.valid ? 'pass' : 'fail'}">
                        [${step4Result.valid ? 'OK' : 'NG'}]
                    </span>
                </div>
                <div class="step-content">
                    <div class="step-info">
                        <span class="label">判定条件:</span>
                    </div>
                    <div class="conditions-check">
                        <div class="condition-item ${condition1_result ? 'pass' : 'fail'}">
                            <span class="condition-icon">[${condition1_result ? '✓' : '✗'}]</span>
                            <span class="condition-text">${condition1_text}</span>
                        </div>
                        <div class="condition-item ${condition2_result ? 'pass' : 'fail'}">
                            <span class="condition-icon">[${condition2_result ? '✓' : '✗'}]</span>
                            <span class="condition-text">${condition2_text}</span>
                        </div>
                    </div>
                    ${step4Result.valid ? `
                        <button class="register-triple-btn" onclick="window.registerTriple(semanticVerifyState.selectedTriple, semanticVerifyState.step1Result.matchedRelation)">
                            トリプルを登録
                        </button>
                    ` : ''}
                </div>
            </div>
        `;

        if (step4Result.prompt) {
            promptsHtml += `
                <div class="prompt-section">
                    <div class="prompt-label">Step 4: パラフレーズ判定</div>
                    <div class="prompt-text">${escapeHtml(step4Result.prompt)}</div>
                    ${step4Result.gemini_response ? `<div class="response-text">応答:\n${escapeHtml(step4Result.gemini_response)}</div>` : ''}
                </div>
            `;
        }
    }

    flowContainer.innerHTML = flowHtml;
    promptsContainer.innerHTML = promptsHtml;
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

window.registerTriple = function(triple, relation) {
    const id = semanticVerifyState.nextTripleId++;
    const pattern = semanticVerifyState.step2Result.pattern;

    let registeredSubject = triple.subject;
    let registeredObject = triple.object;

    if (pattern === 'B') {
        registeredSubject = triple.object;
        registeredObject = triple.subject;
    }

    const registeredTriple = {
        id: id,
        subject: registeredSubject,
        predicate: triple.predicate,
        object: registeredObject,
        relation: relation,
        registeredAt: new Date().toLocaleString('ja-JP')
    };

    semanticVerifyState.registeredTriples.push(registeredTriple);
    console.log('✓ トリプル登録:', registeredTriple);

    displayRegisteredTriples();

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '登録済み ✓';
};

function displayRegisteredTriples() {
    const container = document.getElementById('registered-triples-section');
    if (!container) return;

    let html = `<h3>登録済みトリプル (${semanticVerifyState.registeredTriples.length} 件)</h3>`;

    if (semanticVerifyState.registeredTriples.length === 0) {
        html += '<div class="empty-state">登録済みトリプルはありません</div>';
    } else {
        html += '<div class="registered-triples-list">';

        semanticVerifyState.registeredTriples.forEach(triple => {

            const predicateFormat = `${escapeHtml(triple.relation.label)}(${escapeHtml(triple.relation.domain)}, ${escapeHtml(triple.relation.object_class)})`;

            html += `
                <div class="registered-triple-item">
                    <div class="triple-info">
                        <span class="triple-id">#${triple.id}</span>
                        <div class="triple-content">
                            <div class="triple-text">
                                S: ${escapeHtml(triple.subject)}<br>
                                P: ${predicateFormat}<br>
                                O: ${escapeHtml(triple.object)}
                            </div>
                            <div class="triple-time">${triple.registeredAt}</div>
                        </div>
                    </div>
                    <button class="delete-triple-btn" onclick="window.deleteTriple(${triple.id})">削除</button>
                </div>
            `;
        });

        html += '</div>';
    }

    container.innerHTML = html;
}

window.deleteTriple = function(id) {
    const index = semanticVerifyState.registeredTriples.findIndex(t => t.id === id);
    if (index !== -1) {
        const deleted = semanticVerifyState.registeredTriples.splice(index, 1)[0];
        console.log('✓ トリプル削除:', deleted);
        displayRegisteredTriples();
    }
};

window.clearRegisteredTriples = function() {
    if (confirm(`登録済みトリプル ${semanticVerifyState.registeredTriples.length} 件をすべて削除してよろしいですか？`)) {
        semanticVerifyState.registeredTriples = [];
        semanticVerifyState.nextTripleId = 1;
        displayRegisteredTriples();
        console.log('✓ すべてのトリプルをクリア');
    }
};

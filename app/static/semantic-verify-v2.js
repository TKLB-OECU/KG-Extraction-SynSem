let semanticVerifyState = {
    selectedTriple: null,
    stage1Result: null,
    stage2Result: null,
    stage3Result: null,
    extractedTriples: []
};

window.displayExtractedTriples = function(triples) {
    semanticVerifyState.extractedTriples = triples;
    const container = document.getElementById('semantic-verify-section');
    if (!container) return;

    if (!triples || triples.length === 0) {
        container.innerHTML = '<div class="empty-state">トリプルを選択してください</div>';
        return;
    }

    let html = `
        <div class="extracted-triples-panel">
            <div class="triples-header">
                <h4>抽出トリプル: ${triples.length} 件</h4>
            </div>
            <div class="triples-list">
    `;

    triples.forEach((triple, idx) => {
        const subject = triple.subject || triple[0] || '';
        const predicate = triple.predicate || triple[1] || '';
        const object = triple.object || triple[2] || '';

        html += `
            <div class="triple-card" onclick="window.selectTripleForVerification({
                subject: '${escapeQuote(subject)}',
                predicate: '${escapeQuote(predicate)}',
                object: '${escapeQuote(object)}'
            })">
                <div class="triple-content">
                    <div class="triple-row">
                        <span class="label">主語:</span>
                        <span class="value">${escapeHtml(subject)}</span>
                    </div>
                    <div class="triple-row">
                        <span class="label">述語:</span>
                        <span class="value">${escapeHtml(predicate)}</span>
                    </div>
                    <div class="triple-row">
                        <span class="label">目的語:</span>
                        <span class="value">${escapeHtml(object)}</span>
                    </div>
                </div>
                <div class="triple-action">
                    <button class="btn-verify-select" onclick="event.stopPropagation(); window.selectTripleForVerification({
                        subject: '${escapeQuote(subject)}',
                        predicate: '${escapeQuote(predicate)}',
                        object: '${escapeQuote(object)}'
                    })">検証</button>
                </div>
            </div>
        `;
    });

    html += `
            </div>
        </div>
    `;

    container.innerHTML = html;
};

window.selectTripleForVerification = function(triple) {
    semanticVerifyState.selectedTriple = triple;
    const container = document.getElementById('semantic-verify-section');
    if (!container) return;

    const html = `
        <div class="semantic-verify-panel">
            <div class="panel-header">
                <h3>検証対象トリプル</h3>
                <button class="btn-back" onclick="window.displayExtractedTriples(semanticVerifyState.extractedTriples)">← 戻る</button>
            </div>

            <div class="triple-info-box">
                <div class="info-item">
                    <label>主語 (Subject):</label>
                    <span>${escapeHtml(triple.subject)}</span>
                </div>
                <div class="info-item">
                    <label>述語 (Predicate):</label>
                    <span>${escapeHtml(triple.predicate)}</span>
                </div>
                <div class="info-item">
                    <label>目的語 (Object):</label>
                    <span>${escapeHtml(triple.object)}</span>
                </div>
            </div>

            <div class="verify-action">
                <button class="btn-start-verify" onclick="window.performSemanticVerify()">
                    🔍 検証を実行
                </button>
            </div>

            <div id="verify-results" class="verify-results"></div>
        </div>
    `;

    container.innerHTML = html;
};

window.performSemanticVerify = async function() {
    const triple = semanticVerifyState.selectedTriple;
    if (!triple) {
        alert('トリプルが選択されていません');
        return;
    }

    const container = document.getElementById('verify-results');
    container.innerHTML = '<div class="loading">検証実行中...</div>';

    try {

        const ontology = window.getOntologyEditorState ? window.getOntologyEditorState() : null;
        if (!ontology || !ontology.relations || ontology.relations.length === 0) {
            container.innerHTML = '<div class="error">検証用の Relation が定義されていません</div>';
            return;
        }

        console.log('[🔍 Semantic Verify] ===== 3段階検証開始 =====');
        console.log('[Input] トリプル:', triple);
        console.log('[Input] オントロジー Relations:', ontology.relations);

        console.log('\n[Stage 1] 述語定義判定を実行...');
        const stage1Result = await performStage1_DefinitionCheck(triple, ontology.relations);
        semanticVerifyState.stage1Result = stage1Result;
        console.log('[Stage 1] 結果:', stage1Result);

        if (!stage1Result.matched) {
            console.log('[Stage 1] ✗ 述語未定義のため検証終了');
            displayVerificationResults(container, stage1Result, null, null);
            return;
        }

        console.log('\n[Stage 2] オントロジー方向判定と言い換え生成を実行...');
        const stage2Result = await performStage2_DirectionDetection(
            triple,
            stage1Result.matchedRelation
        );
        semanticVerifyState.stage2Result = stage2Result;
        console.log('[Stage 2] 結果:', stage2Result);

        if (!stage2Result.valid) {
            console.log('[Stage 2] ✗ 方向判定失敗のため検証終了');
            displayVerificationResults(container, stage1Result, stage2Result, null);
            return;
        }

        console.log('\n[Stage 3] パラフレーズ検証と3条件チェックを実行...');
        const stage3Result = await performStage3_ParaphraseVerification(
            triple,
            stage2Result.pattern,
            stage1Result.matchedRelation
        );
        semanticVerifyState.stage3Result = stage3Result;
        console.log('[Stage 3] 結果:', stage3Result);

        console.log('\n[🔍 Semantic Verify] ===== 検証完了 =====\n');

        displayVerificationResults(container, stage1Result, stage2Result, stage3Result);

    } catch (error) {
        console.error('[❌ Error]', error);
        container.innerHTML = `<div class="error">エラー: ${error.message}</div>`;
    }
};

async function performStage1_DefinitionCheck(triple, relations) {
    console.log('  [処理] Gemini API を呼び出し、述語定義判定を実行...');

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
        console.log('  [API Response]', result);

        if (result.matched) {
            console.log(`  [✓] リレーション "${result.matchedRelation.label}" にマッチ`);
            return {
                matched: true,
                defined: true,
                matchedRelation: result.matchedRelation,
                stage: 1,
                message: result.message
            };
        } else {
            console.log(`  [✗] 述語マッチング失敗: ${result.message}`);
            return {
                matched: false,
                defined: false,
                stage: 1,
                message: result.message
            };
        }
    } catch (error) {
        console.error('  [❌ Error in Stage 1]', error);
        return {
            matched: false,
            defined: false,
            stage: 1,
            message: `エラー: ${error.message}`
        };
    }
}

async function performStage2_DirectionDetection(triple, relation) {
    console.log('  [処理] Gemini API を呼び出し、方向判定と言い換え生成を実行...');

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
        console.log('  [API Response]', result);

        if (result.valid !== false) {
            const pattern = result.pattern || 'A';
            const paraphrase = result.paraphrase || '';
            const reasoning = result.reasoning || '';

            console.log(`  [✓] Pattern ${pattern}: ${paraphrase}`);

            return {
                valid: true,
                pattern: pattern,
                paraphrase: paraphrase,
                reasoning: reasoning
            };
        } else {
            console.log('  [✗] 方向判定に失敗');
            return {
                valid: false,
                pattern: null,
                paraphrase: null,
                reasoning: result.reasoning || 'エラーが発生しました'
            };
        }
    } catch (error) {
        console.error('  [❌ Error in Stage 2]', error);
        return {
            valid: false,
            pattern: null,
            paraphrase: null,
            reasoning: `エラー: ${error.message}`
        };
    }
}

async function performStage3_ParaphraseVerification(triple, pattern, relation) {
    console.log('  [処理] Gemini API を呼び出し、パラフレーズ検証と3条件チェックを実行...');

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
        console.log('  [API Response]', result);

        const verified = result.valid === true;
        const reasoning = result.reasoning || '';
        const paraphrase = result.paraphrase || '';
        const conditions = result.conditions || {};

        if (verified) {
            console.log(`  [✓] パラフレーズ検証成功: ${paraphrase}`);
        } else {
            console.log(`  [✗] パラフレーズ検証失敗: ${reasoning}`);
        }

        return {
            valid: verified,
            paraphrase: paraphrase,
            reasoning: reasoning,
            conditions: conditions,
            prompt: result.prompt,
            gemini_response: result.gemini_response
        };
    } catch (error) {
        console.error('  [❌ Error in Stage 3]', error);
        return {
            valid: false,
            paraphrase: '',
            reasoning: `エラー: ${error.message}`,
            conditions: {}
        };
    }
}

function displayVerificationResults(container, stage1Result, stage2Result, stage3Result) {
    let html = '<div class="verification-checks">';

    html += `
        <div class="check-item stage-1">
            <div class="check-header">
                <span class="stage-label">Stage 1</span>
                <span class="stage-title">述語定義判定</span>
                <span class="status ${stage1Result.matched ? 'success' : 'failure'}">
                    ${stage1Result.matched ? '✓ PASS' : '✗ FAIL'}
                </span>
            </div>
            <div class="check-body">
                <div class="check-message">${escapeHtml(stage1Result.message)}</div>
                ${stage1Result.matchedRelation ? `
                    <div class="relation-details">
                        <div class="detail-row">
                            <span class="label">Label:</span>
                            <span class="value">${escapeHtml(stage1Result.matchedRelation.label)}</span>
                        </div>
                        <div class="detail-row">
                            <span class="label">Domain:</span>
                            <span class="value">${escapeHtml(stage1Result.matchedRelation.domain)}</span>
                        </div>
                        <div class="detail-row">
                            <span class="label">Object Class:</span>
                            <span class="value">${escapeHtml(stage1Result.matchedRelation.object_class)}</span>
                        </div>
                    </div>
                ` : ''}
                ${stage1Result.prompt ? `
                    <details class="debug-section">
                        <summary>📋 プロンプト・応答を表示</summary>
                        <div class="debug-content">
                            <div class="debug-item">
                                <div class="debug-label">【送信プロンプト】</div>
                                <pre class="debug-text">${escapeHtml(stage1Result.prompt)}</pre>
                            </div>
                            ${stage1Result.gemini_response ? `
                                <div class="debug-item">
                                    <div class="debug-label">【Gemini応答】</div>
                                    <pre class="debug-text">${escapeHtml(stage1Result.gemini_response)}</pre>
                                </div>
                            ` : ''}
                            ${stage1Result.reasoning ? `
                                <div class="debug-item">
                                    <div class="debug-label">【判定理由】</div>
                                    <div class="debug-text">${escapeHtml(stage1Result.reasoning)}</div>
                                </div>
                            ` : ''}
                        </div>
                    </details>
                ` : ''}
            </div>
        </div>
    `;

    if (stage2Result) {
        html += `
            <div class="check-item stage-2">
                <div class="check-header">
                    <span class="stage-label">Stage 2</span>
                    <span class="stage-title">方向判定・言い換え生成</span>
                    <span class="status ${stage2Result.valid ? 'success' : 'failure'}">
                        ${stage2Result.valid ? '✓ PASS' : '✗ FAIL'}
                    </span>
                </div>
                <div class="check-body">
                    ${stage2Result.valid ? `
                        <div class="pattern-box">
                            <div class="detail-row">
                                <span class="label">パターン:</span>
                                <span class="pattern-badge pattern-${stage2Result.pattern}">${stage2Result.pattern}</span>
                            </div>
                            <div class="detail-row">
                                <span class="label">言い換え:</span>
                                <span class="paraphrase">"${escapeHtml(stage2Result.paraphrase)}"</span>
                            </div>
                            <div class="detail-row">
                                <span class="label">理由:</span>
                                <span class="reasoning">${escapeHtml(stage2Result.reasoning)}</span>
                            </div>
                        </div>
                    ` : `
                        <div class="check-message error">${escapeHtml(stage2Result.reasoning)}</div>
                    `}
                    ${stage2Result.prompt ? `
                        <details class="debug-section">
                            <summary>📋 プロンプト・応答を表示</summary>
                            <div class="debug-content">
                                <div class="debug-item">
                                    <div class="debug-label">【送信プロンプト】</div>
                                    <pre class="debug-text">${escapeHtml(stage2Result.prompt)}</pre>
                                </div>
                                ${stage2Result.gemini_response ? `
                                    <div class="debug-item">
                                        <div class="debug-label">【Gemini応答】</div>
                                        <pre class="debug-text">${escapeHtml(stage2Result.gemini_response)}</pre>
                                    </div>
                                ` : ''}
                                ${stage2Result.reasoning ? `
                                    <div class="debug-item">
                                        <div class="debug-label">【判定理由】</div>
                                        <div class="debug-text">${escapeHtml(stage2Result.reasoning)}</div>
                                    </div>
                                ` : ''}
                            </div>
                        </details>
                    ` : ''}
                </div>
            </div>
        `;
    }

    if (stage3Result) {
        html += `
            <div class="check-item stage-3">
                <div class="check-header">
                    <span class="stage-label">Stage 3</span>
                    <span class="stage-title">パラフレーズ検証・3条件チェック</span>
                    <span class="status ${stage3Result.valid ? 'success' : 'failure'}">
                        ${stage3Result.valid ? '✓ PASS' : '✗ FAIL'}
                    </span>
                </div>
                <div class="check-body">
                    <div class="detail-row">
                        <span class="label">生成パラフレーズ:</span>
                        <span class="paraphrase">"${escapeHtml(stage3Result.paraphrase)}"</span>
                    </div>
                    <div class="conditions-box">
                        <div class="conditions-label">【検証条件】</div>
                        <div class="condition-item ${stage3Result.conditions.subject_class ? 'pass' : 'fail'}">
                            <span class="condition-check">${stage3Result.conditions.subject_class ? '✓' : '✗'}</span>
                            <span class="condition-text">主語が正しいクラスに属する</span>
                        </div>
                        <div class="condition-item ${stage3Result.conditions.object_class ? 'pass' : 'fail'}">
                            <span class="condition-check">${stage3Result.conditions.object_class ? '✓' : '✗'}</span>
                            <span class="condition-text">目的語が正しいクラスに属する</span>
                        </div>
                        <div class="condition-item ${stage3Result.conditions.world_knowledge ? 'pass' : 'fail'}">
                            <span class="condition-check">${stage3Result.conditions.world_knowledge ? '✓' : '✗'}</span>
                            <span class="condition-text">世界知識で成立する</span>
                        </div>
                    </div>
                    <div class="detail-row">
                        <span class="label">理由:</span>
                        <span class="reasoning">${escapeHtml(stage3Result.reasoning)}</span>
                    </div>
                    ${stage3Result.prompt ? `
                        <details class="debug-section">
                            <summary>📋 プロンプト・応答を表示</summary>
                            <div class="debug-content">
                                <div class="debug-item">
                                    <div class="debug-label">【送信プロンプト】</div>
                                    <pre class="debug-text">${escapeHtml(stage3Result.prompt)}</pre>
                                </div>
                                ${stage3Result.gemini_response ? `
                                    <div class="debug-item">
                                        <div class="debug-label">【Gemini応答】</div>
                                        <pre class="debug-text">${escapeHtml(stage3Result.gemini_response)}</pre>
                                    </div>
                                ` : ''}
                                ${stage3Result.reasoning ? `
                                    <div class="debug-item">
                                        <div class="debug-label">【判定理由】</div>
                                        <div class="debug-text">${escapeHtml(stage3Result.reasoning)}</div>
                                    </div>
                                ` : ''}
                            </div>
                        </details>
                    ` : ''}
                </div>
            </div>
        `;
    }

    const finalValid = stage1Result.matched &&
                       stage2Result?.valid &&
                       stage3Result?.valid;
    html += `
        <div class="final-verdict ${finalValid ? 'valid' : 'invalid'}">
            <span class="verdict-icon">${finalValid ? '✓' : '✗'}</span>
            <span class="verdict-text">${finalValid ? 'トリプルは有効です' : 'トリプルは無効です'}</span>
        </div>
    `;

    html += '</div>';
    container.innerHTML = html;
}

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

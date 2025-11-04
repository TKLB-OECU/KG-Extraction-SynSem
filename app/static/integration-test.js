window.runIntegrationTest = async function() {
    console.log('=== 統合テスト開始 ===');

    console.log('Test 1: オントロジー確認');
    const ontology = window.getOntologyEditorState?.();
    if (ontology) {
        console.log('✓ Relations:', ontology.relations.map(r => `${r.label}(${r.domain} → ${r.object_class})`));
    } else {
        console.warn('✗ オントロジーが未定義です');
        return;
    }

    console.log('\nTest 2: 4段階検証テスト');
    const mockTriple = {
        subject: '千尋の神隠し',
        predicate: '監督',
        object: '宮崎駿'
    };

    console.log(`検証対象トリプル: (${mockTriple.subject}, ${mockTriple.predicate}, ${mockTriple.object})`);

    console.log('\nStep 1: 述語定義判定');
    const step1Result = await performStep1(mockTriple, ontology.relations);
    console.log(`✓ Step 1:`, step1Result);

    if (!step1Result.matched) {
        console.warn('✗ Step 1 でマッチしませんでした');
        return;
    }

    console.log('\nStep 2: 方向判定（Pattern A/B）');
    const step2Result = await performStep2(mockTriple, step1Result.matchedRelation);
    console.log(`✓ Step 2:`, step2Result);

    if (!step2Result.valid) {
        console.warn('✗ Step 2 が無効です');
        return;
    }

    console.log('\nStep 3: パラフレーズ用サンプル生成');
    const step3Result = await performStep3(step1Result.matchedRelation);
    console.log(`✓ Step 3:`, step3Result);

    if (step3Result.error) {
        console.warn('✗ Step 3 でエラー:', step3Result.error);
        return;
    }

    console.log('\nStep 4: パラフレーズ判定');
    const step4Result = await performStep4(
        mockTriple,
        step2Result.pattern,
        step1Result.matchedRelation,
        step3Result
    );
    console.log(`✓ Step 4:`, step4Result);

    console.log('\n=== 最終結果 ===');
    const finalValid = step1Result.matched &&
                       step2Result.valid &&
                       !step3Result.error &&
                       step4Result.valid;
    console.log(`✓ トリプル有効性: ${finalValid ? 'VALID' : 'INVALID'}`);

    console.log('=== テスト完了 ===\n');
};

async function performStep1(triple, relations) {
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
        return {
            matched: result.matched === true,
            matchedRelation: result.matchedRelation,
            message: result.message
        };
    } catch (error) {
        console.error('[Step 1] Error:', error);
        return {
            matched: false,
            message: `エラー: ${error.message}`
        };
    }
}

async function performStep2(triple, relation) {
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
        return {
            valid: result.valid !== false,
            pattern: result.pattern || 'A',
            reasoning: result.reasoning || ''
        };
    } catch (error) {
        console.error('[Step 2] Error:', error);
        return {
            valid: false,
            pattern: 'A',
            reasoning: `エラー: ${error.message}`
        };
    }
}

async function performStep3(relation) {
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
            error: result.error || null
        };
    } catch (error) {
        console.error('[Step 3] Error:', error);
        return {
            sample_domain: '',
            sample_object_class: '',
            error: `エラー: ${error.message}`
        };
    }
}

async function performStep4(triple, pattern, relation, step3Result) {
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
            error: result.error || null
        };
    } catch (error) {
        console.error('[Step 4] Error:', error);
        return {
            valid: false,
            subject_class: false,
            object_class: false,
            error: `エラー: ${error.message}`
        };
    }
}

console.log('統合テスト実行可能: window.runIntegrationTest()');

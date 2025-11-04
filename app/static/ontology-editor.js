let ontologyEditorState = {
    concepts: [
        "人",
        "映画",
        "映画制作会社",
        "監督",
        "俳優",
        "製作年",
        "作品"
    ],
    relations: [
        {
            label: "監督",
            domain: "映画",
            object_class: "人",
            description: "映画を監督する人"
        },
        {
            label: "制作会社",
            domain: "映画",
            object_class: "映画制作会社",
            description: "映画を制作する企業"
        },
        {
            label: "主演",
            domain: "映画",
            object_class: "人",
            description: "映画に主演する人"
        },
        {
            label: "公開年",
            domain: "映画",
            object_class: "製作年",
            description: "映画の公開年"
        },
        {
            label: "制作",
            domain: "映画制作会社",
            object_class: "映画",
            description: "企業が制作する映画"
        }
    ]
};

window.getOntologyEditorState = function() {
    return ontologyEditorState;
};

window.displayOntologyEditor = function() {
    const container = document.getElementById('ontology-editor-section');
    if (!container) return;

    let html = `
        <div class="ontology-editor">
            <div class="ontology-header">
                <h3>オントロジー定義</h3>
                <div class="ontology-info">デモ用定義</div>
            </div>

            <!-- Concepts セクション -->
            <div class="ontology-section concepts-section">
                <div class="section-title">
                    <h4>概念 (Concepts)</h4>
                    <span class="count-badge">${ontologyEditorState.concepts.length}</span>
                </div>
                <div class="concepts-list">
                    ${ontologyEditorState.concepts.map(concept => `
                        <div class="concept-item">
                            <span class="concept-name">${escapeHtml(concept)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>

            <!-- Relations セクション -->
            <div class="ontology-section relations-section">
                <div class="section-title">
                    <h4>関係 (Relations)</h4>
                    <span class="count-badge">${ontologyEditorState.relations.length}</span>
                </div>
                <div class="relations-list">
                    ${ontologyEditorState.relations.map((relation, idx) => `
                        <div class="relation-item" data-index="${idx}">
                            <div class="relation-header">
                                <span class="relation-label">${escapeHtml(relation.label)}</span>
                            </div>
                            <div class="relation-signature">
                                <span class="domain">${escapeHtml(relation.domain)}</span>
                                <span class="arrow">-></span>
                                <span class="range">${escapeHtml(relation.object_class)}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.addConceptToOntology = function(conceptName) {
    if (!conceptName || ontologyEditorState.concepts.includes(conceptName)) {
        return false;
    }
    ontologyEditorState.concepts.push(conceptName);
    window.displayOntologyEditor();
    return true;
};

window.addRelationToOntology = function(label, domain, objectClass, description = "") {
    if (!label || !domain || !objectClass) {
        return false;
    }

    const relationExists = ontologyEditorState.relations.some(r => r.label === label);
    if (relationExists) {
        return false;
    }

    ontologyEditorState.relations.push({
        label,
        domain,
        object_class: objectClass,
        description
    });

    window.displayOntologyEditor();
    return true;
};

window.removeRelationFromOntology = function(index) {
    if (index >= 0 && index < ontologyEditorState.relations.length) {
        ontologyEditorState.relations.splice(index, 1);
        window.displayOntologyEditor();
        return true;
    }
    return false;
};

window.resetOntology = function() {
    ontologyEditorState.concepts = [
        "人",
        "映画",
        "映画制作会社",
        "監督",
        "俳優",
        "製作年",
        "作品"
    ];
    ontologyEditorState.relations = [
        {
            label: "監督",
            domain: "映画",
            object_class: "人",
            description: "映画を監督する人"
        },
        {
            label: "制作会社",
            domain: "映画",
            object_class: "映画制作会社",
            description: "映画を制作する企業"
        },
        {
            label: "主演",
            domain: "映画",
            object_class: "人",
            description: "映画に主演する人"
        },
        {
            label: "公開年",
            domain: "映画",
            object_class: "製作年",
            description: "映画の公開年"
        },
        {
            label: "制作",
            domain: "映画制作会社",
            object_class: "映画",
            description: "企業が制作する映画"
        }
    ];
    window.displayOntologyEditor();
};

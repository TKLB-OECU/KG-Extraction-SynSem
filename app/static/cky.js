let ckyState = {
    result: null,
    selectedTreeId: null,
    bunsetsuList: null
};

function initCKY() {
    console.log('[CKY Module] Initialized');
}

function updateCKYContent(content) {
    const ckyContent = DOM.get('#cky-content');
    if (ckyContent) {
        ckyContent.innerHTML = content;
    }
}

function resetCKY() {
    ckyState.result = null;
    ckyState.selectedTreeId = null;
    updateCKYContent('<div class="empty-state">編集後のデータを送信してください</div>');
}

function buildCKYTable(matrix, bunsetsuList) {
    const n = matrix.length;
    let html = '<div class="cky-table-container"><table class="cky-table"><tbody>';

    for (let i = 0; i < n; i++) {
        html += '<tr>';
        for (let j = 0; j < n; j++) {
            if (j < i) {
                html += '<td class="hidden-cell"></td>';
            } else if (i === j) {
                html += `<td class="diagonal-cell" data-i="${i}" data-j="${j}">
                    <div class="cell-content">${bunsetsuList[i].text}</div>
                </td>`;
            } else {
                const cell = matrix[i][j];
                const pred1Count = cell?.expanded_pred1_count ?? 0;
                const pred0Count = cell?.expanded_pred0_count ?? 0;

                let countDisplay = '';
                if (pred1Count > 0) countDisplay += `<span class="pred-count pred1-color">${pred1Count}</span>`;
                if (pred0Count > 0) countDisplay += `<span class="pred-count pred0-color">${pred0Count}</span>`;
                if (!countDisplay) countDisplay = '<span class="pred-count">0</span>';

                let cellClass = 'combinable-cell';
                if (pred1Count > 0) cellClass += ' has-pred1';
                if (pred0Count > 0) cellClass += ' has-pred0';

                html += `<td class="${cellClass}" data-i="${i}" data-j="${j}">
                    <div class="cell-content">
                        <div class="cell-text">${cell?.text ?? ''}</div>
                        <div class="cell-count">${countDisplay}</div>
                    </div>
                </td>`;
            }
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    return html;
}

function buildTreeDisplay(node, depth = 0) {
    if (!node) return '';

    const indent = depth * 20;
    const types = node.types ? `[${node.types.join(', ')}]` : '';
    const pred = node.pred !== undefined && node.pred !== null ? `pred=${node.pred}` : '';
    const confidence = node.confidence ? `conf=${(node.confidence * 100).toFixed(0)}%` : '';

    const nodeColorClass = `node-color-${node.color || 'gray'}`;

    let html = `<div class="tree-node" style="margin-left: ${indent}px;">`;
    html += `<div class="tree-node-header ${nodeColorClass}">
        <span class="node-text">${node.text}</span>
        <span class="node-info">${types} ${pred} ${confidence}</span>
    </div>`;

    if (node.children && node.children.length >= 2) {
        html += '<div class="tree-children-with-branches">';
        html += '<div class="tree-branch left-branch"><div class="branch-line"></div><div class="branch-label">L</div>';
        html += buildTreeDisplay(node.children[0], depth + 1);
        html += '</div>';
        html += '<div class="tree-branch right-branch"><div class="branch-line"></div><div class="branch-label">R</div>';
        html += buildTreeDisplay(node.children[1], depth + 1);
        html += '</div></div>';
    } else if (node.children && node.children.length > 0) {
        html += '<div class="tree-children">';
        node.children.forEach(child => {
            if (child) html += buildTreeDisplay(child, depth + 1);
        });
        html += '</div>';
    }

    html += '</div>';
    return html;
}

function drawTreeOnCanvas(node) {
    const canvas = document.getElementById('tree-canvas');
    if (!canvas) return;

    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;

    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawNode(ctx, node, canvas.width / 2, 30, canvas.width / 4);
}

function drawNode(ctx, node, x, y, horizontalGap) {
    if (!node) return;

    const boxWidth = 80, boxHeight = 40, cornerRadius = 6;

    const colorMap = {
        'green': { fill: '#c8e6c9', stroke: '#4CAF50', text: '#1b5e20' },
        'red': { fill: '#ffcdd2', stroke: '#F44336', text: '#b71c1c' },
        'gray': { fill: '#e0e0e0', stroke: '#999999', text: '#424242' }
    };
    const colors = colorMap[node.color] || colorMap['gray'];

    drawRoundedRect(ctx, x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight, cornerRadius, colors.fill, colors.stroke, 2);

    ctx.fillStyle = colors.text;
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.text, x, y);

    if (node.children && node.children.length >= 2) {
        const verticalGap = 60;
        const leftX = x - horizontalGap, rightX = x + horizontalGap;
        const childY = y + verticalGap;

        drawBranchLine(ctx, x, y + boxHeight / 2, leftX, childY - 20, 'L');
        drawBranchLine(ctx, x, y + boxHeight / 2, rightX, childY - 20, 'R');

        drawNode(ctx, node.children[0], leftX, childY, horizontalGap / 2);
        drawNode(ctx, node.children[1], rightX, childY, horizontalGap / 2);
    }
}

function drawBranchLine(ctx, fromX, fromY, toX, toY, label) {
    ctx.strokeStyle = '#999999';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);
    ctx.lineTo(toX, toY);
    ctx.stroke();

    ctx.fillStyle = '#666666';
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, (fromX + toX) / 2, (fromY + toY) / 2 - 10);
}

function drawRoundedRect(ctx, x, y, width, height, radius, fillColor, strokeColor, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();

    ctx.fillStyle = fillColor;
    ctx.fill();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
}

function displayCKYResult(result) {
    ckyState.result = result;
    ckyState.bunsetsuList = result.input_data.bunsetsu;

    let html = '<div class="cky-result">';
    html += '<div class="cky-table-section">';
    html += '<p class="table-note">セルをクリックすると構文木が表示されます</p>';
    html += buildCKYTable(result.cky_data.matrix, ckyState.bunsetsuList);
    html += '</div>';

    html += '<div class="cky-tree-section" id="root-tree-section" style="display: none;"><h4>ツリー表示</h4></div>';
    html += '<div class="cky-expanded-section" id="cell-expanded-section"></div>';
    html += '<div class="cky-matching-section" id="cell-matching-section"></div>';
    html += '</div>';

    updateCKYContent(html);
    bindCKYTableEvents();
}

function bindCKYTableEvents() {
    document.querySelectorAll('.cky-table .combinable-cell').forEach(cell => {
        cell.addEventListener('click', async function() {
            const i = parseInt(this.dataset.i);
            const j = parseInt(this.dataset.j);

            document.querySelectorAll('.cky-table .combinable-cell').forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            await expandTreeFromCell(i, j);
        });
    });
}

async function expandTreeFromCell(i, j) {
    let data = (typeof getCurrentData === 'function') ? getCurrentData() : ckyState.bunsetsuList;
    if (!data || data.length === 0) return;

    try {
        const resp = await API.ckyExpandCell(data, [i, j], 1);
        if (resp.status !== 'success') {
            displayExpandedTrees(null, i, j);
            return;
        }
        displayExpandedTrees(resp, i, j);
    } catch (err) {
        console.error('[CKY] Expand error:', err);
        displayExpandedTrees(null, i, j);
    }
}

function displayExpandedTrees(result, i, j) {
    const section = document.querySelector('#cell-expanded-section');
    if (!section) return;

    if (!result || result.status !== 'success') {
        section.innerHTML = `<p class="error">セル (${i}, ${j}) からの展開に失敗しました</p>`;
        return;
    }

    let html = `<div class="expanded-trees-layout"><h3>セル (${i}, ${j}) : ${result.cell_text}</h3>`;

    if (result.is_terminal) {
        html += `<p class="terminal-note">Terminal（基本文節）</p>`;
    } else if (result.tree_list && result.tree_list.length > 0) {
        html += `<div class="expanded-trees-container">`;
        html += `<div class="trees-selector-panel">`;
        result.tree_list.forEach((tree, idx) => {
            const pred = tree.root_pred ?? 'unknown';
            const predClass = pred === 1 ? 'pred-1' : pred === 0 ? 'pred-0' : '';
            html += `<button class="tree-option ${idx === 0 ? 'active' : ''} ${predClass}" data-tree-idx="${idx}">`;
            html += `<div class="tree-option-header">#${tree.tree_number} Tree ${tree.tree_number}</div>`;
            html += `<div class="tree-option-split-left">${tree.left_split}</div>`;
            html += `<div class="tree-option-split-right">${tree.right_split}</div>`;
            html += `</button>`;
        });
        html += `</div>`;
        html += `<div class="trees-display-panel"><canvas id="tree-canvas" class="tree-canvas"></canvas></div>`;
        html += `</div>`;
    } else {
        html += `<p>展開可能なツリーがありません</p>`;
    }
    html += `</div>`;

    section.innerHTML = html;

    if (result.tree_list && result.tree_list.length > 0) {
        updateCellBatchCount(i, j, result.tree_list);
        bindTreeListEvents(result);
        drawTreeOnCanvas(result.tree_list[0].tree);

        if (typeof initializeMatching === 'function') {
            initializeMatching(result.tree_list[0].tree, ckyState.bunsetsuList);
        }
    }
}

function updateCellBatchCount(i, j, treeList) {
    const pred1 = treeList.filter(t => t.root_pred === 1).length;
    const pred0 = treeList.filter(t => t.root_pred === 0).length;

    const cell = document.querySelector(`td[data-i="${i}"][data-j="${j}"]`);
    if (!cell) return;

    const countDiv = cell.querySelector('.cell-count');
    if (countDiv) {
        let display = '';
        if (pred1 > 0) display += `<span class="pred-count pred1-color">${pred1}</span>`;
        if (pred0 > 0) display += `<span class="pred-count pred0-color">${pred0}</span>`;
        if (!display) display = '<span class="pred-count">0</span>';
        countDiv.innerHTML = display;
    }
}

function bindTreeListEvents(result) {
    document.querySelectorAll('.tree-option').forEach(btn => {
        btn.addEventListener('click', function() {
            const idx = parseInt(this.dataset.treeIdx);
            if (isNaN(idx) || !result.tree_list[idx]) return;

            document.querySelectorAll('.tree-option').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            drawTreeOnCanvas(result.tree_list[idx].tree);

            if (typeof initializeMatching === 'function') {
                initializeMatching(result.tree_list[idx].tree, ckyState.bunsetsuList);
            }
        });
    });
}

async function initializeMatching(tree, bunsetsuList) {
    try {
        await PatternMatchingFlow.init(tree, bunsetsuList);
    } catch (error) {
        console.error('[CKY] Matching error:', error);
    }
}

document.addEventListener('DOMContentLoaded', initCKY);

const API = {

    async bunsetu(text) {
        const response = await fetch('/api/bunsetu', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        return response.json();
    },

    async cky(data) {
        const response = await fetch('/api/cky', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data })
        });

        if (!response.ok) {
            throw new Error(`CKY API Error: ${response.status}`);
        }

        return response.json();
    },

    async ckyExpandCell(data, cell, pred_threshold = 1) {
        const response = await fetch('/api/cky/expand-cell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data, cell, pred_threshold })
        });

        if (!response.ok) {
            throw new Error(`CKY Expand Cell API Error: ${response.status}`);
        }

        return response.json();
    }
};

const DOM = {

    get(selector) {
        return document.querySelector(selector);
    },

    getAll(selector) {
        return document.querySelectorAll(selector);
    },

    on(selector, event, handler) {
        const el = this.get(selector);
        if (el) el.addEventListener(event, handler);
    },

    setText(selector, text) {
        const el = this.get(selector);
        if (el) el.textContent = text;
    },

    setHTML(selector, html) {
        const el = this.get(selector);
        if (el) el.innerHTML = html;
    },

    addClass(selector, className) {
        const el = this.get(selector);
        if (el) el.classList.add(className);
    },

    removeClass(selector, className) {
        const el = this.get(selector);
        if (el) el.classList.remove(className);
    },

    toggleClass(selector, className, condition) {
        const el = this.get(selector);
        if (el) el.classList.toggle(className, condition);
    }
};

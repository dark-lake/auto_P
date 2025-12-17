highlight_js_func = """(() => {
    /* ============================================================
     * AX → DOM 高亮服务（evaluate_script 专用）
     * ============================================================
     */
    
    /* -----------------------------
     * 工具函数
     * ----------------------------- */
    function isVisibleRect(rect) {
        return (
            rect.width > 0 &&
            rect.height > 0 &&
            rect.bottom > 0 &&
            rect.right > 0 &&
            rect.top < window.innerHeight &&
            rect.left < window.innerWidth
        );
    }
    
    function getLabelledByText(el) {
        const ids = el.getAttribute?.("aria-labelledby");
        if (!ids) return [];
        return ids
            .split(/\\s+/)
            .map(id => document.getElementById(id))
            .filter(Boolean)
            .map(n => n.innerText?.trim())
            .filter(Boolean);
    }
    
    /* ============================================================
     * 1. 构建 AX → DOM 索引
     * ============================================================ */
    window.__AX_BUILD_INDEX__ = () => {
        const index = [];
        
        document.querySelectorAll("*").forEach(el => {
            try {
                const ax = window.getComputedAccessibleNode?.(el);
                if (!ax) return;
                
                const rect = el.getBoundingClientRect();
                if (!isVisibleRect(rect)) return;
                
                index.push({
                    role: ax.role || null,
                    name: ax.name || "",
                    tag: el.tagName.toLowerCase(),
                    rect: {
                        x: rect.x,
                        y: rect.y,
                        w: rect.width,
                        h: rect.height
                    },
                    el
                });
            } catch (_) {}
        });
        
        window.__AX_DOM_INDEX__ = index;
        
        return {
            ok: true,
            count: index.length
        };
    };
    
    /* ============================================================
     * 2. AX 查询 → 精确定位 DOM
     * ============================================================ */
    window.__AX_FIND_NODE__ = (query) => {
        const { role, name } = query || {};
        let candidates = window.__AX_DOM_INDEX__ || [];
        
        if (!candidates.length) {
            return { ok: false, reason: "index_not_built" };
        }
        
        if (role) {
            candidates = candidates.filter(n => n.role === role);
        }
        
        if (name) {
            candidates = candidates.filter(n => {
                const texts = [];
                
                // AX name（最可靠）
                if (n.name) texts.push(n.name);
                
                // textbox 特有补充
                if (role === "textbox") {
                    if (n.el.placeholder) texts.push(n.el.placeholder.trim());
                    if (n.el.value) texts.push(n.el.value.trim());
                    texts.push(...getLabelledByText(n.el));
                }
                
                return texts.some(t => t === name);
            });
        }
        
        if (!candidates.length) {
            return { ok: false, reason: "no_match" };
        }
        
        /* -----------------------------
         * 候选排序（非常关键）
         * ----------------------------- */
        candidates.sort((a, b) => {
            let s1 = 0, s2 = 0;
            
            // 可交互优先
            if (typeof a.el.click === "function") s1 += 10;
            if (typeof b.el.click === "function") s2 += 10;
            
            // 原生语义优先
            if (a.tag === "button" || a.tag === "a") s1 += 3;
            if (b.tag === "button" || b.tag === "a") s2 += 3;
            
            // 视口中心优先
            const cy = window.innerHeight / 2;
            s1 -= Math.abs(a.rect.y - cy) / 100;
            s2 -= Math.abs(b.rect.y - cy) / 100;
            
            return s2 - s1;
        });
        
        return {
            ok: true,
            count: candidates.length,
            node: candidates[0]
        };
    };
    
    /* ============================================================
     * 3. 高亮渲染
     * ============================================================ */
    window.__AX_HIGHLIGHT__ = (node, duration = 3000) => {
        const el = node?.el;
        if (!el) return { ok: false };
        
        const rect = el.getBoundingClientRect();
        const overlay = document.createElement("div");
        
        Object.assign(overlay.style, {
            position: "fixed",
            top: rect.top + "px",
            left: rect.left + "px",
            width: rect.width + "px",
            height: rect.height + "px",
            border: "3px solid #ff4d4f",
            boxShadow: "0 0 12px rgba(255,77,79,.8)",
            pointerEvents: "none",
            zIndex: 2147483647,
            transition: "opacity .3s ease"
        });
        
        document.body.appendChild(overlay);
        
        setTimeout(() => {
            overlay.style.opacity = "0";
            setTimeout(() => overlay.remove(), 300);
        }, duration);
        
        return { ok: true };
    };
    
    /* ============================================================
     * 4. 一体化快捷接口（给 Python 用）
     * ============================================================ */
    window.__AX_HIGHLIGHT_BY_A11Y__ = (query, duration = 3000) => {
        if (!window.__AX_DOM_INDEX__ || !window.__AX_DOM_INDEX__.length) {
            window.__AX_BUILD_INDEX__();
        }
        
        const res = window.__AX_FIND_NODE__(query);
        if (!res.ok) return res;
        
        window.__AX_HIGHLIGHT__(res.node, duration);
        return {
            ok: true,
            matchedCount: res.count,
            role: query.role,
            name: query.name
        };
    };
    
    // 立即构建索引
    window.__AX_BUILD_INDEX__();
    
    return {
        ok: true,
        api: [
            "__AX_BUILD_INDEX__",
            "__AX_FIND_NODE__",
            "__AX_HIGHLIGHT__",
            "__AX_HIGHLIGHT_BY_A11Y__"
        ]
    };
})"""

highlight_func = {
    "function": highlight_js_func
}

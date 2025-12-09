// ==UserScript==
// @name         Emby 多站点搜索
// @namespace    http://tampermonkey.net/
// @version      6.0
// @description  Emby 多站点搜索 + 轮询 + 番号识别 + 扫描 + 剧集显示第几季第几集 + 网站入库状态（网站可绑定Emby服务端）
// @author       Hu
// @match        http*://*/*
// @exclude      http*://gying.org/*
// @grant        GM_registerMenuCommand
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// ==/UserScript==

(function () {
    'use strict';

    /* ===================== 存储键 ===================== */
    const SERVER_KEY = "EMBY_SERVER_LIST_v1"; // Emby 服务端列表
    const SITE_KEY = "EMBY_SITE_LIST_v1";     // 网站列表（每个网站可绑定一个服务端）
    const POS_KEY = "EMBY_PANEL_POS_v1";

    const getServers = () => GM_getValue(SERVER_KEY, []);
    const setServers = v => GM_setValue(SERVER_KEY, v);
    const getSites = () => GM_getValue(SITE_KEY, []);
    const setSites = v => GM_setValue(SITE_KEY, v);
    const getPos = () => GM_getValue(POS_KEY, { top: 100, left: window.innerWidth - 120 });
    const setPos = v => GM_setValue(POS_KEY, v);

    /* ===================== 样式（保留你的风格） ===================== */
    GM_addStyle(`
.emby-panel,.emby-setting{
position:fixed;z-index:2147483647;background:#fff;border-radius:12px;
box-shadow:0 10px 30px rgba(0,0,0,.18);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI";
}
.emby-panel{width:500px;max-height:80vh;overflow:auto;}
.emby-header{
padding:12px 16px;font-weight:600;border-bottom:1px solid #eee;
display:flex;align-items:center;cursor:move;user-select:none;
}
.emby-body{padding:14px}
.emby-row{display:flex;gap:8px;margin-bottom:10px}
.emby-row input{flex:1;padding:8px 10px;border-radius:8px;border:1px solid #ddd;}
.emby-btn{padding:8px 14px;border:none;border-radius:8px;background:#165DFF;color:#fff;cursor:pointer;}
.emby-btn.ghost{background:#f2f3f5;color:#333}
.emby-item{display:flex;align-items:center;border:1px solid #eee;border-radius:8px;padding:6px;margin-bottom:8px;gap:8px;}
.emby-item img{width:60px;height:80px;object-fit:cover;border-radius:6px;}
.emby-title{font-weight:600;cursor:pointer;}
.emby-type{font-size:12px;color:#64748b;margin-top:2px;display:flex;align-items:center;gap:6px;}
.status-text{font-size:12px;color:#f97316;margin-top:4px;}
#minimizeBtn, #clearBtn {display:inline-flex;justify-content:center;align-items:center;width:28px;height:28px;border-radius:50%;background-color:#f0f0f0;color:#333;font-size:16px;font-weight:bold;cursor:pointer;transition:all 0.2s;}
#minimizeBtn:hover, #clearBtn:hover {background-color:#165DFF;color:#fff;}
.autofill-btn {display:inline-block;margin-left:6px;padding:4px 10px;font-size:13px;color:#fff;background: linear-gradient(135deg, rgba(24, 144, 255, 0.7), rgba(64, 169, 255, 0.7));border:none;border-radius:6px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,0.15);transition:all 0.2s ease;}
.autofill-btn:hover {background:linear-gradient(135deg,#40a9ff,#69c0ff);transform:translateY(-1px);box-shadow:0 4px 10px rgba(0,0,0,0.2);}
.autofill-btn:active {background:linear-gradient(135deg,#096dd9,#1890ff);transform:translateY(0);box-shadow:0 2px 6px rgba(0,0,0,0.15);}
.site-row {display:flex;justify-content:space-between;align-items:center;padding:6px;border:1px solid #eee;border-radius:8px;margin-bottom:6px;}
.site-controls button {margin-left:6px;}
`);

    /* ===================== 共用工具：拖拽 ===================== */
    function dragElement(elmnt, handle) {
        const dragTarget = handle || elmnt;
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        dragTarget.onmousedown = dragMouseDown;

        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
            elmnt.dataset.dragged = true;
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
            if (elmnt.id === "embyMiniBtn") {
                setPos({ left: elmnt.offsetLeft, top: elmnt.offsetTop });
            }
        }
    }

    /* ===================== 获取 serverId（缓存） ===================== */
    async function getServerId(serverObj) {
        if (!serverObj) return null;
        if (serverObj.serverId) return serverObj.serverId;
        return new Promise(resolve => {
            GM_xmlhttpRequest({
                method: "GET",
                url: serverObj.server.replace(/\/$/, "") + "/emby/System/Info",
                headers: serverObj.useHeader ? { "X-Emby-Token": serverObj.key } : {},
                onload: r => {
                    try {
                        const id = JSON.parse(r.responseText).Id;
                        serverObj.serverId = id;
                        // persist back
                        const servers = getServers();
                        servers.forEach((s, i) => { if (s.server === serverObj.server) servers[i].serverId = id; });
                        setServers(servers);
                        resolve(id);
                    } catch (e) {
                        console.warn("getServerId fail", e);
                        resolve(null);
                    }
                },
                onerror: () => resolve(null),
                timeout: 15000
            });
        });
    }
    /* ===================== 搜索面板（保留原行为 & 悬浮按钮） ===================== */
    function createSearchPanel() {
        if (document.getElementById("embyPanel")) return;

        const pos = getPos();
        const boxWidth = 500;
        const box = document.createElement("div");
        box.id = "embyPanel";
        box.className = "emby-panel";
        box.style.position = "fixed";
        box.style.display = "none";
        box.style.width = boxWidth + "px";
        box.style.top = "500px";
        box.style.left = (window.innerWidth - boxWidth) / 2 + "px";

        box.innerHTML = `
        <div class="emby-header" id="embyDrag">
          <span>Emby 多站点搜索</span>
        <div style="margin-left:auto; display:flex; gap:6px; align-items:center;">
            <span id="minimizeBtn" title="最小化">➖</span>
            <span id="clearBtn" title="清空">♻️</span>
            <span id="openServerBtn" title="服务端管理" style="margin-left:8px;cursor:pointer">⚙️</span>
            <span id="openSiteBtn" title="网站管理" style="margin-left:6px;cursor:pointer">🌐</span>
        </div>
        </div>
        <div class="emby-body">
          <div class="emby-row">
            <input id="embyKeyword" placeholder="输入资源名称">
            <button id="embySearchBtn" class="emby-btn">搜索</button>
          </div>
          <div id="embyResult"></div>
        </div>`;

        document.body.appendChild(box);

        document.getElementById("embySearchBtn").onclick = doSearch;
        document.getElementById("embyKeyword").onkeydown = e => { if (e.key === "Enter") doSearch(); };


        dragElement(box, document.getElementById("embyDrag"));

        // 悬浮最小化按钮
        let miniBtn = document.getElementById("embyMiniBtn");
        if (!miniBtn) {
            miniBtn = document.createElement("div");
            miniBtn.id = "embyMiniBtn";
            miniBtn.textContent = "🔍Emby";
            miniBtn.title = "点击展开搜索面板";
            Object.assign(miniBtn.style, {
                position: "fixed",
                top: (pos.top || 100) + "px",
                left: (pos.left || window.innerWidth - 120) + "px",
                padding: "8px 12px",
                borderRadius: "20px",
                background: "#1677ff",
                color: "#fff",
                cursor: "pointer",
                zIndex: 999999,
                fontSize: "16px",
                textAlign: "center",
                lineHeight: "16px",
                boxShadow: "0 2px 10px rgba(0,0,0,.3)",
                userSelect: "none"
            });
            document.body.appendChild(miniBtn);
        }
        dragElement(miniBtn);
        miniBtn.onclick = () => {
            box.style.display = "block";
            miniBtn.style.display = "none";
            if (!box.dataset.dragged) { box.style.top = "50%"; box.style.left = "50%"; box.style.transform = "translate(-50%,-50%)"; }
            else { box.style.transform = "none"; }
        };

        document.getElementById("minimizeBtn").onclick = () => { box.style.display = "none"; miniBtn.style.display = "block"; };
        document.getElementById("clearBtn").onclick = () => {
            document.getElementById("embyKeyword").value = "";
            document.getElementById("embyResult").innerHTML = "";
        };

        document.getElementById("openServerBtn").onclick = () => {
            showConfigPanel();
            document.getElementById("tabServer").click(); // 自动定位到 服务端 TAB
        };

        document.getElementById("openSiteBtn").onclick = () => {
            showConfigPanel();
            document.getElementById("tabSite").click(); // 自动定位到 网站 TAB
        };

    }

    /* ===================== 获取最新剧集信息 ===================== */
    function getLatestEpisodeInfo(serverObj, seriesId, callback) {
        if (!serverObj) return callback("服务端未配置");
        const base = serverObj.server.replace(/\/$/, "");
        const url = `${base}/emby/Shows/${seriesId}/Episodes?Limit=1&SortBy=PremiereDate&SortOrder=Descending`;

        GM_xmlhttpRequest({
            method: "GET",
            url: serverObj.useHeader ? url : (url + "&api_key=" + encodeURIComponent(serverObj.key || "")),
            headers: serverObj.useHeader ? { "X-Emby-Token": serverObj.key } : {},
            responseType: "json",
            onload: r => {
                try {
                    const items = r.response?.Items || [];
                    if (!items.length) return callback("已完结 / 无集信息");

                    const ep = items[0];
                    const seasonNum = ep.ParentIndexNumber || "?";
                    const episodeNum = ep.IndexNumber || "?";

                    // 判断连载状态（Emby Show对象里有 Status 字段）
                    // 需要先获取剧集详情
                    const showUrl = `${base}/emby/Shows/${seriesId}`;
                    GM_xmlhttpRequest({
                        method: "GET",
                        url: serverObj.useHeader ? showUrl : (showUrl + "?api_key=" + encodeURIComponent(serverObj.key || "")),
                        headers: serverObj.useHeader ? { "X-Emby-Token": serverObj.key } : {},
                        responseType: "json",
                        onload: r2 => {
                            try {
                                const show = r2.response;
                                const status = show.Status || "Ended"; // Emby里 Status: "Continuing"/"Ended"
                                const statusText = status === "Continuing" ? "连载中" : "完结";
                                callback(`${statusText} · 更新到 第${seasonNum}季 第${episodeNum}集`);
                            } catch (e) {
                                callback(`更新到 第${seasonNum}季 第${episodeNum}集`);
                            }
                        },
                        onerror: () => callback(`更新到 第${seasonNum}季 第${episodeNum}集`)
                    });

                } catch (e) {
                    callback("集信息解析失败");
                }
            },
            onerror: () => callback("集信息获取失败")
        });
    }


    /* ===================== 搜索逻辑（遍历所有 Emby 服务端） ===================== */
    function doSearch() {
        const kw = document.getElementById("embyKeyword").value.trim();
        if (!kw) return alert("请输入关键词");

        const wrap = document.getElementById("embyResult");
        wrap.innerHTML = "";

        const servers = getServers();
        if (!servers.length) {
            wrap.innerHTML = `<div class="status-text">未配置任何 Emby 服务端，请先在“服务端管理”中添加。</div>`;
            return;
        }

        servers.forEach(server => {
            const block = document.createElement("div");
            block.className = "emby-server-block";
            block.innerHTML = `<div class="status-text">站点 ${server.name} 搜索中...</div>`;
            wrap.appendChild(block);
            searchServer(server, kw, block);
        });
    }


    /* ===================== 标题精确匹配相关工具函数 ===================== */

    // 标题标准化
    function normalizeTitle(str) {
        if (!str) return "";
        return str
            .toLowerCase()
            .replace(/\s+/g, "")
            .replace(/[^\w\u4e00-\u9fa5]/g, "");
    }

    // 标题相似度判断
    function isTitleMatch(a, b) {
        if (!a || !b) return false;
        const na = normalizeTitle(a);
        const nb = normalizeTitle(b);
        return na === nb || na.includes(nb) || nb.includes(na);
    }


    /* ===================== 搜索单个 Emby 服务端 ===================== */
    function searchServer(serverObj, kw, wrap) {
        const base = serverObj.server.replace(/\/$/, "");

        // ✅ 使用你提供的更精准 URL 参数
        const url = `${base}/emby/Items` +
              `?SearchTerm=${encodeURIComponent(kw)}` +
              `&IncludeItemTypes=Movie,Series` +
              `&Recursive=true` +
              `&Fields=ProductionYear,OriginalTitle` +
              `&Limit=20`;

        GM_xmlhttpRequest({
            method: "GET",
            url: serverObj.useHeader
            ? url
            : (url + "&api_key=" + encodeURIComponent(serverObj.key || "")),
            headers: serverObj.useHeader
            ? { "X-Emby-Token": serverObj.key || "" }
            : {},
            responseType: "json",
            timeout: 20000,

            onload: r => {
                wrap.innerHTML = "";
                const list = r.response?.Items || [];

                // ✅ 只保留 Movie / Series
                const filteredList = list.filter(it =>
                                                 it && (it.Type === "Movie" || it.Type === "Series")
                                                );

                // ===== 精准匹配增强逻辑 =====
                const exactList = filteredList.filter(it => {
                    const nameMatch =
                          isTitleMatch(it.Name, kw) ||
                          isTitleMatch(it.OriginalTitle, kw);

                    const yearMatch =
                          !it.ProductionYear ||
                          !/\d{4}/.test(kw) ||
                          kw.includes(String(it.ProductionYear));

                    return nameMatch && yearMatch;
                });

                // 如果精准匹配有结果就用精准的，否则退回普通结果
                const finalList = exactList.length ? exactList : filteredList;

                // ===== 未入库判断 =====
                if (!finalList.length) {
                    const st = document.createElement("div");
                    st.className = "status-text";
                    st.innerHTML = `
                    <span style="color:#999">【${serverObj.name}】</span>
                    <span style="margin-left:6px;color:#F52800">未入库</span>
                `;

                    if (serverObj.scanPaths?.length) {
                        const btn = document.createElement("button");
                        btn.className = "autofill-btn";
                        btn.textContent = "触发扫描";
                        btn.onclick = () =>
                        triggerLibraryScan(serverObj, st, kw, () => doSearch());
                        st.appendChild(btn);
                    }

                    wrap.appendChild(st);
                    return;
                }

                // ===== 渲染搜索结果 =====
                finalList.forEach(it => {
                    const div = document.createElement("div");
                    div.className = "emby-item";

                    const tag = it.ImageTags?.Primary;
                    const imgUrl = tag
                    ? `${base}/emby/Items/${it.Id}/Images/Primary?tag=${tag}&maxWidth=60` +
                          (!serverObj.useHeader && serverObj.key
                           ? `&api_key=${encodeURIComponent(serverObj.key)}`
                           : "")
                    : "";

                    div.innerHTML = `
                    <img src="${imgUrl}">
                    <div style="flex:1">
                        <div class="emby-title" title="${it.Name}">
                            ${it.Name}
                        </div>
                        <div class="emby-type" id="type_${serverObj.name}_${it.Id}"></div>
                        <div style="font-size:12px">${serverObj.name}</div>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;">
                        <button class="emby-btn ghost openBtn">▶ 打开</button>
                    </div>
                `;

                    wrap.appendChild(div);

                    // 打开逻辑
                    const open = () => {
                        getServerId(serverObj).then(id => {
                            if (id) {
                                window.open(`${base}/web/index.html#!/item?id=${it.Id}&serverId=${id}`);
                            } else {
                                window.open(`${base}/web/index.html#!/item?id=${it.Id}`);
                            }
                        });
                    };

                    div.querySelector(".openBtn").onclick = open;
                    div.querySelector(".emby-title").ondblclick = open;

                    // 类型展示
                    const dom = div.querySelector(`#type_${serverObj.name}_${it.Id}`);

                    if (it.Type === "Series") {
                        dom.textContent = "剧集 · 获取中...";
                        getLatestEpisodeInfo(serverObj, it.Id, t => {
                            dom.innerHTML = `剧集<br>${t}`;
                            dom.style.whiteSpace = "normal";
                            dom.style.lineHeight = "1.3em";
                        });
                    } else if (it.Type === "Movie") {
                        dom.textContent = "电影";
                    }
                });
            },

            onerror: () => {
                wrap.innerHTML = `<div class="status-text">【${serverObj.name}】请求失败</div>`;
            }
        });
    }


    /* ===================== 扫描媒体库（支持等待并刷新） ===================== */
    function triggerLibraryScan(serverObj, statusDiv, keyword, callbackAfter) {
        const base = serverObj.server.replace(/\/$/, "");
        const paths = serverObj.scanPaths || ["/"];
        let index = 0;

        Object.assign(statusDiv.style, { fontWeight: "bold", color: "#F52800", backgroundColor: "#fff4f4", padding: "4px 8px", borderRadius: "4px", display: "inline-block", transition: "all 0.2s" });

        function next() {
            if (index >= paths.length) {
                if (callbackAfter) callbackAfter();
                return;
            }
            const p = paths[index];
            let wait60 = 60;
            const t1 = setInterval(() => {
                statusDiv.textContent = `${serverObj.name} ${p} 60s 后扫描 倒计时...${wait60--}s`;
                statusDiv.style.opacity = (wait60 % 2 === 0 ? "1" : "0.6");
                if (wait60 < 0) {
                    clearInterval(t1);
                    const url = `${base}/emby/Library/Refresh?path=${encodeURIComponent(p)}&recursive=true`;
                    GM_xmlhttpRequest({
                        method: "POST",
                        url: serverObj.useHeader ? url : (url + "&api_key=" + encodeURIComponent(serverObj.key || "")),
                        headers: serverObj.useHeader ? { "X-Emby-Token": serverObj.key } : {},
                        onload: () => {
                            let w10 = 10;
                            const t2 = setInterval(() => {
                                statusDiv.textContent = `扫描完成 ${w10--}s 后重搜`;
                                statusDiv.style.opacity = (w10 % 2 === 0 ? "1" : "0.6");
                                if (w10 < 0) {
                                    clearInterval(t2);
                                    if (typeof callbackAfter === "function") callbackAfter();
                                    index++; next();
                                }
                            }, 1000);
                        },
                        onerror: () => {
                            statusDiv.textContent = `扫描请求失败`;
                            if (typeof callbackAfter === "function") callbackAfter();
                        }
                    });
                }
            }, 1000);
        }
        next();
    }

    /* ===================== 自动填写函数 ===================== */
    function fillInput(value) {
        const input = document.getElementById("embyKeyword");
        if (!input) return;
        input.value = value;
        input.focus();
        input.style.transition = "background 0.3s";
        input.style.background = "#fffae6";
        setTimeout(() => input.style.background = "", 300);
        const event = new Event('input', { bubbles: true });
        input.dispatchEvent(event);
    }

    // 清理标题（例如去除年番后面的数字，处理季节信息等）
    function cleanTitle(title) {
        title = title.replace(/\s*(第一|第二|第三|第四|第五|第六|第七|第八|第九|第十)\s*季/g, '');
        title = title.replace(/\s*年番\s*(\d+)\s*/g, '');
        title = title.replace(/\s*(剧场版|OVA|番外篇|特别篇)/g, '');
        title = title.replace(/(\d{4})年/g, '');
        title = title.replace(/[\s]+/g, ' ').trim();
        return title;
    }

    /* ===================== 番号/标题自动填写 & 入库检测（原代码） ===================== */
    const TMDB_API_KEY = "51f772f97bf0233c711f948135a5a358";

    function detectAll() {
        const iconUrl = "https://raw.githubusercontent.com/lige47/QuanX-icon-rule/main/icon/emby.png";

        async function autoCheckStatus(element, text, linkElement) {
            try {
                const sites = getSites();
                const host = window.location.host;
                let matchedSite = null;
                for (const s of sites) {
                    try {
                        if (!s.url) continue;
                        const u = (new URL(s.url)).host;
                        if (host.includes(u) || u.includes(host)) { matchedSite = s; break; }
                        if (window.location.href.includes(s.url)) { matchedSite = s; break; }
                    } catch (e) {
                        if (s.url && window.location.href.includes(s.url)) { matchedSite = s; break; }
                    }
                }
                if (!matchedSite) {
                    element.textContent = "未配置";
                    element.parentNode.style.background = "#f5222d";
                    element.parentNode.style.color = "#fff";
                    if (linkElement) linkElement.style.display = "none";
                    return;
                }

                const servers = getServers();
                const serverObj = servers[matchedSite.serverIndex];
                if (!serverObj) {
                    element.textContent = "未绑定";
                    element.parentNode.style.background = "#f5222d";
                    element.parentNode.style.color = "#fff";
                    if (linkElement) linkElement.style.display = "none";
                    return;
                }

                checkTitleOnServer(serverObj, text, present => {
                    if (present) {
                        element.textContent = "已入库";
                        element.parentNode.style.background = "#52c41a";
                        if (linkElement) linkElement.style.display = "none";
                    } else {
                        element.textContent = "未入库";
                        element.parentNode.style.background = "#f5222d";
                        if (linkElement) linkElement.style.display = "inline-block";
                    }
                    element.parentNode.style.color = "#fff";
                }, err => {
                    element.textContent = "⚠ 检测失败";
                    element.parentNode.style.background = "#faad14";
                    element.parentNode.style.color = "#000";
                    if (linkElement) linkElement.style.display = "none";
                });
            } catch (e) {
                element.textContent = "⚠ 错误";
                element.parentNode.style.background = "#faad14";
                element.parentNode.style.color = "#000";
                if (linkElement) linkElement.style.display = "none";
            }
        }

        // 处理番号
        document.querySelectorAll('div.panel-block.first-block').forEach(block => {
            if (block.dataset.doneNumber) return;
            const span = block.querySelector('span.value');
            if (!span) return;
            let code = span.textContent.trim();
            code = cleanTitle(code);

            const btnWrap = document.createElement('div');
            btnWrap.style.marginTop = '4px';
            span.parentNode.appendChild(btnWrap);

            // 自动填写番号按钮
            const autofillBtn = document.createElement('button');
            autofillBtn.className = 'autofill-btn';
            autofillBtn.textContent = '自动填写番号';
            autofillBtn.onclick = () => fillInput(code);
            btnWrap.appendChild(autofillBtn);

            // 入库状态按钮
            const statusBtn = document.createElement('button');
            statusBtn.className = 'autofill-btn';
            statusBtn.style.display = 'flex';
            statusBtn.style.alignItems = 'center';
            statusBtn.style.gap = '4px';
            statusBtn.style.marginLeft = '6px';

            const img = document.createElement('img');
            img.src = iconUrl;
            img.style.width = '16px';
            img.style.height = '16px';
            statusBtn.appendChild(img);

            const statusText = document.createElement('span');
            statusText.textContent = "检测中...";
            statusBtn.appendChild(statusText);

            btnWrap.appendChild(statusBtn);

            autoCheckStatus(statusText, code); // 番号不传链接
            block.dataset.doneNumber = 1;
        });

        // 处理标题
        document.querySelectorAll('div.main-ui-meta h1').forEach(h1 => {
            if (h1.dataset.doneTitle) return;
            const div = h1.querySelector('div');
            if (!div) return;
            let title = div.textContent.trim();
            title = cleanTitle(title);

            const btnWrap = document.createElement('div');
            btnWrap.style.marginTop = '4px';
            h1.appendChild(btnWrap);

            // 自动填写标题按钮
            const autofillBtn = document.createElement('button');
            autofillBtn.className = 'autofill-btn';
            autofillBtn.textContent = '自动填写标题';
            autofillBtn.onclick = () => fillInput(title);
            btnWrap.appendChild(autofillBtn);

            // 入库状态按钮
            const statusBtn = document.createElement('button');
            statusBtn.className = 'autofill-btn';
            statusBtn.style.display = 'flex';
            statusBtn.style.alignItems = 'center';
            statusBtn.style.gap = '4px';
            statusBtn.style.marginLeft = '6px';

            const img = document.createElement('img');
            img.src = iconUrl;
            img.style.width = '16px';
            img.style.height = '16px';
            statusBtn.appendChild(img);

            const statusText = document.createElement('span');
            statusText.textContent = "检测中...";
            statusBtn.appendChild(statusText);

            btnWrap.appendChild(statusBtn);

            // 跳转到 HDHive 链接（仅标题使用）
            const hdhiveLink = document.createElement('a');
            hdhiveLink.className = 'autofill-btn';
            hdhiveLink.textContent = '跳转到 HDHive';
            hdhiveLink.style.display = 'none'; // 初始隐藏
            hdhiveLink.style.textDecoration = 'none';
            hdhiveLink.style.color = '#fff';
            hdhiveLink.target = '_blank';
            hdhiveLink.rel = 'noopener noreferrer';

            // 异步设置 href
            (async () => {
                const tmdbId = await getTmdbId(title);
                const type = await getTitleType(tmdbId);
                let url;
                if (type === 'movie') {
                    url = `https://hdhive.com/tmdb/movie/${tmdbId}`;
                } else if (type === 'tv') {
                    url = `https://hdhive.com/tmdb/tv/${tmdbId}`;
                }
                hdhiveLink.href = url;
            })();

            btnWrap.appendChild(hdhiveLink);

            autoCheckStatus(statusText, title, hdhiveLink); // 传入 HDHive 链接
            h1.dataset.doneTitle = 1;
        });
    }


    // ===================== TMDB 相关函数（标题专用） =====================
    /* ===================== TMDB 原函数（不删） ===================== */
    async function getTmdbId(title) {
        const encodedTitle = encodeURIComponent(title);
        const url = `https://api.themoviedb.org/3/search/multi?api_key=${TMDB_API_KEY}&query=${encodedTitle}`;
        const response = await fetch(url);
        const data = await response.json();
        if (data.results && data.results.length > 0) {
            return data.results[0].id;
        }
        return null;
    }

    async function getTitleType(tmdbId) {
        const url = `https://api.themoviedb.org/3/movie/${tmdbId}?api_key=${TMDB_API_KEY}`;
        const response = await fetch(url);
        const movieData = await response.json();
        if (movieData.status_code === 34) {
            const tvUrl = `https://api.themoviedb.org/3/tv/${tmdbId}?api_key=${TMDB_API_KEY}`;
            const tvResponse = await fetch(tvUrl);
            const tvData = await tvResponse.json();
            if (tvData.status_code !== 34) return 'tv';
        }
        if (movieData.status_code !== 34) return 'movie';
        return 'unknown';
    }


    /* =====================【增强版】Emby 入库检测函数（兼容原调用） ===================== */
    function checkTitleOnServer(serverObj, title, cbSuccess, cbError) {
        if (!serverObj) {
            if (typeof cbError === "function") cbError("no server");
            return;
        }

        const base = serverObj.server.replace(/\/$/, "");

        // ✅ 新增更精准参数（兼容旧逻辑）
        const url =
              `${base}/emby/Items` +
              `?SearchTerm=${encodeURIComponent(title)}` +
              `&IncludeItemTypes=Movie,Series` +
              `&Recursive=true` +
              `&Fields=ProductionYear,OriginalTitle` +
              `&Limit=20`;

        GM_xmlhttpRequest({
            method: "GET",
            url: serverObj.useHeader ? url : (url + "&api_key=" + encodeURIComponent(serverObj.key || "")),
            headers: serverObj.useHeader ? { "X-Emby-Token": serverObj.key } : {},
            responseType: "json",
            onload: r => {
                try {
                    const list = r.response?.Items || [];

                    if (!list.length) {
                        if (typeof cbSuccess === "function") cbSuccess(false);
                        return;
                    }

                    // ✅ 不删除原逻辑，只做增强判断
                    const matched = list.some(it => {
                        const nameOk =
                              it.Name === title ||
                              isTitleMatch(it.Name, title) ||
                              isTitleMatch(it.OriginalTitle, title);

                        const yearOk =
                              !it.ProductionYear ||
                              !/\d{4}/.test(title) ||
                              title.includes(String(it.ProductionYear));

                        return nameOk && yearOk;
                    });

                    if (typeof cbSuccess === "function") cbSuccess(matched);
                } catch (e) {
                    if (typeof cbError === "function") cbError(e);
                }
            },
            onerror: e => { if (typeof cbError === "function") cbError(e); },
            timeout: 15000
        });
    }


    /* ===================== 电影信息自动检测入库状态 ===================== */
    function detectMovieInfo() {
        const iconUrl = "https://raw.githubusercontent.com/lige47/QuanX-icon-rule/main/icon/emby.png";

        function cleanTitle(title) {
            // 去除季节信息（如 第一季、第二季、第三季等）
            title = title.replace(/\s*(第一|第二|第三|第四|第五|第六|第七|第八|第九|第十)\s*季/g, '');
            // 去除“年番”后面跟随的任何数字（如“年番1”，“年番2”...）
            title = title.replace(/\s*年番\s*(\d+)\s*/g, '');
            // 去除剧场版、OVA等标识
            title = title.replace(/\s*(剧场版|OVA|番外篇|特别篇)/g, '');
            // 去除年份标识（如 2022年），但不删除其他有效的年份部分
            title = title.replace(/(\d{4})年/g, '');
            // 去除多余空格
            title = title.replace(/[\s]+/g, ' ').trim();
            return title;
        }


        // 实际的入库检测函数
        async function autoCheckStatus(element, text) {
            try {
                const sites = getSites();
                const host = window.location.host;
                let matchedSite = null;

                // Find matched site based on URL
                for (const s of sites) {
                    try {
                        if (!s.url) continue;
                        const u = (new URL(s.url)).host;
                        if (host.includes(u) || u.includes(host) || window.location.href.includes(s.url)) {
                            matchedSite = s;
                            break;
                        }
                    } catch (e) {
                        if (s.url && window.location.href.includes(s.url)) {
                            matchedSite = s;
                            break;
                        }
                    }
                }

                if (!matchedSite) {
                    element.textContent = "未配置";
                    element.parentNode.style.background = "#f5222d";
                    element.parentNode.style.color = "#fff";
                    return;
                }

                const servers = getServers();
                const serverObj = servers[matchedSite.serverIndex];
                if (!serverObj) {
                    element.textContent = "未绑定";
                    element.parentNode.style.background = "#f5222d";
                    element.parentNode.style.color = "#fff";
                    return;
                }

                // 清理标题
                const cleanedTitle = cleanTitle(text);

                console.log(`开始检测标题: ${cleanedTitle}`);
                // 调用真实的 checkTitleOnServer 检测
                checkTitleOnServer(serverObj, cleanedTitle, (present) => {
                    console.log(`检测完成: ${cleanedTitle}，入库状态：${present ? '已入库' : '未入库'}`);
                    if (present) {
                        element.textContent = "已入库";
                        element.parentNode.style.background = "#52c41a";
                    } else {
                        element.textContent = "未入库";
                        element.parentNode.style.background = "#f5222d";
                    }
                    element.parentNode.style.color = "#fff";
                }, (err) => {
                    console.error("检测失败", err);
                    element.textContent = "⚠ 检测失败";
                    element.parentNode.style.background = "#faad14";
                    element.parentNode.style.color = "#000";
                });
            } catch (e) {
                console.error("发生错误", e);
                element.textContent = "⚠ 错误";
                element.parentNode.style.background = "#faad14";
                element.parentNode.style.color = "#000";
            }
        }

        // 公用按钮样式
        function createStatusButton(text) {
            const statusBtn = document.createElement('button');
            statusBtn.className = 'autofill-btn';
            statusBtn.style.display = 'flex';
            statusBtn.style.alignItems = 'center';
            statusBtn.style.gap = '4px';
            statusBtn.style.marginLeft = '6px';
            statusBtn.style.padding = '6px 12px';
            statusBtn.style.backgroundColor = 'rgba(82, 196, 26, 0.5)'; // 透明背景
            statusBtn.style.color = '#fff'; // 字体颜色
            statusBtn.style.border = 'none'; // 边框
            statusBtn.style.borderRadius = '4px'; // 圆角

            const img = document.createElement('img');
            img.src = iconUrl;
            img.style.width = '16px';
            img.style.height = '16px';
            statusBtn.appendChild(img);

            const statusText = document.createElement('span');
            statusText.textContent = text;
            statusBtn.appendChild(statusText);

            return statusBtn;
        }

        // 处理每个电影项
        function handleMovieItems() {
            document.querySelectorAll('div.li-bottom').forEach(block => {
                const titleElement = block.querySelector('h3 a');
                const scoreElement = block.querySelector('span');
                const tagElement = block.querySelector('.tag');

                if (!titleElement || !scoreElement || !tagElement || block.dataset.processed) return; // 确保有必要的元素并且没有重复处理过

                const title = titleElement.textContent.trim();
                const score = scoreElement.textContent.trim();
                const tags = tagElement.textContent.trim();

                // 按钮容器换行显示，并居中显示按钮
                const btnWrap = document.createElement('div');
                btnWrap.style.marginTop = '4px';
                btnWrap.style.display = 'flex'; // 设置为flex布局
                btnWrap.style.justifyContent = 'center'; // 水平居中
                btnWrap.style.alignItems = 'center'; // 垂直居中
                block.appendChild(btnWrap); // 将按钮添加到标签容器下面

                const statusBtn = createStatusButton("检测中...");
                btnWrap.appendChild(statusBtn);

                // 开始入库状态检测
                autoCheckStatus(statusBtn.querySelector('span'), title);

                block.dataset.processed = 'true';  // 标记为已处理，防止重复执行
            });
        }

        // 新增的部分：处理番号和标签
        function handleTags() {
            document.querySelectorAll('.video-title').forEach(block => {
                const titleElement = block.querySelector('strong');
                const tagsElement = block.closest('.video-title').nextElementSibling; // 找到相邻的 .tags

                if (!titleElement || !tagsElement || block.dataset.processed) return; // 确保有必要的元素并且没有重复处理过

                const title = titleElement.textContent.trim();

                // 按钮容器换行显示，并居中显示按钮
                const btnWrap = document.createElement('div');
                btnWrap.style.marginTop = '4px';
                btnWrap.style.display = 'flex'; // 设置为flex布局
                btnWrap.style.justifyContent = 'center'; // 水平居中
                btnWrap.style.alignItems = 'center'; // 垂直居中
                tagsElement.appendChild(btnWrap); // 将按钮添加到标签容器下面

                const statusBtn = createStatusButton("检测中...");
                btnWrap.appendChild(statusBtn);

                // 开始入库状态检测
                autoCheckStatus(statusBtn.querySelector('span'), title);

                block.dataset.processed = 'true';  // 标记为已处理，防止重复执行
            });
        }

        // 初始化检测
        handleMovieItems();
        handleTags();

        // 设置MutationObserver监听wrap部分的DOM变动
        const wrapElement = document.querySelector('.wrap');
        if (wrapElement) {
            const observer = new MutationObserver(() => {
                console.log("检测到 DOM 变化，重新处理");
                // 重新运行处理函数，确保按钮加载
                handleMovieItems();
                handleTags();
            });

            observer.observe(wrapElement, { childList: true, subtree: true });
        }
    }

    // 调用函数开始检测
    detectMovieInfo();


    /* ===================== Emby 统一配置面板（TAB版本） ===================== */
    let configPanelEl = null;

    function showConfigPanel() {
        if (!configPanelEl) createConfigPanel();
        configPanelEl.style.display = "block";
    }

    function createConfigPanel() {
        if (document.getElementById("embyConfigPanel")) return;

        configPanelEl = document.createElement("div");
        configPanelEl.id = "embyConfigPanel";
        configPanelEl.className = "emby-setting";

        // 使用 CSS 居中
        Object.assign(configPanelEl.style, {
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)", // 垂直水平居中
            width: "580px",
            maxHeight: "80vh",
            overflowY: "auto",
            padding: "12px",
            backgroundColor: "#fff",
            boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
            borderRadius: "8px",
            zIndex: 99999,
            display: "none" // 默认隐藏
        });

        configPanelEl.innerHTML = `
    <div class="emby-header" id="configPanelDrag">
        Emby 配置中心
        <span id="closeConfigPanel" style="margin-left:auto;cursor:pointer">✖</span>
    </div>

    <!-- TAB 头 -->
    <div style="height:10px;"></div>
    <div style="display:flex;gap:6px;margin-bottom:10px;">
        <button class="emby-btn" id="tabServer">服务端管理</button>
        <button class="emby-btn ghost" id="tabSite">网站管理</button>
    </div>

    <!-- 服务端 TAB -->
    <div id="tab_server_panel">
        <div class="emby-row">
            <input id="srv_name" placeholder="服务端名称">
            <input id="srv_url" placeholder="服务端地址 (http://ip:port)">
        </div>

        <div class="emby-row">
            <input id="srv_key" placeholder="API Key (可选)">
            <label style="display:flex;align-items:center;gap:6px;">
                <input type="checkbox" id="srv_useHeader"> 使用Header
            </label>
        </div>

        <div class="emby-row">
            <input id="srv_paths" placeholder="扫描路径, 多个用逗号分隔">
        </div>

        <div style="display:flex;gap:8px;">
            <button id="srv_add" class="emby-btn">保存/新增</button>
            <button id="srv_refresh" class="emby-btn ghost">刷新列表</button>
        </div>

        <div id="srv_list" style="margin-top:12px;max-height:300px;overflow:auto"></div>
    </div>

    <!-- 网站 TAB -->
    <div id="tab_site_panel" style="display:none;">
        <div class="emby-row">
            <input id="site_name" placeholder="网站名称">
            <input id="site_url" placeholder="网站URL (例: https://example.com)">
        </div>

        <div class="emby-row">
            <select id="site_server_select">
                <option value="">请选择服务端</option>
            </select>
        </div>

        <div style="display:flex;gap:8px;">
            <button id="site_add" class="emby-btn">保存/新增网站</button>
            <button id="site_refresh" class="emby-btn ghost">刷新列表</button>
        </div>

        <div id="site_list" style="margin-top:12px;max-height:320px;overflow:auto"></div>
    </div>
    `;

        document.body.appendChild(configPanelEl);
        dragElement(configPanelEl, document.getElementById("configPanelDrag"));
        document.getElementById("closeConfigPanel").onclick = () => configPanelEl.style.display = "none";

        /* ===== TAB 切换逻辑 ===== */
        const tabServer = document.getElementById("tabServer");
        const tabSite = document.getElementById("tabSite");
        const serverPanel = document.getElementById("tab_server_panel");
        const sitePanel = document.getElementById("tab_site_panel");

        tabServer.onclick = () => {
            tabServer.classList.remove("ghost");
            tabSite.classList.add("ghost");
            serverPanel.style.display = "block";
            sitePanel.style.display = "none";
            renderServerList();
        };

        tabSite.onclick = () => {
            tabSite.classList.remove("ghost");
            tabServer.classList.add("ghost");
            serverPanel.style.display = "none";
            sitePanel.style.display = "block";
            renderServerOptions();
            renderSiteList();
        };

        /* ===================== 原【服务端管理】逻辑完整保留 ===================== */
        function renderServerList() {
            const wrap = document.getElementById("srv_list");
            wrap.innerHTML = "";
            const servers = getServers();

            servers.forEach((s, i) => {
                const row = document.createElement("div");
                row.className = "site-row";
                row.innerHTML = `
                <div style="flex:1">
                    <strong>${s.name}</strong>
                    <div style="font-size:12px;color:#666">${s.server}</div>
                </div>
                <div class="site-controls">
                    <button class="emby-btn ghost" data-i="${i}" data-act="edit">编辑</button>
                    <button class="emby-btn ghost" data-i="${i}" data-act="del">删除</button>
                    <button class="emby-btn ghost" data-i="${i}" data-act="test">连通</button>
                </div>
            `;
                wrap.appendChild(row);
            });

            wrap.querySelectorAll("button").forEach(btn => {
                const idx = btn.dataset.i;
                const act = btn.dataset.act;

                btn.onclick = () => {
                    const servers = getServers();

                    if (act === "del") {
                        servers.splice(idx, 1);
                        setServers(servers);
                        renderServerList();
                    }

                    if (act === "edit") {
                        const s = servers[idx];
                        document.getElementById("srv_name").value = s.name || "";
                        document.getElementById("srv_url").value = s.server || "";
                        document.getElementById("srv_key").value = s.key || "";
                        document.getElementById("srv_useHeader").checked = !!s.useHeader;
                        document.getElementById("srv_paths").value = (s.scanPaths || []).join(",");
                        servers.splice(idx, 1);
                        setServers(servers);
                        renderServerList();
                    }

                    if (act === "test") {
                        const s = servers[idx];
                        btn.textContent = "测试中...";
                        checkServerReachable(s, ok => {
                            btn.textContent = ok ? "在线" : "离线";
                            setTimeout(renderServerList, 800);
                        });
                    }
                };
            });
        }

        document.getElementById("srv_add").onclick = () => {
            const name = document.getElementById("srv_name").value.trim();
            const server = document.getElementById("srv_url").value.trim();
            if (!name || !server) return alert("请填写名称与服务端地址");

            const key = document.getElementById("srv_key").value.trim();
            const useHeader = document.getElementById("srv_useHeader").checked;
            const paths = document.getElementById("srv_paths").value.trim();

            const servers = getServers();
            servers.push({
                name,
                server,
                key,
                useHeader,
                scanPaths: paths ? paths.split(",").map(p => p.trim()).filter(Boolean) : []
            });

            setServers(servers);

            document.getElementById("srv_name").value = "";
            document.getElementById("srv_url").value = "";
            document.getElementById("srv_key").value = "";
            document.getElementById("srv_useHeader").checked = false;
            document.getElementById("srv_paths").value = "";

            renderServerList();
            renderServerOptions();
        };

        document.getElementById("srv_refresh").onclick = renderServerList;

        /* ===================== 原【网站管理】逻辑完整保留 ===================== */
        function renderServerOptions() {
            const sel = document.getElementById("site_server_select");
            sel.innerHTML = `<option value="">请选择服务端</option>`;
            getServers().forEach((s, i) => {
                sel.innerHTML += `<option value="${i}">${s.name}</option>`;
            });
        }

        function renderSiteList() {
            const wrap = document.getElementById("site_list");
            wrap.innerHTML = "";
            const sites = getSites();

            sites.forEach((s, i) => {
                const server = getServers()[s.serverIndex];
                const row = document.createElement("div");
                row.className = "site-row";

                row.innerHTML = `
                <div style="flex:1">
                    <strong>${s.name}</strong>
                    <div style="font-size:12px;color:#666">${s.url}</div>
                    <div style="font-size:12px;color:#999">
                        绑定：${server ? server.name : "未绑定"}
                    </div>
                </div>
                <div class="site-controls">
                    <button class="emby-btn ghost" data-i="${i}" data-act="edit">编辑</button>
                    <button class="emby-btn ghost" data-i="${i}" data-act="del">删除</button>
                    <button class="autofill-btn" data-i="${i}" data-act="check">检测入库</button>
                </div>
            `;
                wrap.appendChild(row);
            });

            wrap.querySelectorAll("button").forEach(btn => {
                const idx = btn.dataset.i;
                const act = btn.dataset.act;

                btn.onclick = () => {
                    const sites = getSites();

                    if (act === "del") {
                        sites.splice(idx, 1);
                        setSites(sites);
                        renderSiteList();
                    }

                    if (act === "edit") {
                        const s = sites[idx];
                        document.getElementById("site_name").value = s.name || "";
                        document.getElementById("site_url").value = s.url || "";
                        renderServerOptions();
                        document.getElementById("site_server_select").value = s.serverIndex;
                        sites.splice(idx, 1);
                        setSites(sites);
                        renderSiteList();
                    }

                    if (act === "check") {
                        const s = sites[idx];
                        const server = getServers()[s.serverIndex];
                        if (!server) return alert("未绑定服务端");

                        const title = prompt("输入检测标题", "");
                        if (!title) return;

                        btn.textContent = "检测中...";
                        checkTitleOnServer(server, title, present => {
                            alert(present ? `已入库（${server.name}）` : `未入库（${server.name}）`);
                            btn.textContent = "检测入库";
                        });
                    }
                };
            });
        }

        document.getElementById("site_add").onclick = () => {
            const name = document.getElementById("site_name").value.trim();
            const url = document.getElementById("site_url").value.trim();
            const serverIndexRaw = document.getElementById("site_server_select").value;

            if (!name || !url || serverIndexRaw === "") {
                return alert("请填写完整网站信息并选择服务端");
            }

            const sites = getSites();
            sites.push({
                name,
                url,
                serverIndex: parseInt(serverIndexRaw)
            });

            setSites(sites);

            document.getElementById("site_name").value = "";
            document.getElementById("site_url").value = "";

            renderSiteList();
        };

        document.getElementById("site_refresh").onclick = () => {
            renderServerOptions();
            renderSiteList();
        };

        renderServerList();
    }

    /* ===================== 页面加载后自动挂载检测（番号/标题/页面入库按钮） ===================== */
    function initPageObservers() {
        // first run
        setTimeout(detectAll, 400);
        const obs = new MutationObserver(detectAll);
        obs.observe(document.body, { childList: true, subtree: true });
    }

    /* ===================== 检查服务端是否可达（简单GET /System/Info） ===================== */
    function checkServerReachable(srv, cb) {
        if (!srv) return cb(false);
        const url = srv.server.replace(/\/$/, "") + "/emby/System/Info";
        GM_xmlhttpRequest({
            method: "GET",
            url: srv.useHeader ? url : (url + "&api_key=" + encodeURIComponent(srv.key || "")),
            headers: srv.useHeader ? { "X-Emby-Token": srv.key } : {},
            onload: r => {
                try {
                    const json = JSON.parse(r.responseText);
                    if (json && json.Id) return cb(true);
                    cb(false);
                } catch (e) { cb(false); }
            },
            onerror: () => cb(false),
            timeout: 10000
        });
    }

    /* ===================== 初始化：创建面板并注册菜单 ===================== */
    function initAll() {
        createSearchPanel();

        initPageObservers();

        GM_registerMenuCommand("Emby 配置中心", () => {
            showConfigPanel();
        });

        GM_registerMenuCommand("Emby 搜索面板", () => {
            const p = document.getElementById("embyPanel");
            const mini = document.getElementById("embyMiniBtn");
            if (p && mini) {
                p.style.display = "block";
                mini.style.display = "none";
            }
        });
    }


    /* ===================== 兼容：若用户之前使用过旧键，尝试迁移（弱） ===================== */
    (function tryMigrateOldKeys() {
        try {
            const maybeOldServers = GM_getValue("EMBY_SERVER_LIST");
            const maybeOldSites = GM_getValue("EMBY_SITE_LIST");
            if (maybeOldServers && !GM_getValue(SERVER_KEY)) setServers(maybeOldServers);
            if (maybeOldSites && !GM_getValue(SITE_KEY)) setSites(maybeOldSites);
        } catch (e) { /* ignore */ }
    })();

    /* ===================== 启动 ===================== */
    initAll();

})();

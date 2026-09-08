let currentContext = { title: "", url: "", selection: "" };

function logEvent(msg, type = 'sys') {
  const stream = document.getElementById('event-stream');
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'});
  entry.textContent = `[${time}] ${msg}`;
  stream.appendChild(entry);
  stream.scrollTop = stream.scrollHeight;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('status-badge').textContent = 'Linked';
  document.getElementById('status-badge').classList.add('active');
  logEvent('Extension initialized. Monitoring tab.', 'sys');
  
  updateContext();

  document.getElementById('send-context-btn').addEventListener('click', (e) => {
    const btn = e.target;
    const originalText = btn.textContent;
    btn.innerHTML = 'Transmitting...';
    logEvent(`Transmitting context: ${currentContext.url.substring(0, 30)}...`, 'info');
    
    fetch('http://127.0.0.1:8000/api/v1/context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentContext)
    })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      btn.innerHTML = 'Transmission Complete';
      btn.style.backgroundColor = '#10b981';
      logEvent('Payload delivered to VoiceOps.', 'success');
      
      setTimeout(() => {
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 5px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Transmit to VoiceOps';
        btn.style.backgroundColor = '';
      }, 2500);
    })
    .catch(err => {
      console.log('Backend not reachable', err);
      btn.innerHTML = 'Transmission Failed';
      btn.style.backgroundColor = '#ef4444';
      logEvent('Delivery failed. Backend unreachable.', 'error');
      
      setTimeout(() => {
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 5px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Transmit to VoiceOps';
        btn.style.backgroundColor = '';
      }, 3000);
    });
  });

  const refreshBtn = document.getElementById('refresh-context-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      logEvent('Scanning for active browser tab...', 'info');
      updateContext();
    });
  }

  document.getElementById('open-ml-btn').addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://127.0.0.1:8000/' });
  });
});

async function getActiveTab() {
  try {
    // 1. First priority: active tab in last focused window (the browser window user is looking at)
    let [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tab && tab.url && !tab.url.startsWith('chrome-extension://')) {
      return tab;
    }

    // 2. Second priority: active tab in current window
    const currentWindowTabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (currentWindowTabs.length > 0 && currentWindowTabs[0].url && !currentWindowTabs[0].url.startsWith('chrome-extension://')) {
      return currentWindowTabs[0];
    }

    // 3. Third priority: any active tab with a valid web URL
    const allActive = await chrome.tabs.query({ active: true });
    const webTab = allActive.find(t => t.url && (t.url.startsWith('http://') || t.url.startsWith('https://')));
    if (webTab) return webTab;

    return tab || currentWindowTabs[0] || null;
  } catch (e) {
    console.warn("Error querying tabs:", e);
    return null;
  }
}

async function updateContext() {
  try {
    const tab = await getActiveTab();
    if (!tab) {
      renderContext();
      return;
    }

    const url = tab.url || "";
    const title = tab.title || "Untitled Tab";

    // Only update if we have a real URL or if context is empty
    if (url && !url.startsWith('chrome-extension://')) {
      currentContext.title = title;
      currentContext.url = url;
    }

    const isRestricted = !url || 
                         url.startsWith('chrome://') || 
                         url.startsWith('edge://') || 
                         url.startsWith('about:') || 
                         url.startsWith('chrome-extension://');

    if (!isRestricted && tab.id) {
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: () => {
          try {
            return window.getSelection() ? window.getSelection().toString() : "";
          } catch (e) {
            return "";
          }
        }
      }, (results) => {
        if (chrome.runtime.lastError) {
          // Ignored for non-scriptable tabs
        } else if (results && results[0] && results[0].result) {
          currentContext.selection = results[0].result;
        }
        renderContext();
      });
    } else {
      renderContext();
    }
  } catch (err) {
    console.warn("Context update error:", err);
    renderContext();
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderContext() {
  const el = document.getElementById('context-info');
  if (!el) return;

  if (!currentContext.url || currentContext.url.startsWith('chrome-extension://')) {
    el.innerHTML = '<span style="color:#9ca3af;">No active web page detected.<br><span style="font-size:0.85em; color:#6b7280;">Click on a website tab to detect.</span></span>';
    return;
  }

  let html = `<div style="color:#ff6a00; font-weight:600; margin-bottom:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(currentContext.title)}">${escapeHtml(currentContext.title || "Page")}</div>`;
  html += `<div style="color:#60a5fa; font-size:0.8em; margin-bottom:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(currentContext.url)}">${escapeHtml(currentContext.url)}</div>`;
  
  if (currentContext.selection) {
    html += `<div style="color:#10b981; font-size:0.75em; border-top:1px solid #222; padding-top:4px;">Selection: "${escapeHtml(currentContext.selection.substring(0, 70))}..."</div>`;
  }
  el.innerHTML = html;
}

// Automatically detect when user switches tabs or navigates
chrome.tabs.onActivated.addListener(() => {
  updateContext();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'complete' || changeInfo.url) {
    updateContext();
  }
});

// Receive real-time page context from content script
chrome.runtime.onMessage.addListener((request) => {
  if (request?.type === 'PAGE_CONTEXT') {
    if (request.url && !request.url.startsWith('chrome://') && !request.url.startsWith('chrome-extension://')) {
      currentContext.url = request.url;
      currentContext.title = request.title || "Web Page";
      if (request.selection) currentContext.selection = request.selection;
      renderContext();
    }
  } else if (request?.type === 'SELECTION_CHANGED') {
    currentContext.selection = request.selection || "";
    renderContext();
  }
});

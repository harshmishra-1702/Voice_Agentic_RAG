let currentContext = { title: "", url: "", selection: "" };

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('status').textContent = 'Ready';
  
  // Get active tab context
  updateContext();

  document.getElementById('send-context-btn').addEventListener('click', () => {
    // Send to local VoiceOps backend (which bridges to data channel or state)
    // We can use the REST API for this if we build a context webhook endpoint, 
    // or just let the main WebUI handle it. 
    // Wait, the instructions say "Send selected text to backend."
    fetch('http://127.0.0.1:8000/api/v1/context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentContext)
    }).catch(e => console.log('Backend not reachable', e));
  });

  document.getElementById('open-ml-btn').addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://127.0.0.1:8000/' });
  });
});

async function updateContext() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    currentContext.title = tab.title;
    currentContext.url = tab.url;
    
    // Attempt to get selection
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: () => window.getSelection().toString()
    }, (results) => {
      if (results && results[0]) {
        currentContext.selection = results[0].result;
      }
      renderContext();
    });
  }
}

function renderContext() {
  const el = document.getElementById('context-info');
  if (currentContext.selection) {
    el.textContent = `Selection: "${currentContext.selection.substring(0, 50)}..."`;
  } else {
    el.textContent = `Page: ${currentContext.title}`;
  }
}

chrome.runtime.onMessage.addListener((request) => {
  if (request.type === 'SELECTION_CHANGED') {
    currentContext.selection = request.selection;
    renderContext();
  }
});

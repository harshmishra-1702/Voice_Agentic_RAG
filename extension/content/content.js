function sendPageContext() {
  try {
    if (typeof chrome !== 'undefined' && chrome?.runtime?.sendMessage) {
      chrome.runtime.sendMessage({
        type: 'PAGE_CONTEXT',
        url: window.location.href,
        title: document.title,
        selection: window.getSelection() ? window.getSelection().toString() : ""
      }).catch(() => {
        // Ignore if sidepanel is not open
      });
    }
  } catch (e) {
    // Context invalidated when extension is reloaded
  }
}

// Initial announcement
sendPageContext();

// Update when user returns to / focuses the tab
window.addEventListener('focus', sendPageContext);

// Update on selection
document.addEventListener('selectionchange', () => {
  try {
    const selection = window.getSelection() ? window.getSelection().toString() : "";
    if (typeof chrome !== 'undefined' && chrome?.runtime?.sendMessage) {
      chrome.runtime.sendMessage({
        type: 'SELECTION_CHANGED',
        selection: selection
      }).catch(() => {});
    }
  } catch (e) {}
});

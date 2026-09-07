document.addEventListener('selectionchange', () => {
  const selection = window.getSelection().toString();
  if (selection.length > 0) {
    chrome.runtime.sendMessage({
      type: 'SELECTION_CHANGED',
      selection: selection
    }).catch(e => {
      // Ignore errors when popup/sidepanel is closed
    });
  }
});

  function followLink(element) {
    element.click(window.location = element.getAttribute('data-href'));
  }
// Small element builders. Text goes in as text nodes, never as HTML, so tool data can't inject markup.

function build(el, attrs, children) {
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key === "className" ? "class" : key, value === true ? "" : value);
  }
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

export const h = (tag, attrs, ...children) => build(document.createElement(tag), attrs, children);

export const s = (tag, attrs, ...children) =>
  build(document.createElementNS("http://www.w3.org/2000/svg", tag), attrs, children);

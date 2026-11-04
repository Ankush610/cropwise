// The small part of Markdown the advisor writes: paragraphs, **bold**, *italic*, numbered and bulleted lists
// with one level of sub-bullets, and headings shown as bold lines. Text is escaped first.

const escape = (text) =>
  text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const inline = (text) =>
  escape(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, "$1<em>$2</em>");

const ITEM = /^(\s*)(?:[-*•]|(\d+)[.)])\s+(.*)$/;

export function markdown(text) {
  const blocks = [];
  let para = null;
  let list = null;

  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const item = raw.match(ITEM);
    if (!raw.trim()) {
      para = null; // a blank line ends a paragraph; lists survive it (the advisor spaces out numbered items)
    } else if (item && item[1].length >= 2 && list?.items.length) {
      list.items.at(-1).sub.push(inline(item[3]));
    } else if (item) {
      const type = item[2] ? "ol" : "ul";
      if (list?.type !== type) {
        list = { type, start: Number(item[2] ?? 1), items: [] };
        blocks.push(list);
      }
      list.items.push({ html: inline(item[3]), sub: [] });
      para = null;
    } else if (list && /^\s{2,}/.test(raw)) {
      list.items.at(-1).html += `<br>${inline(raw.trim())}`;
    } else {
      list = null;
      const heading = raw.match(/^#{1,6}\s+(.*)$/);
      if (heading) {
        blocks.push({ type: "p", lines: [`<strong>${inline(heading[1])}</strong>`] });
        para = null;
      } else if (para) {
        para.lines.push(inline(raw.trim()));
      } else {
        para = { type: "p", lines: [inline(raw.trim())] };
        blocks.push(para);
      }
    }
  }

  return blocks
    .map((b) => {
      if (b.type === "p") return `<p>${b.lines.join("<br>")}</p>`;
      const items = b.items
        .map((i) => `<li>${i.html}${i.sub.length ? `<ul>${i.sub.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}</li>`)
        .join("");
      return b.type === "ol" && b.start !== 1 ? `<ol start="${b.start}">${items}</ol>` : `<${b.type}>${items}</${b.type}>`;
    })
    .join("");
}

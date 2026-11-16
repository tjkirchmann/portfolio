// Sätteri hast plugin. A paragraph holding only an image that has a title becomes
// <figure><img><figcaption>alt</figcaption></figure>. Untitled images stay as they are.
export const figurePlugin = {
  name: 'figure-caption',
  element: {
    filter: ['p'],
    visit(node, ctx) {
      const kids = node.children.filter((c) => !(c.type === 'text' && !c.value.trim()));
      if (kids.length !== 1) return;
      const img = kids[0];
      if (img.type !== 'element' || img.tagName !== 'img' || !img.properties?.title) return;
      const alt = String(img.properties.alt ?? '');
      ctx.setField(node, 'tagName', 'figure');
      if (alt) {
        ctx.appendChild(node, {
          type: 'element',
          tagName: 'figcaption',
          properties: {},
          children: [{ type: 'text', value: alt }],
        });
      }
    },
  },
};

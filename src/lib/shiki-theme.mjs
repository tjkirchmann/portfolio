// Code highlighting in greens only (emerald, teal, deep and lighter tints), neutrals for the rest.
export const chaferTheme = {
  name: 'chafer',
  type: 'dark',
  colors: { 'editor.background': '#0f1312', 'editor.foreground': '#d5dad5' },
  tokenColors: [
    { scope: ['comment', 'punctuation.definition.comment'], settings: { foreground: '#868f89', fontStyle: 'italic' } },
    { scope: ['keyword', 'storage', 'storage.type', 'keyword.control'], settings: { foreground: '#76c8a5' } },
    { scope: ['string', 'string.template', 'markup.inline.raw'], settings: { foreground: '#a9dcc6' } },
    { scope: ['constant.numeric', 'constant.language', 'constant.character'], settings: { foreground: '#6fb59c' } },
    { scope: ['entity.name.function', 'support.function', 'meta.function-call'], settings: { foreground: '#c7e8da' } },
    { scope: ['entity.name.type', 'entity.name.class', 'support.type', 'support.class'], settings: { foreground: '#8fcfb5' } },
    { scope: ['variable.parameter', 'variable.other.property', 'meta.object-literal.key'], settings: { foreground: '#bfc7c1' } },
    { scope: ['entity.name.tag', 'punctuation.definition.tag'], settings: { foreground: '#579d87' } },
    { scope: ['entity.other.attribute-name'], settings: { foreground: '#8fcfb5' } },
    { scope: ['punctuation', 'keyword.operator', 'meta.brace'], settings: { foreground: '#8a938d' } },
  ],
};

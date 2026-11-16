// Code highlighting in the chafer palette. Kept muted; colour mostly in keywords and strings.
export const chaferTheme = {
  name: 'chafer',
  type: 'dark',
  colors: { 'editor.background': '#0f1312', 'editor.foreground': '#d5dad5' },
  tokenColors: [
    { scope: ['comment', 'punctuation.definition.comment'], settings: { foreground: '#868f89', fontStyle: 'italic' } },
    { scope: ['keyword', 'storage', 'storage.type', 'keyword.control'], settings: { foreground: '#76c8a5' } },
    { scope: ['string', 'string.template', 'markup.inline.raw'], settings: { foreground: '#bbc368' } },
    { scope: ['constant.numeric', 'constant.language', 'constant.character'], settings: { foreground: '#c9a46a' } },
    { scope: ['entity.name.function', 'support.function', 'meta.function-call'], settings: { foreground: '#9fd9bf' } },
    { scope: ['entity.name.type', 'entity.name.class', 'support.type', 'support.class'], settings: { foreground: '#73984f' } },
    { scope: ['variable.parameter', 'variable.other.property', 'meta.object-literal.key'], settings: { foreground: '#bfc7c1' } },
    { scope: ['entity.name.tag', 'punctuation.definition.tag'], settings: { foreground: '#579d87' } },
    { scope: ['entity.other.attribute-name'], settings: { foreground: '#bbc368' } },
    { scope: ['punctuation', 'keyword.operator', 'meta.brace'], settings: { foreground: '#8a938d' } },
  ],
};

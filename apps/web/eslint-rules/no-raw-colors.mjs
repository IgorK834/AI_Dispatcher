// Forbids raw colour values and font-family outside src/styles/tokens.css (AC-FEAT-005-27).
// Colours and fonts come from design tokens only: use var(--token) or a Tailwind token class.
const COLOUR_PATTERNS = [
  /#[0-9a-fA-F]{3,8}\b/, // hex
  /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\(/i, // colour functions
];
const FONT_PATTERNS = [/font-family\s*:/i, /\bfontFamily\b/];
// CSS colour keywords are only checked where a colour is certainly meant: the value of a
// colour-like JSX attribute or style property ("fill=\"white\"", "{ color: 'red' }").
const NAMED = new Set(
  'black white red green blue yellow orange purple pink brown gray grey silver gold navy teal cyan magenta lime maroon olive aqua fuchsia'.split(
    ' ',
  ),
);
const COLOUR_PROPERTIES = new Set([
  'color',
  'fill',
  'stroke',
  'stopColor',
  'stop-color',
  'floodColor',
  'background',
  'backgroundColor',
  'borderColor',
  'outlineColor',
]);

export const noRawColors = {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      colour: 'Raw colour value "{{value}}": use a design token (var(--token) or a token class).',
      font: 'font-family belongs in styles/tokens.css and next/font; use a token class.',
    },
  },
  create(context) {
    const filename = context.filename.replaceAll('\\', '/');
    if (filename.endsWith('/styles/tokens.css')) return {};
    function check(node, text) {
      for (const pattern of COLOUR_PATTERNS) {
        const match = text.match(pattern);
        if (match) {
          context.report({ node, messageId: 'colour', data: { value: match[0] } });
          return;
        }
      }
      if (FONT_PATTERNS.some((pattern) => pattern.test(text))) {
        context.report({ node, messageId: 'font' });
      }
    }
    return {
      Literal(node) {
        if (typeof node.value === 'string') check(node, node.value);
      },
      TemplateElement(node) {
        check(node, node.value.cooked ?? '');
      },
      Identifier(node) {
        if (node.name === 'fontFamily') context.report({ node, messageId: 'font' });
      },
      JSXAttribute(node) {
        const name = node.name?.name;
        const value = node.value;
        if (
          typeof name === 'string' &&
          COLOUR_PROPERTIES.has(name) &&
          value?.type === 'Literal' &&
          typeof value.value === 'string' &&
          NAMED.has(value.value.trim().toLowerCase())
        ) {
          context.report({ node, messageId: 'colour', data: { value: value.value } });
        }
      },
      Property(node) {
        const key = node.key?.name ?? node.key?.value;
        if (
          COLOUR_PROPERTIES.has(key) &&
          node.value?.type === 'Literal' &&
          typeof node.value.value === 'string' &&
          NAMED.has(node.value.value.trim().toLowerCase())
        ) {
          context.report({
            node,
            messageId: 'colour',
            data: { value: node.value.value },
          });
        }
      },
    };
  },
};

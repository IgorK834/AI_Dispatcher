// Fails on hard-coded user-visible strings in components: all copy comes from messages/*.json
// through next-intl (FR-27, AC-FEAT-005-18). Strings without letters (punctuation, numbers) pass.
const ATTRIBUTES = new Set(['aria-label', 'title', 'placeholder', 'alt', 'aria-description']);
const HAS_LETTER = /\p{L}/u;

export const noHardcodedText = {
  meta: {
    type: 'problem',
    schema: [],
    messages: { text: 'Hard-coded text "{{text}}": use a translation key from messages/*.json.' },
  },
  create(context) {
    function report(node, text) {
      context.report({ node, messageId: 'text', data: { text: text.trim().slice(0, 40) } });
    }
    return {
      JSXText(node) {
        if (HAS_LETTER.test(node.value)) report(node, node.value);
      },
      JSXAttribute(node) {
        const name = node.name?.name;
        if (typeof name !== 'string' || !ATTRIBUTES.has(name)) return;
        const value = node.value;
        if (
          value?.type === 'Literal' &&
          typeof value.value === 'string' &&
          HAS_LETTER.test(value.value)
        ) {
          report(node, value.value);
        }
      },
    };
  },
};

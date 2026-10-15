// Minimal .graphql loader (GitLab uses a similar plugin): supports `#import "./x.graphql"`.

export default function graphqlPlugin() {
  return {
    name: 'gitlab-demo-graphql',
    enforce: 'pre',
    transform(src, id) {
      if (!/\.(graphql|gql)$/.test(id)) return null;
      const imports = [];
      const body = src.replace(/^#import\s+["'](.+)["']\s*$/gm, (_, p) => {
        imports.push(p);
        return '';
      });
      const importLines = imports
        .map((p, i) => `import __frag${i} from ${JSON.stringify(p)};`)
        .join('\n');
      const merges = imports.map((_, i) => `__frag${i}`).join(', ');
      // Like graphql-tag/loader: also export every named operation on its own (import { getX } from './x.graphql').
      const opNames = [...body.matchAll(/^\s*(?:query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)/gm)].map((m) => m[1]);
      const named = opNames
        .map(
          (n) =>
            `export const ${n} = { ...doc, definitions: doc.definitions.filter((d) => d.kind === 'FragmentDefinition' || (d.name && d.name.value === ${JSON.stringify(n)})) };`,
        )
        .join('\n');
      return {
        code: `import gql from 'graphql-tag';
${importLines}
const doc = gql(${JSON.stringify(body)});
const seen = new Set(doc.definitions.map((d) => d.name && d.name.value));
for (const frag of [${merges}]) {
  for (const d of frag.definitions) {
    if (!seen.has(d.name && d.name.value)) { seen.add(d.name && d.name.value); doc.definitions.push(d); }
  }
}
export default doc;
${named}
`,
        map: null,
      };
    },
  };
}

import {expect, test} from 'vitest';
import postcss from 'postcss';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const referenceCss = readFileSync(resolve(process.cwd(), 'src/sdl-teaching-ui.css'), 'utf8');

test('reference theme cannot style other tools or replace their animations', () => {
  const css = postcss.parse(referenceCss);
  let scopedRules = 0;
  css.walkRules(rule => {
    if (rule.parent.type === 'atrule' && /keyframes$/.test(rule.parent.name)) return;
    for (const selector of rule.selectors) expect(selector).toContain('.sdl-teaching-ui');
    scopedRules++;
  });
  expect(scopedRules).toBeGreaterThan(100);
  css.walkAtRules(/keyframes$/, rule => expect(rule.params).toMatch(/^sdl-teaching-/));
});

test('reference keeps the sidebar/chat layout and responsive rules', () => {
  const css = postcss.parse(referenceCss);
  const layouts = [];
  css.walkRules(rule => {
    if (rule.selector.includes('.workspace-grid')) rule.walkDecls('grid-template-columns', decl => layouts.push(decl.value));
  });
  expect(layouts).toContain('270px minmax(0, 1fr)');
  expect(layouts).toContain('1fr');
});

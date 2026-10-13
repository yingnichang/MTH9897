// Render the generated deck to PNG previews using @oai/artifact-tool.
// ARTIFACT_TOOL_MODULE can point to artifact_tool.mjs in a bundled runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const modulePath = process.env.ARTIFACT_TOOL_MODULE;
const {PresentationFile, FileBlob} = modulePath
  ? await import(pathToFileURL(modulePath).href)
  : await import('@oai/artifact-tool');
const input = process.argv[2] || path.join(here, 'conservative_formula.pptx');
const deck = await PresentationFile.importPptx(await FileBlob.load(input));
const previews = path.join(here, 'build', 'previews');
await fs.mkdir(previews, {recursive: true});
for (let i = 0; i < deck.slides.items.length; i++) {
  const png = await deck.export({slide: deck.slides.items[i], format: 'png', scale: 1});
  await fs.writeFile(path.join(previews, `slide-${String(i + 1).padStart(2, '0')}.png`),
    new Uint8Array(await png.arrayBuffer()));
}
console.log(`Rendered ${deck.slides.items.length} slides to ${previews}`);
// PDF assembly is done by build_pdf.py to avoid platform-specific font packages.

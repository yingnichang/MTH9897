/** Render the existing deck at 2x resolution, then package 16:9 PDF pages.
 * Requires the bundled Artifact Tool runtime plus Python with reportlab and pypdf.
 * Set ARTIFACT_TOOL_MODULE and RUNTIME_PYTHON if not available on default paths.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const here=path.dirname(fileURLToPath(import.meta.url));
const modulePath=process.env.ARTIFACT_TOOL_MODULE;
const {FileBlob,PresentationFile}=await import(modulePath ? pathToFileURL(path.resolve(modulePath)).href : '@oai/artifact-tool');
const input=path.resolve(process.argv[2] ?? path.join(here,'conservative_formula_presentation.pptx'));
const output=path.resolve(process.argv[3] ?? path.join(here,'conservative_formula_presentation.pdf'));
const build=path.join(here,'build','pdf-pages');
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(input));
const pages=[];
for(let i=0;i<deck.slides.items.length;i++){
  const image=await deck.export({slide:deck.slides.items[i],format:'png',scale:2});
  const imagePath=path.join(build,`page-${String(i+1).padStart(2,'0')}.png`);
  await fs.writeFile(imagePath,new Uint8Array(await image.arrayBuffer()));
  pages.push(imagePath);
}
const manifest=path.join(build,'pages.json');
await fs.writeFile(manifest,JSON.stringify(pages));
const result=spawnSync(process.env.RUNTIME_PYTHON ?? 'python',
  [path.join(here,'images_to_pdf.py'),manifest,output],{encoding:'utf8'});
if(result.stdout) process.stdout.write(result.stdout);
if(result.status!==0) throw new Error(result.stderr || `PDF packaging failed: ${result.status}`);
console.log(`Exported ${pages.length} slides to ${output}`);

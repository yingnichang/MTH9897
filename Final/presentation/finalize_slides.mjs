/** Package editable chart workbooks and validate a separately staged deck.
 * Requires the Codex presentation skill and bundled Python, as documented.
 * Usage: node finalize_slides.mjs path/to/candidate.pptx path/to/final.pptx
 */
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import fs from 'node:fs/promises';
const skill=process.env.PRESENTATIONS_SKILL_DIR;
const python=process.env.RUNTIME_PYTHON;
if(!skill || !python || !process.env.RUNTIME_NODE_MODULES)
  throw new Error('Set PRESENTATIONS_SKILL_DIR, RUNTIME_PYTHON, and RUNTIME_NODE_MODULES to your bundled paths.');
const [input,output]=process.argv.slice(2);
if(!input || !output) throw new Error('Provide candidate and new final PPTX paths.');
const root=path.resolve(process.env.DECK_WORKSPACE ?? process.cwd());
const candidate=path.resolve(input), final=path.resolve(output);
const manifest=JSON.parse(await fs.readFile(path.join(path.dirname(candidate),'deck_manifest.json'),'utf8'));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(path.dirname(final),{recursive:true});
await fs.mkdir(path.join(root,'.slide-validation'),{recursive:true});
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,
  pythonExecutable:python,
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--validate-bullet-geometry',
    ...manifest.nativeTables.flatMap(n=>['--require-native-table-slide',String(n)])],
  requiredNativeTableOwnerSlides:manifest.nativeTables,requiredNativeChartOwnerSlides:manifest.nativeCharts,
  materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:['Arial']},
  verifyArtifactToolImport:true,
  receiptPath:path.join(root,'.slide-validation',`${path.basename(final)}.validation.json`)
});
console.log(`Finalized ${final}`);

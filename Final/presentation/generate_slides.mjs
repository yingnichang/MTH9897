/**
 * Generate an editable PowerPoint from the notebook's saved synthetic results.
 * Requires the Codex-bundled @oai/artifact-tool runtime (see README.md).
 * No data downloads, credentials, or machine-specific paths are embedded.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const toolModule = process.env.ARTIFACT_TOOL_MODULE;
const { Presentation, PresentationFile } = await import(
  toolModule ? pathToFileURL(path.resolve(toolModule)).href : '@oai/artifact-tool'
);
const data = JSON.parse(await fs.readFile(path.join(HERE, 'slide_data.json'), 'utf8'));
if (data.manifest.mode !== 'demo') throw new Error('Revise slide claims before switching to empirical data.');
const OUTPUT = path.resolve(process.env.DECK_OUTPUT ?? path.join(HERE, 'conservative_formula_presentation.pptx'));
const PREVIEW = process.env.PREVIEW_DIR ? path.resolve(process.env.PREVIEW_DIR) : null;
const FONT = 'Arial';
const C = { navy:'#152D3B', teal:'#137D8D', ink:'#213A47', muted:'#56707D', light:'#F3F6F7', white:'#FFFFFF', amber:'#996211' };
const deck = Presentation.create({ slideSize: { width:1280, height:720 } });
const paper = 'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152';
const guide = 'https://www.robeco.com/docm/docu-202302-guide-to-conservative-investing.pdf';
const crsp = 'https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Databases_Summary_of_CIZ_Differences_to_Legacy_Files.pdf';
const repo = 'https://github.com/yingnichang/MTH9897/tree/main/Final';
const pct = n => `${(100*n).toFixed(2)}%`;
const fixed = n => n.toFixed(2);
const specs = [];

function text(s, content, x, y, w, h, size=28, color=C.ink, bold=false) {
  const shape = s.shapes.add({geometry:'textbox', position:{left:x,top:y,width:w,height:h},
    fill:'none', line:{fill:'none',width:0}});
  shape.text = content;
  shape.text.style = {typeface:FONT,fontSize:size,color,bold,autoFit:'none'};
  return shape;
}
function slide(title, notes, opts={}) {
  const s=deck.slides.add();
  s.background.fill=opts.dark ? C.navy : C.white;
  const number=specs.length+1;
  if(title) text(s,title,64,42,1150,80,44,opts.dark?C.white:C.navy,true);
  text(s,`${number.toString().padStart(2,'0')}`,1164,674,50,26,17,opts.dark?'#B8CAD2':C.muted);
  s.speakerNotes.textFrame.setText(notes);
  specs.push({number,title,notes});
  return s;
}
function subtitle(s,t){text(s,t,64,124,1148,62,25,C.muted);}
function footer(s,t){text(s,t,64,631,1072,45,18,C.muted);}
function demo(s){text(s,'SYNTHETIC DEMONSTRATION',64,126,1140,35,23,C.amber,true);}
function table(s,values,widths,y=200,rowHeight=70,size=24){
  const t=s.tables.add({rows:values.length,columns:values[0].length,left:64,top:y,
    width:1152,height:rowHeight*values.length,columnWidths:widths,values});
  t.borders.assign({fill:'#DBE3E7',width:0.6,style:'solid'});
  t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({
    textStyle:{typeface:FONT,fontSize:size,color:C.ink}, margins:{left:14,right:14,top:10,bottom:10},
    fill:C.white});
  t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({
    fill:C.navy,textStyle:{typeface:FONT,fontSize:size,color:C.white,bold:true}});
  return t;
}
function chart(s,type,config){
  const style={typeface:FONT,fontSize:22,fill:C.ink};
  // Excel stores at most 15 significant digits. Round chart values only.
  config.series=config.series.map(series=>({...series,values:series.values.map(v=>Number(v.toFixed(10)))}));
  return s.charts.add(type,{position:{left:64,top:198,width:1152,height:400},
    chartFill:C.white,plotAreaFill:C.white,chartLine:{fill:'none',width:0},
    titlePlacement:'none',hasLegend:false,
    xAxis:{textStyle:style,line:{fill:'#B8CAD2',width:1}},
    yAxis:{textStyle:style,majorGridlines:{fill:'#E1E7EA',width:1}},
    ...config});
}

// 1. Minimal editable cover.
{
  const s=slide('',`This presentation accompanies the first draft of Project 8 for MTH 9897. It asks whether the Conservative Formula still works. The implementation and displayed numerical outputs currently use seeded synthetic data. State this clearly before discussing any chart. Real CRSP analysis remains the next stage. Suggested talk length: 12 to 15 minutes, plus questions.\nSources: ${paper}\nProject: ${repo}`,{dark:true});
  specs[0].title='Does the Conservative Formula still work?';
  text(s,'Does the Conservative\nFormula still work?',64,133,1150,185,66,C.white,true);
  text(s,'Replication design and extensions',68,352,1100,60,34,'#B8D5DD');
  text(s,'MTH 9897  /  Project 8',68,449,1100,45,25,C.white);
  text(s,'First-draft presentation\nSynthetic demonstration results',68,546,1050,75,25,'#B8D5DD');
}
// 2. Research question and honest status.
{
  const s=slide('Research question',`The core question is whether combining the signals improves the risk-return tradeoff relative to simple controls. These are hypotheses, not findings. The code can already perform the comparisons. This presentation makes no claim about real investment performance. A favorable demo result would not validate the strategy, and an unfavorable one would not refute the paper.\nSources: notebook Sections 1 and 12. ${repo}`);
  text(s,'Does combining stable stocks with momentum\nand shareholder payouts improve performance?',64,183,1130,125,39,C.navy,true);
  text(s,'Comparisons',64,354,350,50,28,C.teal,true);
  text(s,'Market benchmark\nSingle-signal strategies\nResults after trading costs',64,419,570,155,29);
  text(s,'Current status',714,354,450,50,28,C.teal,true);
  text(s,'Executable research prototype\nHistorical equity data pending\nEmpirical conclusions remain open',714,419,500,155,27);
}
// 3. Selection algorithm.
{
  const s=slide('The portfolio selection rule',`The paper's full-data recipe starts with the largest 1,000 stocks at each quarter end. Keep the lower-volatility half, rank within that pool on momentum and net payout yield, and equal-weight the best 100. In the notebook, the 1,000-stock cap precedes the complete-case screen. If history is missing, the low-volatility pool may have fewer than 500 names. Formation audits report the actual counts. Do not imply every historical period has all 1,000 eligible stocks.\nSources: ${paper}\n${guide}\nNotebook Sections 2 and 5.`);
  subtitle(s,'Paper recipe at each quarter end, with sufficient eligible history');
  const rows=[['1,000','Largest eligible US stocks by market capitalization'],['500','Lower-volatility half using 36 months of returns'],['100','Best average ranks on momentum and payout yield']];
  rows.forEach((r,i)=>{text(s,r[0],64,220+i*118,235,85,62,C.teal,true);text(s,r[1],331,233+i*118,872,72,29);});
  footer(s,'Equal weights at formation. Quarterly rebalancing. Historical sample counts may be smaller.');
}
// 4. Signals.
{
  const s=slide('Signal definitions in the draft',`Volatility is annualized monthly sample standard deviation over 36 consecutive months. Momentum compounds 11 monthly price returns and skips the formation month. The payout measure uses the trailing twelve-month cash dividend yield plus one minus current adjusted shares divided by their trailing twenty-four-month mean. A falling share count increases this proxy. Dividends, prices, and shares require consistent split adjustments. The proxy needs reconciliation with the instructor or paper implementation before calling the study an exact replication.\nSources: notebook Sections 2 and 4. ${paper}`);
  table(s,[['Signal','Draft construction','Preference'],['Volatility','36-month return standard deviation','Lower'],['Momentum','11-month price return, skipping latest month','Higher'],['Payout proxy','Dividend yield + 1 − shares / 24-month mean','Higher']],[220,730,202],191,88,24);
  footer(s,'Payout definition remains subject to reconciliation with the paper.');
}
// 5. Timing.
{
  const s=slide('Information timing',`Use December as an example. Volatility includes returns through December, while momentum excludes December and compounds January through November. The portfolio first earns the following January return. The code carries monthly weight drift during the holding quarter. Month-end execution is idealized. A deployable strategy would use a subsequent tradable price and may need further lags for delayed fields. Avoid saying that timing eliminates every possible source of look-ahead bias.\nSource: notebook Sections 2, 4 and 6.`);
  subtitle(s,'Example: portfolio formed at December month end');
  table(s,[['Input or action','Window / timing'],['Volatility','36 months ending in December'],['Momentum','January through November'],['Selection','December month-end information'],['First earned return','Following January']],[410,742],196,73,25);
  footer(s,'Quarter-end execution is idealized. Late-reported inputs require an additional lag.');
}
// 6. Data.
{
  const s=slide('Historical study and demonstration data',`The course asks for CRSP performance beginning in 1929. Three years of earlier return history are needed for the first formation. The delivered draft instead uses 1,100 artificial securities from 2000 through 2025, with the first investment month in January 2003. There are no real delistings in the synthetic panel. The notebook tests terminal settlement separately using a hand-computed example. Do not confuse the scenario dates with observed market crises. The existing workspace bond files cannot support this equity study.\nSources: course brief pages 1 and 5. Notebook Sections 2 and 3. ${crsp}`);
  table(s,[['Dimension','Intended empirical study','Current demonstration'],['Source','WRDS / CRSP','Seeded synthetic generator'],['Return period','1929 to latest full year','January 2003–December 2025'],['Universe','Historical eligible US stocks','1,100 artificial securities'],['Interpretation','Test the paper’s findings','Illustrate the research workflow']],[235,472,445],186,79,24);
  footer(s,'Historical work must retain delisted names and reconcile legacy versus CIZ return conventions.');
}
// 7. Accounting.
{
  const s=slide('Portfolio accounting',`Between quarterly rebalances, stock weights drift with total returns. The next rebalance compares target weights with the drifted holdings. Traded stock notional sums buys and sells, including the initial purchase. The engine subtracts a proportional cost haircut before the next monthly return. A full replacement has two units of traded notional. Terminal proceeds earn the audited final return and then move to cash. Unknown held-stock returns raise an exception. This is a research cost approximation and excludes taxes and nonlinear impact.\nSource: notebook Sections 6 and 7.`);
  const items=[['Quarterly targets','Weights drift between rebalances'],['Trading costs','Charge both purchases and sales'],['Terminal events','Final proceeds move to cash'],['Missing held returns','Stop and reconcile the data']];
  items.forEach((r,i)=>{text(s,r[0],64,206+i*93,405,52,29,C.teal,true);text(s,r[1],505,206+i*93,704,66,29);});
  footer(s,'Costs, cash returns, and initial purchases enter the backtest explicitly.');
}
// 8. Comparisons.
{
  const s=slide('Experiments',`The full formula is the baseline. Dropping one signal at a time estimates its incremental contribution within this particular design. The signal strategies share a common complete-case sample and portfolio size. Separate universe benchmarks distinguish stock selection from equal weighting. The paper sample through 2016, the 2017–2018 transition, and the period from 2019 onward are fixed comparisons. A historical post-publication period is not an untouched prospective holdout for a researcher working in 2026.\nSource: notebook Sections 5 and 9–11.`);
  table(s,[['Comparison','Research purpose'],['Remove momentum or payout','Measure each signal’s incremental contribution'],['Remove the volatility screen','Test whether defensive selection matters'],['Equal / cap-weight universe','Separate selection effects from weighting'],['Later periods and costs','Assess stability and implementation sensitivity']],[465,687],194,80,25);
}
// 9. Native editable line chart.
{
  const s=slide('Demonstration wealth paths',`Every line on this slide comes from artificial data. We start at one dollar in December 2002 and show year-end wealth from compounded monthly returns through December 2025. The strategies pay ten basis points per dollar traded. The synthetic market benchmark is gross of implementation costs. Annual sampling reduces clutter and is not an annual rebalancing assumption. These curves show how the reporting works and cannot establish an investment premium.\nSource: slide_data.json, annual_wealth, generated from synthetic_demo_monthly_returns.csv. Seed 9897.`);
  demo(s);
  const colors=[C.teal,'#A86F2A','#82989D',C.navy];
  const names=['Conservative','Low volatility only','Universe equal weight','Market'];
  chart(s,'line',{lineOptions:{smooth:false},categories:data.annual_wealth.map(r=>r.year),
    series:names.map((name,i)=>({name,values:data.annual_wealth.map(r=>r[name]),line:{fill:colors[i],width:3},marker:{symbol:'none'}})),
    hasLegend:true,legend:{position:'bottom',textStyle:{typeface:FONT,fontSize:19,fill:C.ink}},
    yAxis:{title:{text:'Growth of $1',textStyle:{typeface:FONT,fontSize:22,fill:C.ink}},min:0,numberFormatCode:'0.0',textStyle:{typeface:FONT,fontSize:20,fill:C.ink},majorGridlines:{fill:'#E1E7EA',width:1}},
    xAxis:{textStyle:{typeface:FONT,fontSize:16,fill:C.ink}}});
  footer(s,'Year-end wealth, 2002–2025. Strategies include 10 bps per dollar traded. Synthetic market is gross.');
}
// 10. Metrics sourced directly from snapshot.
{
  const s=slide('Demonstration performance measures',`These are descriptive results over 276 synthetic investment months. CAGR compounds monthly returns. Annualized volatility scales monthly standard deviation by square root of twelve. Sharpe subtracts the supplied monthly risk-free return, which is 0.15 percent each month in the demo. Maximum drawdown includes initial wealth. Even if a row looks favorable, it is not a finding about CRSP stocks. All strategy figures include ten basis points per dollar traded, while the market row does not pay an execution charge.\nSource: slide_data.json, performance, from synthetic_demo_performance.csv.`);
  demo(s);
  const names=['Conservative','Low volatility only','Universe equal weight','Market'];
  table(s,[['Portfolio','CAGR','Volatility','Sharpe','Max drawdown'],...names.map(n=>{const p=data.performance[n];return [n,pct(p.CAGR),pct(p['Ann. volatility']),fixed(p.Sharpe),pct(p['Max drawdown'])];})],[360,172,192,156,272],200,76,24);
  footer(s,'January 2003–December 2025. Synthetic results provide no evidence of real-world outperformance.');
}
// 11. Ablation chart.
{
  const s=slide('Synthetic signal comparisons',`This slide illustrates the proposed ablation test. The chart shows annualized Sharpe ratios for the full combination and versions that remove one component. The simulated differences are small and do not prove any signal adds or subtracts value in real markets. In the empirical study, discuss uncertainty, drawdowns, turnover, and changes in exposures alongside Sharpe. These comparisons should use pre-specified rules rather than searching for the best-looking variation.\nSource: slide_data.json, performance. All values refer to 2003–2025 synthetic returns with 10 bps trading costs.`);
  demo(s);
  const names=['Conservative','No momentum','No payout','No low-vol screen'];
  chart(s,'bar',{categories:names,series:[{name:'Annualized Sharpe',values:names.map(n=>data.performance[n].Sharpe),fill:C.teal,valuesFormatCode:'0.00'}],
    barOptions:{direction:'column',grouping:'clustered',gapWidth:130},
    dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:FONT,fontSize:23,fill:C.ink}},
    yAxis:{min:0,max:.45,numberFormatCode:'0.00',textStyle:{typeface:FONT,fontSize:21,fill:C.ink},majorGridlines:{fill:'#E1E7EA',width:1}}});
  footer(s,'Annualized Sharpe, January 2003–December 2025. Interpretation awaits historical equity data.');
}
// 12. Cost sensitivity.
{
  const s=slide('Synthetic trading-cost sensitivity',`The portfolio positions stay fixed across all four scenarios. Costs increase from zero to fifty basis points per dollar bought or sold. The downward change in compounded return demonstrates the cost accounting, not a measured historical cost curve. In real data, estimate turnover and consider spreads and market impact by period and trade size. The simulator currently uses a proportional cost haircut and omits taxes and nonlinear execution effects.\nSource: slide_data.json, costs, from synthetic_demo_cost_sensitivity.csv.`);
  demo(s);
  chart(s,'bar',{categories:data.costs.map(r=>`${r['bps per dollar traded']} bps`),
    series:[{name:'CAGR',values:data.costs.map(r=>r.CAGR),fill:C.teal,valuesFormatCode:'0.00%'}],
    barOptions:{direction:'column',grouping:'clustered',gapWidth:150},
    dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:FONT,fontSize:23,fill:C.ink}},
    yAxis:{min:0,max:.075,numberFormatCode:'0%',textStyle:{typeface:FONT,fontSize:22,fill:C.ink},majorGridlines:{fill:'#E1E7EA',width:1}}});
  footer(s,'Synthetic CAGR, 2003–2025. Basis points apply to each dollar traded. These are assumed cost scenarios.');
}
// 13. Research conclusion without invented findings.
{
  const s=slide('Empirical conclusions remain open',`The project now has a transparent implementation and pre-specified extensions. It does not yet answer whether the strategy works. The next stage is to assemble audited CRSP history, reconcile the payout definition, and repeat the experiments. After that, add factor attribution and robust uncertainty estimates. Sector constraints are an optional extension after the baseline. A final presentation should replace the synthetic results with empirical outputs and revise the conclusion accordingly.\nSource: notebook Sections 12 and 13.`);
  text(s,'The draft defines a reproducible test\nof the Conservative Formula',64,177,1150,118,40,C.navy,true);
  text(s,'Remaining work',64,351,420,50,29,C.teal,true);
  text(s,'Historical CRSP data and corporate-action audit\nPayout definition and sample reconciliation\nEmpirical comparisons and uncertainty estimates',64,421,1120,166,30);
  footer(s,'A successful replication may confirm, weaken, or reject the original findings.');
}
// 14. References.
{
  const s=slide('References and project files',`Primary paper: Pim van Vliet and David Blitz, March 2018 working paper, The Conservative Formula: Quantitative Investing Made Easy, SSRN 3145152. The published Journal of Portfolio Management version lists David Blitz and Pim van Vliet, volume 44, issue 7. Supporting overview: Robeco, The Introductory Guide to Conservative Investing, 2023. Data conventions: CRSP Summary of CIZ Differences to Legacy Files. Course source: MTH 9897 Final Projects 2026, pages 1 and 5.\n${paper}\n${guide}\n${crsp}\n${repo}`);
  text(s,'Van Vliet and Blitz (2018)',64,184,1140,44,29,C.teal,true);
  text(s,'The Conservative Formula: Quantitative Investing Made Easy\nSSRN 3145152',64,234,1140,82,26);
  text(s,'Supporting sources',64,352,1140,44,29,C.teal,true);
  text(s,'Robeco, Guide to Conservative Investing (2023)\nCRSP, Summary of CIZ Differences to Legacy Files\nMTH 9897, Final Projects 2026',64,402,1140,128,26);
  text(s,'Notebook, slides, and generator code',64,566,1140,38,24,C.teal,true);
  text(s,'github.com/yingnichang/MTH9897/tree/main/Final',64,607,1120,40,23);
}

await fs.mkdir(path.dirname(OUTPUT),{recursive:true});
await (await PresentationFile.exportPptx(deck)).save(OUTPUT);
const notes=specs.map(s=>`## ${s.number}. ${s.title}\n\n${s.notes}`).join('\n\n');
await fs.writeFile(path.join(path.dirname(OUTPUT),'speaker_notes.md'),`# Speaker notes\n\n${notes}\n`);
if(PREVIEW){
  await fs.mkdir(PREVIEW,{recursive:true});
  for(let i=0;i<deck.slides.items.length;i++){
    const s=deck.slides.items[i];
    const blob=await deck.export({slide:s,format:'png',scale:1});
    await fs.writeFile(path.join(PREVIEW,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
}
console.log(`Created ${specs.length} slides: ${OUTPUT}`);

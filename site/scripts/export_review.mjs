// Package the real working site. A server is required for image workers/WASM;
// single-file HTML snapshots cannot preserve the converter's actual functionality.
import { cpSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

if(!process.argv[2])throw new Error('Provide an output directory');
const site=fileURLToPath(new URL('../',import.meta.url));
const dist=resolve(site,'dist'), output=resolve(process.argv[2]);
if(output===dist||output.startsWith(dist+sep)||dist.startsWith(output+sep))throw new Error('Output must be separate from the site build');
if(!existsSync(join(dist,'index.html')))throw new Error('Run npm run build first');
mkdirSync(output,{recursive:true});
cpSync(dist,output,{recursive:true});
cpSync(join(site,'scripts/preview.mjs'),join(output,'preview-server.mjs'));
writeFileSync(join(output,'Apri-anteprima.cmd'),'@echo off\r\ncd /d "%~dp0"\r\nnode preview-server.mjs . 8793\r\npause\r\n');
writeFileSync(join(output,'LEGGIMI.txt'),'Anteprima completa del sito\n\nServe Node.js. Su Windows apri Apri-anteprima.cmd, poi visita http://127.0.0.1:8793/\nIl server resta sul tuo computer. Ctrl+C per fermarlo.\n\nLe fotografie vengono elaborate nel browser. Il modello AI e le librerie sono inclusi.\n');
console.log(`Working preview exported to ${output}`);

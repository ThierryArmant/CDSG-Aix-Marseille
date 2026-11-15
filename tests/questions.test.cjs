const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const test=require('node:test');
const page=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const respond=page.slice(page.indexOf('async function repondre(){'),page.indexOf('document.getElementById("go").onclick = repondre;'));
function setup(token){
  const elements={q:{value:'combien d unité militaire en vaucluse'}};
  for(const id of ['rep','repTxt','repSrc']) elements[id]={classList:{add(){},remove(){}},textContent:''};
  const context={document:{getElementById:id=>elements[id]},jeton:{value:token},
    inK:{value:'ancienne-cle'},inU:{value:'https://albert.api.etalab.gouv.fr/v1'},
    chercherLocal:()=>({liste:[]}),fichesChips(){},lancerQuestionWeb:async()=>{context.serverCalls++;},
    serverCalls:0,fetch:()=>{throw Error('appel direct inattendu');}};
  vm.createContext(context);vm.runInContext(respond,context);
  return {context,elements};
}
test('Chercher utilise le serveur si le jeton est disponible',async()=>{
  const {context}=setup('jeton-test');await context.repondre();assert.equal(context.serverCalls,1);
});
test('Albert sans connexion affiche le blocage sans appel CORS ni faux résultat',async()=>{
  const {context,elements}=setup('');await context.repondre();
  assert.match(elements.repTxt.textContent,/IA n’est pas connectée/);
  assert.equal(context.serverCalls,0);
});
test('la session est restaurée après initialisation du champ, sans écraser le jeton',()=>{
  const field={value:''};const start=page.indexOf('const jeton = document.getElementById("ghJeton");');
  const snippet=page.slice(start,page.indexOf('const CHAMPS',start));
  const context={document:{getElementById:()=>field},localStorage:{getItem:()=>null},
    sessionStorage:{getItem:k=>k==='cdsg_role'?'animateur':'jeton-session'},
    modeGestion:(role,tok)=>{field.value=tok;}};
  vm.runInNewContext(snippet,context);
  assert.equal(field.value,'jeton-session');
});

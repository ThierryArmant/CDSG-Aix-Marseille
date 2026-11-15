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

const helpers=page.slice(page.indexOf('function titreDoublon('),page.indexOf('/* ───────── Médailles'));
function dedup(){const c={};vm.createContext(c);vm.runInContext(helpers,c);return c;}
test('fusionne les variantes de rang typographique sans fusionner des prix distincts',()=>{
  const c=dedup(),base={type:'distinction',date:null,source:'https://source.fr'};
  const result=c.elementsUniques([
    {...base,titre:'5ᵉ Prix Départemental – Devoir Collectif'},
    {...base,titre:'5e Prix Départemental – Devoir Collectif (concours de la Résistance)'},
    {...base,titre:'19e Prix Départemental – Devoir Individuel'},
    {...base,titre:'5e Prix Départemental – Devoir Collectif',date:'2025'},
  ]);assert.equal(result.length,3);
});
test('une carte par article, sans effacer les événements de la chronologie',()=>{
  const c=dedup(),events=[{type:'article',titre:'Article',source:'https://a.fr',image:'photo.jpg'},
    {type:'sortie',titre:'Visite',source:'https://a.fr',image:'photo.jpg'},
    {type:'ceremonie',titre:'Cérémonie',source:'https://b.fr',image:'photo.jpg'}];
  const cards=c.articlesUniques(events);assert.equal(cards.length,2);
  assert.equal(cards.filter(e=>e.image).length,1);assert.equal(c.elementsUniques(events).length,3);
});
test('préserve les photos manuelles et masque les images automatiques partagées',()=>{
  const c=dedup(),w={a:{photo:{url:'x.jpg'}},b:{photo:{url:'x.jpg'}},c:{photo:{url:'x.jpg',manuel:true}}};
  const result=c.photosSansRepetition(w);assert.equal(result.a.photo,null);
  assert.equal(result.c.photo.manuel,true);assert.equal(w.a.photo.url,'x.jpg');
});

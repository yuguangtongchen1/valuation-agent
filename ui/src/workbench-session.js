const key='valuation-workbench-session-v1';

export function readWorkbenchSession(storage=window.sessionStorage){
 try{return JSON.parse(storage.getItem(key)||'null');}catch{return null;}
}

export function rememberWorkbenchSession(view,quote,storage=window.sessionStorage){
 // Imported files already live in IndexedDB; only the tiny live demo needs a copy.
 try{storage.setItem(key,JSON.stringify({...view,demoQuote:quote?.id==='verified-demo'?quote:undefined}));}catch{}
}

export function resolveWorkbenchQuote(view,quotes,demoQuote){
 return quotes.find(q=>q.id===view?.quoteId)||(demoQuote?.id===view?.quoteId?demoQuote:null);
}

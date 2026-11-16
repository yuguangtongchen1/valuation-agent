import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import DataWorkbench from './DataWorkbench.jsx';
import './styles.css';
class WorkbenchBoundary extends React.Component {
 state={error:null};
 static getDerivedStateFromError(error){return {error};}
 render(){if(this.state.error)return <main style={{padding:32,fontFamily:'sans-serif'}}><h1>工作台加载遇到问题</h1><p role="alert">{String(this.state.error.message||this.state.error)}</p><button onClick={()=>{sessionStorage.removeItem('valuation-workbench-session-v1');location.assign('/?handoff=1');}}>重新载入当前报价</button></main>;return this.props.children;}
}
createRoot(document.getElementById('root')).render(<WorkbenchBoundary>{location.pathname==='/data'?<DataWorkbench/>:<App/>}</WorkbenchBoundary>);

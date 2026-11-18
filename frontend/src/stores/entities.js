import {nodesAPI,scenariosAPI,drillsAPI,txDrillsAPI} from '../api/entities.js';
export const store={nodes:[],scenarios:[],drills:[],txDrills:[],async refresh(){[this.nodes,this.scenarios,this.drills,this.txDrills]=await Promise.all([nodesAPI.list(),scenariosAPI.list(),drillsAPI.list(),txDrillsAPI.list()]);}};

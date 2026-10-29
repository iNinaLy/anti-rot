import type { ActivityModule } from '../core/registry';

const module: ActivityModule = { id:'rewards', title:'Rewards', description:'', TodayCard: () => <div className="activity-card"><span className="activity-icon">✦</span><div><strong>Your rewards</strong><p>Spend the points you’ve earned.</p></div><button className="secondary" onClick={() => window.dispatchEvent(new Event('open-rewards'))}>Open rewards</button></div> };
export default module;

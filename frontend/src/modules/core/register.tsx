import type { ActivityModule } from './registry';

const module: ActivityModule = {
  id: 'history', title: 'Activity history', description: '',
  TodayCard: () => <div className="activity-card"><span className="activity-icon">▦</span><div><strong>Activity history</strong><p>Your completed learning and exercise.</p></div>
    <button className="secondary" onClick={() => window.dispatchEvent(new Event('open-history'))}>Open history</button></div>,
};
export default module;

import { activities } from './registry';
import type { Today as TodayType } from '../../types';

export function Today({ today }: { today: TodayType }) {
  return <section aria-label="Today's activity"><div className="section-heading"><h2>Your day, so far</h2><span>Resets at midnight UTC</span></div>
    {activities.map(activity => <activity.TodayCard key={activity.id} today={today} />)}</section>;
}

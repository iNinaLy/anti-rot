import type { ActivityModule } from '../core/registry';

const activity: ActivityModule = {
  id: 'flashcards', title: 'Flashcards', description: 'Make a little room for what you want to remember.',
  TodayCard: ({ today }) => {
    const count = today.activities.find(a => a.type === 'flashcards')?.completions || 0;
    return <div className="activity-card"><span className="activity-icon">▤</span><div><strong>Daily learning</strong>
      <p>{count ? `${count} review session${count === 1 ? '' : 's'} completed today` : 'Your next small step starts with a deck.'}</p></div>
      <span className={count ? 'badge' : 'badge neutral'}>{count ? '✓ Complete' : 'Ready when you are'}</span></div>;
  },
};
export default activity;

import type { ActivityModule } from '../core/registry';
import { NewsToday } from './News';

const module: ActivityModule = { id: 'news', title: 'News', description: '', TodayCard: () => <NewsToday /> };
export default module;

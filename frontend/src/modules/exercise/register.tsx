import type { ActivityModule } from '../core/registry';
import { ExerciseToday } from './Exercise';

const module: ActivityModule = {
  id: 'exercise', title: 'Exercise', description: '',
  TodayCard: ({ today }) => <ExerciseToday refresh={today} />,
};
export default module;

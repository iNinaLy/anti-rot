import type { ComponentType } from 'react';
import type { Today } from '../../types';

export interface ActivityModule {
  id: string;
  title: string;
  description: string;
  TodayCard: ComponentType<{ today: Today }>;
}
// A new module exports a default ActivityModule from its own register.tsx.
const registrations = import.meta.glob<{ default: ActivityModule }>('../*/register.tsx', { eager: true });
export const activities = Object.values(registrations).map(module => module.default);

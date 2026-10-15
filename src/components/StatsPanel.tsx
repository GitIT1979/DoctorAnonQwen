import { DataCategory, customCategory } from '../utils/dataCategories';
import { FoundData } from '../utils/anonymizer';

interface StatsPanelProps {
  foundData: FoundData[];
  categories: DataCategory[];
}

export default function StatsPanel({ foundData, categories }: StatsPanelProps) {
  const allCategories = [...categories, customCategory];
  const enabledCategories = categories.filter((c) => c.enabled);
  const totalFound = foundData.length;
  const willBeRedacted = foundData.filter((d) => {
    if (d.categoryId === 'custom') return true;
    const cat = categories.find((c) => c.id === d.categoryId);
    return cat?.enabled;
  }).length;
  const willBeVisible = totalFound - willBeRedacted;

  // Group by category
  const grouped: Record<string, number> = {};
  for (const data of foundData) {
    grouped[data.categoryId] = (grouped[data.categoryId] || 0) + 1;
  }

  const sortedCategories = Object.entries(grouped)
    .sort(([, a], [, b]) => b - a)
    .map(([catId, count]) => ({
      category: allCategories.find((c) => c.id === catId),
      count,
    }))
    .filter((item) => item.category);

  return (
    <div className="space-y-4">
      {/* Main Stats */}
      <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">📊 Статистика</h3>
        <div className="space-y-3">
          <StatRow label="Всего найдено" value={totalFound} color="text-green-400" />
          <StatRow label="Будет скрыто" value={willBeRedacted} color="text-red-400" />
          <StatRow label="Останется видимым" value={willBeVisible} color="text-gray-400" />
        </div>
      </div>

      {/* Breakdown by category */}
      {sortedCategories.length > 0 && (
        <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">📋 По категориям</h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {sortedCategories.map(({ category, count }) => (
              <div key={category!.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{category!.icon}</span>
                  <span className="text-xs text-gray-400 truncate max-w-[150px]">
                    {category!.name}
                  </span>
                </div>
                <span className={`text-sm font-bold ${
                  category!.enabled ? 'text-red-400' : 'text-gray-500'
                }`}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">📈 Уровень анонимизации</h3>
        <div className="relative h-3 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-600 to-red-400 rounded-full transition-all"
            style={{ width: `${totalFound > 0 ? (willBeRedacted / totalFound) * 100 : 0}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 mt-2">
          {totalFound > 0
            ? `${Math.round((willBeRedacted / totalFound) * 100)}% данных будет скрыто`
            : 'Персональные данные не обнаружены'}
        </p>
      </div>
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-400">{label}</span>
      <span className={`text-lg font-bold ${color}`}>{value}</span>
    </div>
  );
}

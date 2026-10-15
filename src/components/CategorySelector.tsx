import { DataCategory } from '../utils/dataCategories';
import { FoundData } from '../utils/anonymizer';

interface CategorySelectorProps {
  categories: DataCategory[];
  foundData: FoundData[];
  onToggle: (categoryId: string) => void;
  onToggleAll: (enabled: boolean) => void;
}

export default function CategorySelector({
  categories,
  foundData,
  onToggle,
  onToggleAll,
}: CategorySelectorProps) {
  const getCountByCategory = (categoryId: string) => {
    return foundData.filter((d) => d.categoryId === categoryId).length;
  };

  // Фильтруем только категории с найденными данными
  const categoriesWithFindings = categories.filter((category) => {
    const count = getCountByCategory(category.id);
    return count > 0;
  });

  const totalFound = foundData.length;
  const totalWillBeRedacted = foundData.filter((d) => {
    const cat = categories.find((c) => c.id === d.categoryId);
    return cat?.enabled;
  }).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Обнаруженные данные</h2>
        <div className="flex gap-2">
          <button
            onClick={() => onToggleAll(true)}
            className="px-3 py-1.5 text-sm bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors font-medium"
          >
            ✓ Все
          </button>
          <button
            onClick={() => onToggleAll(false)}
            className="px-3 py-1.5 text-sm bg-red-600 text-white hover:bg-red-700 rounded-lg transition-colors font-medium"
          >
            ✗ Все
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="flex items-center gap-4 text-sm text-gray-400">
        <span>
          Найдено: <strong className="text-red-400">{totalFound}</strong>
        </span>
        <span>
          Скрыто: <strong className="text-green-400">{totalWillBeRedacted}</strong>
        </span>
        <span>
          Видимо: <strong className="text-gray-300">{totalFound - totalWillBeRedacted}</strong>
        </span>
      </div>

      {/* Categories Grid */}
      {categoriesWithFindings.length > 0 ? (
        <div className="space-y-2">
          {categoriesWithFindings.map((category) => {
            const count = getCountByCategory(category.id);
            return (
              <div
                key={category.id}
                className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 border border-gray-700 hover:bg-gray-700/50 transition-all cursor-pointer"
                onClick={() => onToggle(category.id)}
              >
                <div className="flex items-center gap-3 flex-1">
                  <span className="text-xl">{category.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className={`font-medium text-sm ${
                        category.enabled ? 'text-green-400' : 'text-red-400'
                      }`}>{category.name}</h3>
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
                        {count}
                      </span>
                    </div>
                  </div>
                </div>
                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                  category.enabled
                    ? 'bg-green-500 border-green-500'
                    : 'bg-transparent border-gray-500'
                }`}>
                  {category.enabled && (
                    <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-8 bg-gray-800/30 rounded-xl border border-gray-700 text-center">
          <div className="text-4xl mb-3">🔍</div>
          <p className="text-gray-400">Персональные данные не обнаружены</p>
          <p className="text-xs text-gray-500 mt-1">Попробуйте добавить пользовательские паттерны для поиска</p>
        </div>
      )}
    </div>
  );
}

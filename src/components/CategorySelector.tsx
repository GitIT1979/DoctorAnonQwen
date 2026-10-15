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

  const totalEnabled = categories.filter((c) => c.enabled).length;
  const totalFound = foundData.length;
  const totalWillBeRedacted = foundData.filter((d) => {
    const cat = categories.find((c) => c.id === d.categoryId);
    return cat?.enabled;
  }).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Категории персональных данных</h2>
          <p className="text-gray-400 text-sm mt-1">
            Выберите, какие категории данных следует скрыть в документе
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onToggleAll(true)}
            className="px-3 py-1.5 text-sm bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg transition-colors"
          >
            Скрыть всё
          </button>
          <button
            onClick={() => onToggleAll(false)}
            className="px-3 py-1.5 text-sm bg-gray-700 text-gray-400 hover:bg-gray-600 rounded-lg transition-colors"
          >
            Показать всё
          </button>
        </div>
      </div>

      {/* Summary bar */}
      <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-6 text-sm">
          <span className="text-gray-400">
            Категорий: <strong className="text-white">{totalEnabled}/{categories.length}</strong>
          </span>
          <span className="text-gray-400">
            Найдено данных: <strong className="text-yellow-400">{totalFound}</strong>
          </span>
          <span className="text-gray-400">
            Будет скрыто: <strong className="text-red-400">{totalWillBeRedacted}</strong>
          </span>
        </div>
      </div>

      {/* Categories Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {categories.map((category) => {
          const count = getCountByCategory(category.id);
          return (
            <div
              key={category.id}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                category.enabled
                  ? 'bg-red-900/10 border-red-700/50 hover:bg-red-900/20'
                  : 'bg-gray-800/30 border-gray-700 hover:bg-gray-800/50'
              }`}
              onClick={() => onToggle(category.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{category.icon}</span>
                  <div>
                    <h3 className="font-semibold text-white text-sm">{category.name}</h3>
                    <p className="text-xs text-gray-400 mt-0.5">{category.description}</p>
                    {count > 0 && (
                      <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs font-medium ${
                        category.enabled
                          ? 'bg-red-600/20 text-red-400'
                          : 'bg-gray-700 text-gray-400'
                      }`}>
                        Найдено: {count}
                      </span>
                    )}
                    {count === 0 && (
                      <span className="inline-block mt-2 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-700/50 text-gray-500">
                        Не обнаружено
                      </span>
                    )}
                  </div>
                </div>
                <div className={`w-10 h-6 rounded-full relative transition-colors ${
                  category.enabled ? 'bg-red-600' : 'bg-gray-600'
                }`}>
                  <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                    category.enabled ? 'translate-x-5' : 'translate-x-1'
                  }`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

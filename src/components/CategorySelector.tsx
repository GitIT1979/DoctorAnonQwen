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
        <div>
          <h2 className="text-2xl font-bold">Категории персональных данных</h2>
          <p className="text-gray-400 text-sm mt-1">
            Выберите, какие категории данных следует скрыть в документе
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onToggleAll(true)}
            className="px-3 py-1.5 text-sm bg-red-600 text-white hover:bg-red-700 rounded-lg transition-colors font-medium"
          >
            🔒 Скрыть всё
          </button>
          <button
            onClick={() => onToggleAll(false)}
            className="px-3 py-1.5 text-sm bg-white text-gray-900 hover:bg-gray-100 border border-gray-300 rounded-lg transition-colors font-medium"
          >
            👁️ Показать всё
          </button>
        </div>
      </div>

      {/* Summary bar */}
      <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-6 text-sm">
          <span className="text-gray-400">
            Обнаружено категорий: <strong className="text-white">{categoriesWithFindings.length}</strong>
          </span>
          <span className="text-gray-400">
            Найдено данных: <strong className="text-yellow-400">{totalFound}</strong>
          </span>
          <span className="text-gray-400">
            Будет скрыто: <strong className="text-red-400">{totalWillBeRedacted}</strong>
          </span>
          <span className="text-gray-400">
            Останется видимым: <strong className="text-green-400">{totalFound - totalWillBeRedacted}</strong>
          </span>
        </div>
      </div>

      {/* Categories Grid */}
      {categoriesWithFindings.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {categoriesWithFindings.map((category) => {
            const count = getCountByCategory(category.id);
            return (
              <div
                key={category.id}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  category.enabled
                    ? 'bg-red-600 border-red-500 hover:bg-red-700'
                    : 'bg-white border-gray-300 hover:bg-gray-50'
                }`}
                onClick={() => onToggle(category.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{category.icon}</span>
                    <div>
                      <h3 className={`font-semibold text-sm ${
                        category.enabled ? 'text-white' : 'text-gray-900'
                      }`}>{category.name}</h3>
                      <p className={`text-xs mt-0.5 ${
                        category.enabled ? 'text-red-100' : 'text-gray-600'
                      }`}>{category.description}</p>
                      <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs font-medium ${
                        category.enabled
                          ? 'bg-amber-100/20 text-amber-100'
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        Найдено: {count}
                      </span>
                    </div>
                  </div>
                  <div className={`w-10 h-6 rounded-full relative transition-colors ${
                    category.enabled ? 'bg-green-500' : 'bg-red-500'
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

import { useState } from 'react';
import { FoundData } from '../utils/anonymizer';

interface FoundDataListProps {
  foundData: FoundData[];
  onRemoveItem: (id: string) => void;
}

export default function FoundDataList({ foundData, onRemoveItem }: FoundDataListProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  const categories = [...new Set(foundData.map((d) => d.categoryName))];
  
  const filteredData = filter === 'all' 
    ? foundData 
    : foundData.filter((d) => d.categoryId === filter);

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🔍</span>
          <span className="font-semibold text-white text-sm">Найденные данные</span>
          <span className="px-2 py-0.5 bg-yellow-600/20 text-yellow-400 rounded-full text-xs">
            {foundData.length}
          </span>
        </div>
        <span className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div className="p-4 border-t border-gray-700 space-y-3">
          <p className="text-xs text-gray-400">
            Нажмите × чтобы исключить элемент из анонимизации
          </p>

          {/* Filter */}
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => setFilter('all')}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              Все ({foundData.length})
            </button>
            {categories.map((catName) => {
              const count = foundData.filter((d) => d.categoryName === catName).length;
              const catId = foundData.find((d) => d.categoryName === catName)?.categoryId || '';
              return (
                <button
                  key={catId}
                  onClick={() => setFilter(catId)}
                  className={`px-2 py-1 rounded text-xs transition-colors ${
                    filter === catId ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  {catName} ({count})
                </button>
              );
            })}
          </div>

          {/* Data List */}
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {filteredData.map((data) => (
              <div
                key={data.id}
                className="flex items-center justify-between p-2 bg-gray-900/50 rounded-lg group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-white truncate font-mono">
                    «{data.text}»
                  </p>
                  <p className="text-[10px] text-gray-500 mt-0.5">{data.categoryName}</p>
                </div>
                <button
                  onClick={() => onRemoveItem(data.id)}
                  className="ml-2 px-2 py-1 text-xs text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Исключить из анонимизации"
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          {filteredData.length === 0 && (
            <p className="text-center text-sm text-gray-500 py-4">
              Нет данных для отображения
            </p>
          )}
        </div>
      )}
    </div>
  );
}

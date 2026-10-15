import { useState } from 'react';

interface CustomPatternsProps {
  patterns: string[];
  onAdd: (pattern: string) => void;
  onRemove: (index: number) => void;
}

export default function CustomPatterns({ patterns, onAdd, onRemove }: CustomPatternsProps) {
  const [input, setInput] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const handleAdd = () => {
    const trimmed = input.trim();
    if (trimmed && !patterns.includes(trimmed)) {
      onAdd(trimmed);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd();
    }
  };

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">✏️</span>
          <span className="font-semibold text-white text-sm">Собственные данные для скрытия</span>
          {patterns.length > 0 && (
            <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 rounded-full text-xs">
              {patterns.length}
            </span>
          )}
        </div>
        <span className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div className="p-4 border-t border-gray-700 space-y-3">
          <p className="text-xs text-gray-400">
            Добавьте конкретные слова, имена или фразы, которые нужно скрыть в документе
          </p>
          
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Введите слово или фразу..."
              className="flex-1 px-3 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleAdd}
              disabled={!input.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-sm transition-colors"
            >
              Добавить
            </button>
          </div>

          {patterns.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {patterns.map((pattern, index) => (
                <span
                  key={index}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-red-900/20 border border-red-700/30 text-red-300 rounded-lg text-xs"
                >
                  {pattern}
                  <button
                    onClick={() => onRemove(index)}
                    className="ml-1 text-red-400 hover:text-red-300"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

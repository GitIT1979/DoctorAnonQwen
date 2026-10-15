import { useMemo } from 'react';
import { DataCategory } from '../utils/dataCategories';
import { anonymizeText, FoundData } from '../utils/anonymizer';

interface DocumentPreviewProps {
  text: string;
  foundData: FoundData[];
  categories: DataCategory[];
}

export default function DocumentPreview({ text, foundData, categories }: DocumentPreviewProps) {
  const anonymizedHtml = useMemo(() => {
    return anonymizeText(text, foundData, categories);
  }, [text, foundData, categories]);

  return (
    <div className="bg-white rounded-xl shadow-2xl overflow-hidden">
      {/* Document Header */}
      <div className="bg-gray-100 px-6 py-3 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm text-gray-600 ml-2">Анонимизированный документ</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded">
            ██████ СЕКРЕТНО ██████
          </span>
        </div>
      </div>

      {/* Document Content */}
      <div className="p-8 max-h-[70vh] overflow-y-auto">
        <div
          className="font-mono text-sm leading-relaxed text-gray-800 whitespace-pre-wrap break-words"
          dangerouslySetInnerHTML={{ __html: anonymizedHtml }}
        />
      </div>

      {/* Legend */}
      <div className="bg-gray-50 px-6 py-3 border-t">
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-4 bg-black rounded-sm" />
            <span>Закрашенные данные</span>
          </span>
          <span>|</span>
          <span>Наведите на закрашенный текст для просмотра категории</span>
        </div>
      </div>
    </div>
  );
}

import { useMemo, useState, useEffect, useRef } from 'react';
import { DataCategory } from '../utils/dataCategories';
import { anonymizeText, FoundData } from '../utils/anonymizer';
import { ParsedDocument } from '../utils/documentParser';

interface DocumentPreviewProps {
  text: string;
  foundData: FoundData[];
  categories: DataCategory[];
  document?: ParsedDocument | null;
}

export default function DocumentPreview({ text, foundData, categories, document }: DocumentPreviewProps) {
  const anonymizedHtml = useMemo(() => {
    return anonymizeText(text, foundData, categories);
  }, [text, foundData, categories]);

  // For images, show the redacted image
  if (document?.format === 'image' && document.imageData) {
    return <ImagePreview document={document} foundData={foundData} categories={categories} />;
  }

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

function ImagePreview({ document, foundData, categories }: {
  document: ParsedDocument;
  foundData: FoundData[];
  categories: DataCategory[];
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const drawRedacted = async () => {
      if (!canvasRef.current || !document.imageData) return;
      
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        
        // Draw original image
        ctx.drawImage(img, 0, 0);
        
        // Get enabled categories
        const enabledCategories = new Set(
          categories.filter((c) => c.enabled).map((c) => c.id)
        );
        
        // Find and redact words
        const text = document.text;
        const ocrWords = document.ocrWords || [];
        
        const dataToRedact = foundData.filter(d => 
          d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
        );
        
        ctx.fillStyle = '#000000';
        
        for (const data of dataToRedact) {
          // Find OCR words within this data range
          for (const word of ocrWords) {
            const wordText = word.text.toLowerCase().trim();
            if (wordText.length < 2) continue;
            
            // Check if word position is within the found data range
            const wordPosInText = text.toLowerCase().indexOf(wordText);
            if (wordPosInText >= data.startIndex && wordPosInText < data.endIndex) {
              ctx.fillRect(
                word.bbox.x0,
                word.bbox.y0,
                word.bbox.x1 - word.bbox.x0,
                word.bbox.y1 - word.bbox.y0
              );
            }
          }
        }
        
        setIsReady(true);
      };
      img.src = document.imageData;
    };
    
    drawRedacted();
  }, [document, foundData, categories]);

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
          <span className="text-sm text-gray-600 ml-2">Анонимизированное изображение</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded">
            ██████ СЕКРЕТНО ██████
          </span>
        </div>
      </div>

      {/* Image Content */}
      <div className="p-4 max-h-[70vh] overflow-auto flex items-center justify-center bg-gray-50">
        {!isReady && (
          <div className="text-center py-10">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-gray-500 text-sm">Закрашивание персональных данных...</p>
          </div>
        )}
        <canvas
          ref={canvasRef}
          className={`max-w-full h-auto ${isReady ? '' : 'hidden'}`}
          style={{ imageRendering: 'auto' }}
        />
      </div>

      {/* Legend */}
      <div className="bg-gray-50 px-6 py-3 border-t">
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-4 bg-black rounded-sm" />
            <span>Закрашенные данные на изображении</span>
          </span>
          <span>|</span>
          <span>OCR: {document.ocrWords?.length || 0} слов распознано</span>
        </div>
      </div>
    </div>
  );
}

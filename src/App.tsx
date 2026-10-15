import { useState, useCallback } from 'react';
import { parseDocument, ParsedDocument } from './utils/documentParser';
import { DataCategory, getCategories } from './utils/dataCategories';
import { findPersonalData, anonymizeText, FoundData, generateReport, AnonymizationMode } from './utils/anonymizer';
import FileUpload from './components/FileUpload';
import CategorySelector from './components/CategorySelector';
import DocumentPreview from './components/DocumentPreview';
import StatsPanel from './components/StatsPanel';
import CustomPatterns from './components/CustomPatterns';
import FoundDataList from './components/FoundDataList';
import { exportDocument } from './utils/documentExporter';

type AppState = 'upload' | 'configure' | 'preview';

function App() {
  const [state, setState] = useState<AppState>('upload');
  const [categories, setCategories] = useState<DataCategory[]>(getCategories());
  const [foundData, setFoundData] = useState<FoundData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customPatterns, setCustomPatterns] = useState<string[]>([]);

  const [documents, setDocuments] = useState<ParsedDocument[]>([]);

  const [rejectedFiles, setRejectedFiles] = useState<Array<{filename: string, reason: string}>>([]);

  const handleFileUpload = useCallback(async (files: File[], isAdditional: boolean = false) => {
    setIsLoading(true);
    setError(null);
    if (!isAdditional) {
      setRejectedFiles([]);
    }
    
    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
    const MAX_FILES = 50;
    
    // Проверка количества файлов
    const totalFiles = isAdditional ? documents.length + files.length : files.length;
    if (totalFiles > MAX_FILES) {
      setError(`Максимум ${MAX_FILES} файлов. Всего будет: ${totalFiles}.`);
      setIsLoading(false);
      return;
    }
    
    try {
      const parsedDocs: ParsedDocument[] = [];
      const rejected: Array<{filename: string, reason: string}> = [];
      
      // Обработка каждого файла с защитой от ошибок
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Проверка размера файла
        if (file.size > MAX_FILE_SIZE) {
          rejected.push({filename: file.name, reason: 'файл слишком большой (максимум 50 MB)'});
          continue;
        }
        
        try {
          // Таймаут для обработки файла (60 секунд)
          const timeoutPromise = new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error('Превышено время обработки')), 60000);
          });
          
          const parsePromise = parseDocument(file);
          const parsed = await Promise.race([parsePromise, timeoutPromise]);
          parsedDocs.push(parsed);
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Неизвестная ошибка';
          rejected.push({filename: file.name, reason: errorMsg});
        }
      }
      
      // Если это дозагрузка, добавляем к существующим документам
      if (isAdditional) {
        setDocuments(prev => [...prev, ...parsedDocs]);
        if (rejected.length > 0) {
          setRejectedFiles(prev => [...prev, ...rejected]);
        }
      } else {
        // Первая загрузка - очищаем и устанавливаем новые
        setDocuments(parsedDocs);
        setRejectedFiles(rejected);
      }
      
      // Если нет успешно обработанных файлов
      if (parsedDocs.length === 0) {
        if (rejected.length > 0) {
          setError(`Не удалось обработать ни один файл:\n${rejected.map(r => `${r.filename}: ${r.reason}`).join('\n')}`);
        }
        setIsLoading(false);
        return;
      }
      
      // Переходим в состояние configure (если ещё не там)
      if (state !== 'configure') {
        setState('configure');
      }
      
      // Если есть отклонённые файлы, показываем предупреждение
      if (rejected.length > 0) {
        setError(`Обработано ${parsedDocs.length} из ${files.length} файлов. ${rejected.length} файл(ов) отклонено.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при загрузке файлов');
    } finally {
      setIsLoading(false);
    }
  }, [documents.length, state]);

  const handleCategoryToggle = useCallback((categoryId: string) => {
    setCategories(prev =>
      prev.map(cat =>
        cat.id === categoryId ? { ...cat, enabled: !cat.enabled } : cat
      )
    );
  }, []);

  const handleToggleAll = useCallback((enabled: boolean) => {
    setCategories(prev => prev.map(cat => {
      // Переключаем только категории, в которых есть находки
      const hasFindings = foundData.some(d => d.categoryId === cat.id);
      if (hasFindings) {
        return { ...cat, enabled };
      }
      return cat;
    }));
  }, [foundData]);

  const handleAnonymize = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const allData: FoundData[] = [];
      
      // Поиск персональных данных с защитой от зависания
      for (const doc of documents) {
        try {
          // Таймаут для поиска данных (30 секунд на документ)
          const timeoutPromise = new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error('Превышено время поиска')), 30000);
          });
          
          const searchPromise = new Promise<FoundData[]>((resolve) => {
            const data = findPersonalData(doc.text, categories, customPatterns);
            resolve(data);
          });
          
          const data = await Promise.race([searchPromise, timeoutPromise]);
          allData.push(...data);
        } catch (err) {
          console.error(`Ошибка поиска данных в ${doc.filename}:`, err);
        }
      }
      
      setFoundData(allData);
      setState('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при анонимизации');
    } finally {
      setIsLoading(false);
    }
  }, [documents, categories, customPatterns]);

  const handleBack = useCallback(() => {
    if (state === 'preview') {
      setState('configure');
    } else if (state === 'configure') {
      setState('upload');
      setDocuments([]);
      setFoundData([]);
    }
  }, [state]);

  const handleReset = useCallback(() => {
    setState('upload');
    setDocuments([]);
    setFoundData([]);
    setCategories(getCategories());
    setError(null);
    setCustomPatterns([]);
  }, []);

  const handleAddCustomPattern = useCallback((pattern: string) => {
    setCustomPatterns(prev => [...prev, pattern]);
  }, []);

  const handleRemoveCustomPattern = useCallback((index: number) => {
    setCustomPatterns(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleRemoveFoundItem = useCallback((id: string) => {
    setFoundData(prev => prev.filter(d => d.id !== id));
  }, []);

  const [isExporting, setIsExporting] = useState(false);

  const [anonymizationMode, setAnonymizationMode] = useState<AnonymizationMode>('redact');

  const handleDownloadOriginal = useCallback(async () => {
    if (documents.length === 0) return;
    setIsExporting(true);
    try {
      // Export each document separately
      for (let i = 0; i < documents.length; i++) {
        const doc = documents[i];
        const docData = foundData.filter(d => {
          // Find data that belongs to this document
          return doc.text.includes(d.text);
        });
        
        const blob = await exportDocument(doc, docData, categories, anonymizationMode);
        const url = URL.createObjectURL(blob);
        const a = window.document.createElement('a');
        a.href = url;
        a.download = `anonymized_${doc.filename}`;
        a.click();
        URL.revokeObjectURL(url);
        
        // Small delay between downloads
        if (i < documents.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при экспорте');
    } finally {
      setIsExporting(false);
    }
  }, [documents, foundData, categories, anonymizationMode]);

  const handleDownloadHtml = useCallback(() => {
    if (documents.length === 0) return;
    
    // Combine all documents
    let combinedContent = '';
    for (const doc of documents) {
      const docData = foundData.filter(d => doc.text.includes(d.text));
      // Для PDF используем anonymizationMode, для DOCX/MD всегда [censored]
      const mode = doc.format === 'pdf' ? anonymizationMode : 'censored';
      const anonymizedContent = anonymizeText(doc.text, docData, categories, mode);
      combinedContent += `\n\n${'='.repeat(80)}\n`;
      combinedContent += `Файл: ${doc.filename}\n`;
      combinedContent += `${'='.repeat(80)}\n\n`;
      combinedContent += anonymizedContent;
    }
    
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Анонимизированные документы</title>
  <style>
    body {
      font-family: 'Courier New', monospace;
      max-width: 800px;
      margin: 0 auto;
      padding: 40px;
      line-height: 1.6;
      background: white;
    }
    .redacted {
      background-color: #000;
      color: #000;
      padding: 0 2px;
      border-radius: 2px;
      user-select: none;
    }
    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    @media print {
      .redacted {
        background-color: #000 !important;
        color: #000 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
    }
  </style>
</head>
<body>
  <h1 style="text-align:center; border-bottom: 2px solid #000; padding-bottom: 10px;">
    ██████ СЕКРЕТНО ██████
  </h1>
  <pre>${combinedContent}</pre>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `anonymized_documents.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [documents, foundData, categories, anonymizationMode]);

  const handleDownloadReport = useCallback(() => {
    if (documents.length === 0) return;
    const report = generateReport(foundData, categories);
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `report_${documents.length}_files.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [documents, foundData, categories]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-gray-700 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">DocAnon</h1>
              <p className="text-xs text-gray-400">Анонимизация документов</p>
            </div>
          </div>
          
          {state !== 'upload' && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleBack}
                className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              >
                ← Назад
              </button>
              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg transition-colors"
              >
                Сбросить
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Progress Steps */}
      {state !== 'upload' && (
        <div className="max-w-7xl mx-auto px-4 pt-6">
          <div className="flex items-center gap-2 text-sm">
            <StepIndicator step={1} label="Загрузка" active={false} completed={true} />
            <div className="w-8 h-px bg-gray-600" />
            <StepIndicator step={2} label="Настройка" active={state === 'configure'} completed={state === 'preview'} />
            <div className="w-8 h-px bg-gray-600" />
            <StepIndicator step={3} label="Результат" active={state === 'preview'} completed={false} />
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
            ⚠️ {error}
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-gray-400">Обработка документа...</p>
              <p className="text-gray-500 text-sm mt-2">
                Распознавание текста может занять некоторое время
              </p>
            </div>
          </div>
        )}

        {!isLoading && state === 'upload' && (
          <FileUpload onFileUpload={handleFileUpload} />
        )}

        {!isLoading && state === 'configure' && documents.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <CategorySelector
                categories={categories}
                foundData={foundData}
                onToggle={handleCategoryToggle}
                onToggleAll={handleToggleAll}
              />
              <CustomPatterns
                patterns={customPatterns}
                onAdd={handleAddCustomPattern}
                onRemove={handleRemoveCustomPattern}
              />
              <FoundDataList
                foundData={foundData}
                onRemoveItem={handleRemoveFoundItem}
              />
              
              {/* Anonymization Mode - только для PDF */}
              {documents.some(doc => doc.format === 'pdf') && (
                <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                  <h3 className="text-sm font-semibold text-gray-300 mb-3">Режим анонимизации для PDF</h3>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="mode"
                        value="redact"
                        checked={anonymizationMode === 'redact'}
                        onChange={() => setAnonymizationMode('redact')}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">Закрасить чёрным (███)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="mode"
                        value="remove"
                        checked={anonymizationMode === 'remove'}
                        onChange={() => setAnonymizationMode('remove')}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">Удалить полностью</span>
                    </label>
                  </div>
                  <p className="text-xs text-gray-500 mt-3">
                    Примечание: Для DOCX и MD всегда используется замена на [censored]
                  </p>
                </div>
              )}
              
              {/* Список отклонённых файлов */}
              {rejectedFiles.length > 0 && (
                <div className="p-4 bg-yellow-900/20 rounded-xl border border-yellow-700/50">
                  <h3 className="text-sm font-semibold text-yellow-300 mb-3 flex items-center gap-2">
                    <span>⚠️</span>
                    <span>Отклонённые файлы ({rejectedFiles.length})</span>
                  </h3>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {rejectedFiles.map((file, index) => (
                      <div key={index} className="text-xs text-yellow-200 bg-yellow-900/30 p-2 rounded">
                        <p className="font-medium">{file.filename}</p>
                        <p className="text-yellow-400 mt-1">{file.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="space-y-4">
              <StatsPanel foundData={foundData} categories={categories} />
              
              {/* Кнопка дозагрузки файлов */}
              <div className="relative">
                <input
                  type="file"
                  accept=".docx,.pdf,.md"
                  multiple
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length > 0) {
                      handleFileUpload(files, true);
                    }
                    // Сбрасываем value, чтобы можно было загрузить тот же файл снова
                    e.target.value = '';
                  }}
                  className="hidden"
                  id="additional-files-input"
                />
                <label
                  htmlFor="additional-files-input"
                  className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2"
                >
                  <span>➕</span>
                  <span>Добавить ещё файлы</span>
                </label>
              </div>
              
              <button
                onClick={handleAnonymize}
                className="w-full py-4 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl transition-all transform hover:scale-[1.02] shadow-lg shadow-red-600/20"
              >
                🔒 Анонимизируй это!
              </button>
              <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-gray-400">
                    <strong className="text-gray-300">Загружено файлов:</strong>{' '}
                    <span className="text-white">{documents.length}</span>
                  </p>
                  {documents.length > 1 && (
                    <span className="text-xs text-blue-400">Разные форматы</span>
                  )}
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {documents.map((doc, index) => {
                    const formatIcon = doc.format === 'pdf' ? '📄' : 
                                      doc.format === 'docx' ? '📝' : '📋';
                    const formatLabel = doc.format.toUpperCase();
                    
                    return (
                      <div key={index} className="flex items-start gap-2 text-xs text-gray-400 border-l-2 border-gray-600 pl-2">
                        <span className="text-sm flex-shrink-0">{formatIcon}</span>
                        <div className="flex-1 min-w-0">
                          <p className="truncate font-medium text-gray-300">{doc.filename}</p>
                          <p className="text-gray-500">
                            {formatLabel} • {doc.text.length.toLocaleString()} симв.
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-sm text-gray-400">
                    <strong className="text-gray-300">Экспорт:</strong>{' '}
                    <span className="text-green-400">Оригинальные форматы</span>
                  </p>
                  {documents.length > 1 && (
                    <p className="text-xs text-gray-500 mt-1">
                      Каждый файл будет экспортирован в своём формате
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {!isLoading && state === 'preview' && documents.length > 0 && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold">Результат анонимизации</h2>
                <p className="text-sm text-gray-400 mt-1">
                  Обработано файлов: <span className="text-white font-semibold">{documents.length}</span>
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleDownloadOriginal}
                  disabled={isExporting}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2 font-semibold"
                >
                  {isExporting ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Экспорт...
                    </>
                  ) : (
                    <>📥 Скачать {documents.length} файл(ов)</>
                  )}
                </button>
                <button
                  onClick={handleDownloadHtml}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                  📄 HTML
                </button>
                <button
                  onClick={handleDownloadReport}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                  📊 Отчёт
                </button>
                <button
                  onClick={() => window.print()}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                  🖨️ Печать
                </button>
              </div>
            </div>
            {documents.map((doc, index) => {
              const docData = foundData.filter(d => doc.text.includes(d.text));
              return (
                <div key={index} className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-300 mb-2">
                    📄 {doc.filename}
                  </h3>
                  <DocumentPreview
                    text={doc.text}
                    foundData={docData}
                    categories={categories}
                    document={doc}
                  />
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

function StepIndicator({ step, label, active, completed }: {
  step: number;
  label: string;
  active: boolean;
  completed: boolean;
}) {
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
      active ? 'bg-blue-600/20 text-blue-400' :
      completed ? 'bg-green-600/20 text-green-400' :
      'bg-gray-800 text-gray-500'
    }`}>
      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
        active ? 'bg-blue-600 text-white' :
        completed ? 'bg-green-600 text-white' :
        'bg-gray-700 text-gray-400'
      }`}>
        {completed ? '✓' : step}
      </span>
      <span className="text-sm">{label}</span>
    </div>
  );
}

export default App;

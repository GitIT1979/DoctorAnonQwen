import { useState, useCallback } from 'react';
import { parseDocument, ParsedDocument } from './utils/documentParser';
import { DataCategory, getCategories } from './utils/dataCategories';
import { findPersonalData, anonymizeText, FoundData, generateReport } from './utils/anonymizer';
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
  const [document, setDocument] = useState<ParsedDocument | null>(null);
  const [categories, setCategories] = useState<DataCategory[]>(getCategories());
  const [foundData, setFoundData] = useState<FoundData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customPatterns, setCustomPatterns] = useState<string[]>([]);

  const handleFileUpload = useCallback(async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const parsed = await parseDocument(file);
      setDocument(parsed);
      
      // Find personal data
      const data = findPersonalData(parsed.text, categories, customPatterns);
      setFoundData(data);
      setState('configure');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при загрузке файла');
    } finally {
      setIsLoading(false);
    }
  }, [categories, customPatterns]);

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

  const handleAnonymize = useCallback(() => {
    const data = findPersonalData(document!.text, categories, customPatterns);
    setFoundData(data);
    setState('preview');
  }, [document, categories, customPatterns]);

  const handleBack = useCallback(() => {
    if (state === 'preview') {
      setState('configure');
    } else if (state === 'configure') {
      setState('upload');
      setDocument(null);
      setFoundData([]);
    }
  }, [state]);

  const handleReset = useCallback(() => {
    setState('upload');
    setDocument(null);
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

  const handleDemo = useCallback(() => {
    const demoText = `ДОГОВОР КУПЛИ-ПРОДАЖИ КВАРТИРЫ № 45/2024

г. Москва                                                                  «15» марта 2024 г.

Гражданка Иванова Мария Петровна, 12.05.1985 года рождения, паспорт серии 4510 № 789234, 
выдан ОВД района Тверской г. Москвы 20.06.2010, код подразделения 770-012, 
зарегистрирована по адресу: г. Москва, ул. Тверская, д. 15, кв. 42,
ИНН 770123456789, СНИЛС 123-456-789 01,
тел.: +7 (495) 123-45-67, email: ivanova.mp@mail.ru,

именуемая в дальнейшем «Продавец», с одной стороны, и

Гражданин Петров Алексей Сергеевич, 03.08.1990 года рождения, паспорт серии 4612 № 345678, 
выдан УФМС по Московской области 15.03.2015, код подразделения 503-045,
зарегистрирован по адресу: Московская область, г. Балашиха, ул. Ленина, д. 28, кв. 156,
ИНН 501234567890, СНИЛС 987-654-321 02,
тел.: +7 (916) 987-65-43, email: petrov.as@gmail.com,
водительское удостоверение 77 12 № 345678,

именуемый в дальнейшем «Покупатель», с другой стороны,

заключили настоящий договор о нижеследующем:

1. ПРЕДМЕТ ДОГОВОРА
1.1. Продавец продаёт, а Покупатель покупает квартиру, расположенную по адресу: 
г. Москва, ул. Тверская, д. 15, кв. 42, кадастровый номер 77:01:0001234:567, 
площадью 68.5 кв. м.

1.2. Квартира принадлежит Продавцу на праве собственности на основании договора 
купли-продажи от 10.01.2018, что подтверждается выпиской из ЕГРН.

2. ЦЕНА ДОГОВОРА И ПОРЯДОК РАСЧЁТОВ
2.1. Стоимость квартиры составляет 12 500 000 (двенадцать миллионов пятьсот тысяч) рублей.
2.2. Покупатель перечисляет денежные средства на расчётный счёт 40817810099910004312 
в ПАО Сбербанк, БИК 044525225, кор/с 30101810400000000225.
2.3. Ежемесячный доход Продавца составляет 185 000 рублей по основному месту работы 
в ООО «ТехноСервис», должность — главный инженер.

3. МЕСТО РАБОТЫ СТОРОН
3.1. Продавец работает в ООО «ТехноСервис» с 2015 года.
3.2. Покупатель работает в ПАО «Газпром нефть» с 2018 года, должность — аналитик.

4. ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ
4.1. Продавец также имеет в собственности автомобиль BMW X5, гос. номер А123БВ777, 
VIN WBAKV210X0L123456.
4.2. Покупатель имеет вклад № 789456123 в Сбербанке на сумму 3 200 000 рублей.
4.3. Летний отпуск 2023 года Продавец провёл в санатории «Сосновый бор» (Краснодарский край).
4.4. На момент заключения договора у Продавца имеется задолженность перед банком в размере 450 000 рублей по кредитному договору № 123/2022.
4.5. Покупатель должен третьему лицу Сидорову В.И. сумму долга 150 000 рублей по расписке от 01.02.2023.`;

    setDocument({
      text: demoText,
      format: 'md',
      filename: 'demo_contract.md',
    });

    const data = findPersonalData(demoText, categories, customPatterns);
    setFoundData(data);
    setState('configure');
  }, [categories, customPatterns]);

  const [isExporting, setIsExporting] = useState(false);

  const handleDownloadOriginal = useCallback(async () => {
    if (!document) return;
    setIsExporting(true);
    try {
      const blob = await exportDocument(document, foundData, categories);
      const ext = document.filename.split('.').pop() || 'docx';
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = `anonymized_${document.filename}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при экспорте');
    } finally {
      setIsExporting(false);
    }
  }, [document, foundData, categories]);

  const handleDownloadHtml = useCallback(() => {
    if (!document) return;
    
    const anonymizedContent = anonymizeText(document.text, foundData, categories);
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Анонимизированный документ - ${document.filename}</title>
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
  <pre>${anonymizedContent}</pre>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `anonymized_${document.filename}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [document, foundData, categories]);

  const handleDownloadReport = useCallback(() => {
    if (!document) return;
    const report = generateReport(foundData, categories);
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `report_${document.filename}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [document, foundData, categories]);

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
          <FileUpload onFileUpload={handleFileUpload} onDemo={handleDemo} />
        )}

        {!isLoading && state === 'configure' && document && (
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
            </div>
            <div className="space-y-4">
              <StatsPanel foundData={foundData} categories={categories} />
              <button
                onClick={handleAnonymize}
                className="w-full py-4 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl transition-all transform hover:scale-[1.02] shadow-lg shadow-red-600/20"
              >
                🔒 Анонимизировать документ
              </button>
              <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                <p className="text-sm text-gray-400">
                  <strong className="text-gray-300">Файл:</strong> {document.filename}
                </p>
                <p className="text-sm text-gray-400 mt-1">
                  <strong className="text-gray-300">Формат:</strong>{' '}
                  <span className="text-white">
                    {document.format === 'image' ? 'Изображение (OCR)' : document.format.toUpperCase()}
                  </span>
                </p>
                <p className="text-sm text-gray-400 mt-1">
                  <strong className="text-gray-300">Символов:</strong> {document.text.length.toLocaleString()}
                </p>
                {document.format === 'image' && document.ocrWords && (
                  <p className="text-sm text-gray-400 mt-1">
                    <strong className="text-gray-300">Распознано слов:</strong>{' '}
                    <span className="text-blue-400">{document.ocrWords.length}</span>
                  </p>
                )}
                {document.format === 'image' && document.imageData && (
                  <div className="mt-2">
                    <img 
                      src={document.imageData} 
                      alt="Preview" 
                      className="max-h-32 rounded-lg border border-gray-600"
                    />
                  </div>
                )}
                <p className="text-sm text-gray-400 mt-1">
                  <strong className="text-gray-300">Экспорт:</strong>{' '}
                  <span className="text-green-400">{document.format === 'image' ? document.filename.split('.').pop()?.toUpperCase() : document.format.toUpperCase()}</span>
                </p>
              </div>
            </div>
          </div>
        )}

        {!isLoading && state === 'preview' && document && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold">Результат анонимизации</h2>
                <p className="text-sm text-gray-400 mt-1">
                  Формат экспорта: <span className="text-white font-semibold">{document.format.toUpperCase()}</span>
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
                    <>📥 Скачать {document.format.toUpperCase()}</>
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
            <DocumentPreview
              text={document.text}
              foundData={foundData}
              categories={categories}
              document={document}
            />
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

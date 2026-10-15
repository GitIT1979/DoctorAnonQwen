import { useCallback, useState } from 'react';

interface FileUploadProps {
  onFileUpload: (files: File[]) => void;
}

export default function FileUpload({ onFileUpload }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      // Limit to 50 files
      const limitedFiles = files.slice(0, 50);
      onFileUpload(limitedFiles);
    }
  }, [onFileUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      // Limit to 50 files
      const limitedFiles = files.slice(0, 50);
      onFileUpload(limitedFiles);
    }
  }, [onFileUpload]);

  return (
    <div className="max-w-3xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-full text-emerald-400 text-sm mb-6">
          <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
          СЕКРЕТНО — Анонимизация документов
        </div>
        <h2 className="text-4xl font-bold mb-4 bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
          Защитите персональные данные
        </h2>
        <p className="text-gray-400 text-lg max-w-xl mx-auto">
          Загрузите документ, и система автоматически найдёт и скроет персональные данные
        </p>
      </div>

      {/* Upload Area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer ${
          isDragOver
            ? 'border-blue-500 bg-blue-500/10 scale-[1.02]'
            : 'border-gray-600 hover:border-gray-500 bg-gray-800/30 hover:bg-gray-800/50'
        }`}
      >
        <input
          type="file"
          accept=".docx,.pdf,.md"
          multiple
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        
        <div className="space-y-4">
          <div className="text-6xl">📁</div>
          <div>
            <p className="text-xl font-semibold text-white mb-2">
              Перетащите файлы сюда
            </p>
            <p className="text-gray-400">
              или нажмите для выбора файлов (до 50 файлов)
            </p>
            <p className="text-sm text-blue-400 mt-2">
              ✨ Можно загружать файлы разных форматов одновременно
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
            <span className="px-3 py-1.5 bg-sky-500/20 text-sky-400 rounded-lg text-sm font-medium">
              .DOCX
            </span>
            <span className="px-3 py-1.5 bg-cyan-500/20 text-cyan-400 rounded-lg text-sm font-medium">
              .PDF
            </span>
            <span className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded-lg text-sm font-medium">
              .MD
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Поддерживаются только текстовые форматы. PDF должен содержать текстовый слой.
          </p>
        </div>
      </div>

      {/* Info Section */}
      <div className="mt-10 p-6 bg-gray-800/50 rounded-xl border border-gray-700">
        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <span>📋</span> Какие данные скрываются?
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-400">
          <InfoItem text="ФИО (фамилия, имя, отчество)" />
          <InfoItem text="Паспортные данные" />
          <InfoItem text="Водительское удостоверение" />
          <InfoItem text="Адреса проживания" />
          <InfoItem text="Недвижимое имущество" />
          <InfoItem text="ИНН, СНИЛС" />
          <InfoItem text="Банковские счета и карты" />
          <InfoItem text="Финансовое состояние" />
          <InfoItem text="Место работы и должности" />
          <InfoItem text="Телефоны и email" />
          <InfoItem text="Дата рождения" />
          <InfoItem text="Места отдыха, транспортные средства" />
        </div>
      </div>
    </div>
  );
}

function InfoItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-1.5 h-1.5 bg-red-500 rounded-full flex-shrink-0" />
      <span>{text}</span>
    </div>
  );
}

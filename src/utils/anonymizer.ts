import { DataCategory } from './dataCategories';

export interface FoundData {
  id: string;
  categoryId: string;
  categoryName: string;
  text: string;
  startIndex: number;
  endIndex: number;
  enabled: boolean;
}

export interface AnonymizationResult {
  originalText: string;
  anonymizedHtml: string;
  foundData: FoundData[];
  totalRedacted: number;
}

export function findPersonalData(
  text: string,
  categories: DataCategory[],
  customPatterns?: string[]
): FoundData[] {
  const foundData: FoundData[] = [];
  const seenRanges: Array<{ start: number; end: number }> = [];

  // Process custom patterns first
  if (customPatterns && customPatterns.length > 0) {
    for (const pattern of customPatterns) {
      const escapedPattern = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(escapedPattern, 'gi');
      let match;

      while ((match = regex.exec(text)) !== null) {
        const startIndex = match.index;
        const endIndex = startIndex + match[0].length;

        const overlaps = seenRanges.some(
          (range) =>
            (startIndex >= range.start && startIndex < range.end) ||
            (endIndex > range.start && endIndex <= range.end)
        );

        if (!overlaps && match[0].trim().length > 0) {
          seenRanges.push({ start: startIndex, end: endIndex });
          foundData.push({
            id: `data-custom-${foundData.length}`,
            categoryId: 'custom',
            categoryName: 'Пользовательский паттерн',
            text: match[0],
            startIndex,
            endIndex,
            enabled: true,
          });
        }
      }
    }
  }

  for (const category of categories) {
    for (const pattern of category.patterns) {
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;

      while ((match = regex.exec(text)) !== null) {
        const startIndex = match.index;
        const endIndex = startIndex + match[0].length;

        // Check if this range overlaps with already found data
        const overlaps = seenRanges.some(
          (range) =>
            (startIndex >= range.start && startIndex < range.end) ||
            (endIndex > range.start && endIndex <= range.end)
        );

        if (!overlaps && match[0].trim().length > 2) {
          seenRanges.push({ start: startIndex, end: endIndex });
          foundData.push({
            id: `data-${foundData.length}`,
            categoryId: category.id,
            categoryName: category.name,
            text: match[0],
            startIndex,
            endIndex,
            enabled: category.enabled,
          });
        }
      }
    }
  }

  // Sort by position
  foundData.sort((a, b) => a.startIndex - b.startIndex);
  return foundData;
}

export function anonymizeText(
  text: string,
  foundData: FoundData[],
  categories: DataCategory[]
): string {
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );

  // Filter data by enabled categories (custom is always enabled)
  const dataToRedact = foundData.filter((d) =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );

  if (dataToRedact.length === 0) return text;

  // Build result by replacing found data with redaction blocks
  let result = '';
  let lastIndex = 0;

  for (const data of dataToRedact) {
    result += escapeHtml(text.slice(lastIndex, data.startIndex));
    result += `<span class="redacted" title="${data.categoryName}">${'█'.repeat(Math.max(data.text.length, 3))}</span>`;
    lastIndex = data.endIndex;
  }

  result += escapeHtml(text.slice(lastIndex));
  return result;
}

export function generateAnonymizedHtml(
  text: string,
  foundData: FoundData[],
  categories: DataCategory[]
): string {
  const anonymizedContent = anonymizeText(text, foundData, categories);

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Анонимизированный документ</title>
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
    .redacted:hover {
      background-color: #333;
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
  <pre>${anonymizedContent}</pre>
</body>
</html>`;
}

export function generateReport(foundData: FoundData[], categories: DataCategory[]): string {
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );

  const grouped: Record<string, FoundData[]> = {};
  
  for (const data of foundData) {
    if (data.categoryId === 'custom' || enabledCategories.has(data.categoryId)) {
      if (!grouped[data.categoryId]) {
        grouped[data.categoryId] = [];
      }
      grouped[data.categoryId].push(data);
    }
  }

  let report = '=== ОТЧЁТ ОБ АНОНИМИЗАЦИИ ===\n\n';
  report += `Всего найдено персональных данных: ${foundData.length}\n`;
  report += `Будет скрыто: ${Object.values(grouped).reduce((sum, arr) => sum + arr.length, 0)}\n\n`;

  for (const category of categories) {
    if (grouped[category.id]) {
      report += `--- ${category.icon} ${category.name} ---\n`;
      report += `Найдено: ${grouped[category.id].length} фрагмент(ов)\n`;
      for (const data of grouped[category.id]) {
        const preview = data.text.length > 50 ? data.text.slice(0, 50) + '...' : data.text;
        report += `  • "${preview}"\n`;
      }
      report += '\n';
    }
  }

  return report;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

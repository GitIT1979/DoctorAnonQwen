import { PDFDocument, rgb, degrees } from 'pdf-lib';
import JSZip from 'jszip';
import { ParsedDocument, PdfPageInfo, PdfTextItem } from './documentParser';
import { FoundData, AnonymizationMode } from './anonymizer';
import { DataCategory } from './dataCategories';

export async function exportDocument(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  switch (document.format) {
    case 'pdf':
      return exportPdfWithFormatting(document, foundData, categories, mode);
    case 'docx':
      return exportDocxWithFormatting(document, foundData, categories);
    case 'md':
      return exportMarkdownWithFormatting(document, foundData, categories);
    default:
      throw new Error(`Неподдерживаемый формат: ${document.format}`);
  }
}

async function exportPdfWithFormatting(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode
): Promise<Blob> {
  if (!document.originalData || !document.pdfPageInfo) {
    throw new Error('Оригинальные данные PDF недоступны');
  }

  // Загружаем оригинальный PDF
  const pdfDoc = await PDFDocument.load(document.originalData);
  const pages = pdfDoc.getPages();

  // Получаем список категорий для скрытия
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );

  const dataToRedact = foundData.filter(d =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );

  // Для каждого найденного фрагмента находим его позицию в PDF
  for (const data of dataToRedact) {
    const dataText = data.text;
    
    // Ищем этот текст в pageInfo
    for (let pageIndex = 0; pageIndex < document.pdfPageInfo.length; pageIndex++) {
      const pageInfo = document.pdfPageInfo[pageIndex];
      const page = pages[pageIndex];
      
      // Ищем текстовые элементы, которые соответствуют найденным данным
      const matches = findTextMatchesInPage(dataText, pageInfo.items);
      
      for (const match of matches) {
        if (mode === 'remove') {
          // Для режима удаления просто закрашиваем белым
          page.drawRectangle({
            x: match.x,
            y: match.y,
            width: match.width,
            height: match.height,
            color: rgb(1, 1, 1),
          });
        } else {
          // Для режима закрашивания рисуем чёрный прямоугольник
          page.drawRectangle({
            x: match.x,
            y: match.y,
            width: match.width,
            height: match.height,
            color: rgb(0, 0, 0),
          });
        }
      }
    }
  }

  const pdfBytes = await pdfDoc.save();
  return new Blob([pdfBytes as unknown as BlobPart], { type: 'application/pdf' });
}

function findTextMatchesInPage(
  searchText: string,
  items: PdfTextItem[]
): Array<{ x: number; y: number; width: number; height: number }> {
  const matches: Array<{ x: number; y: number; width: number; height: number }> = [];
  
  // Простой поиск: ищем последовательность элементов, которые вместе образуют searchText
  const normalizedSearch = searchText.toLowerCase().trim();
  
  for (let i = 0; i < items.length; i++) {
    // Пробуем собрать текст начиная с этого элемента
    let accumulatedText = '';
    let startX = items[i].transform[4];
    let startY = items[i].transform[5];
    let totalWidth = 0;
    let maxHeight = 0;
    
    for (let j = i; j < items.length && j < i + 50; j++) {
      accumulatedText += items[j].str;
      totalWidth += items[j].width;
      maxHeight = Math.max(maxHeight, items[j].height);
      
      if (accumulatedText.toLowerCase().includes(normalizedSearch)) {
        matches.push({
          x: startX,
          y: startY,
          width: totalWidth,
          height: maxHeight,
        });
        break;
      }
      
      // Если текст стал длиннее поиска, прекращаем
      if (accumulatedText.length > normalizedSearch.length * 2) {
        break;
      }
    }
  }
  
  return matches;
}

async function exportDocxWithFormatting(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[]
): Promise<Blob> {
  if (!document.originalData) {
    throw new Error('Оригинальные данные DOCX недоступны');
  }

  // Распаковываем DOCX
  const zip = await JSZip.loadAsync(document.originalData);
  
  // Получаем список категорий для скрытия
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );

  const dataToRedact = foundData.filter(d =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );

  // Обрабатываем document.xml
  const documentXml = await zip.file('word/document.xml')?.async('string');
  if (!documentXml) {
    throw new Error('Не удалось найти word/document.xml в DOCX');
  }

  // Заменяем персональные данные на [censored] в XML
  let modifiedXml = documentXml;
  
  for (const data of dataToRedact) {
    const escapedText = escapeXml(data.text);
    const replacement = '[censored]';
    
    // Заменяем текст в XML, сохраняя теги форматирования
    modifiedXml = replaceTextInXml(modifiedXml, escapedText, replacement);
  }

  // Обновляем document.xml в архиве
  zip.file('word/document.xml', modifiedXml);

  // Генерируем новый DOCX
  const blob = await zip.generateAsync({ type: 'blob' });
  return blob;
}

function escapeXml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function replaceTextInXml(xml: string, searchText: string, replacement: string): string {
  // Ищем текст между тегами <w:t> и заменяем его
  // Это упрощённая версия, которая работает для простых случаев
  const regex = new RegExp(
    `(<w:t[^>]*>)([^<]*?${escapeRegex(searchText)}[^<]*?)(</w:t>)`,
    'g'
  );
  
  return xml.replace(regex, (match, openTag, content, closeTag) => {
    // Заменяем найденный текст на [censored]
    const newContent = content.replace(new RegExp(escapeRegex(searchText), 'g'), replacement);
    return `${openTag}${newContent}${closeTag}`;
  });
}

function escapeRegex(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function exportMarkdownWithFormatting(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[]
): Promise<Blob> {
  // Для Markdown просто заменяем текст, так как форматирование хранится в самом тексте
  let text = document.text;
  
  // Получаем список категорий для скрытия
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );

  const dataToRedact = foundData.filter(d =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );

  // Заменяем найденные данные на [censored]
  // Сортируем по позиции, чтобы заменять с конца
  const sortedData = [...dataToRedact].sort((a, b) => b.startIndex - a.startIndex);
  
  for (const data of sortedData) {
    text = text.slice(0, data.startIndex) + '[censored]' + text.slice(data.endIndex);
  }

  return new Blob([text], { type: 'text/markdown;charset=utf-8' });
}

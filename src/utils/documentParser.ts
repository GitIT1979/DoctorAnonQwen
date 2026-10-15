import mammoth from 'mammoth';
import * as pdfjsLib from 'pdfjs-dist';

// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js`;

export interface ParsedDocument {
  text: string;
  pages?: string[];
  format: 'docx' | 'pdf' | 'md';
  filename: string;
  // Original file data for preserving formatting
  originalData?: ArrayBuffer;
  // For PDF: store page info for redaction
  pdfPageInfo?: PdfPageInfo[];
}

export interface PdfPageInfo {
  width: number;
  height: number;
  items: PdfTextItem[];
}

export interface PdfTextItem {
  str: string;
  transform: number[]; // [scaleX, skewY, skewX, scaleY, translateX, translateY]
  width: number;
  height: number;
}

const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'tiff', 'tif'];

export function isImageFile(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return IMAGE_EXTENSIONS.includes(ext);
}

export async function parseDocument(file: File): Promise<ParsedDocument> {
  const extension = file.name.split('.').pop()?.toLowerCase();
  
  // Проверка размера файла (максимум 50 MB)
  const MAX_SIZE = 50 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    throw new Error('Файл слишком большой (максимум 50 MB)');
  }
  
  // Отклоняем изображения с понятным сообщением
  if (extension && IMAGE_EXTENSIONS.includes(extension)) {
    throw new Error('Прошу сперва конвертировать в форматы docx, MD или читаемый PDF');
  }
  
  switch (extension) {
    case 'docx':
      return parseDocx(file);
    case 'pdf':
      return parsePdf(file);
    case 'md':
      return parseMarkdown(file);
    default:
      throw new Error(`Прошу сперва конвертировать в форматы docx, MD или читаемый PDF`);
  }
}

async function parseDocx(file: File): Promise<ParsedDocument> {
  const arrayBuffer = await file.arrayBuffer();
  const result = await mammoth.extractRawText({ arrayBuffer });
  
  return {
    text: result.value,
    format: 'docx',
    filename: file.name,
    originalData: arrayBuffer,
  };
}

async function parsePdf(file: File): Promise<ParsedDocument> {
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  
  // Ограничение на количество страниц (максимум 100)
  const MAX_PAGES = 100;
  const numPages = Math.min(pdf.numPages, MAX_PAGES);
  
  const pages: string[] = [];
  const pdfPageInfo: PdfPageInfo[] = [];
  let fullText = '';
  
  for (let i = 1; i <= numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 1.0 });
    const textContent = await page.getTextContent();
    
    const items: PdfTextItem[] = textContent.items
      .filter((item: any) => item.str)
      .map((item: any) => ({
        str: item.str,
        transform: item.transform,
        width: item.width,
        height: item.height || (item.transform ? item.transform[0] : 12),
      }));
    
    pdfPageInfo.push({
      width: viewport.width,
      height: viewport.height,
      items,
    });
    
    const pageText = items.map(item => item.str).join(' ');
    pages.push(pageText);
    fullText += pageText + '\n\n';
  }
  
  return {
    text: fullText.trim(),
    pages,
    format: 'pdf',
    filename: file.name,
    originalData: arrayBuffer,
    pdfPageInfo,
  };
}

async function parseMarkdown(file: File): Promise<ParsedDocument> {
  const text = await file.text();
  
  return {
    text,
    format: 'md',
    filename: file.name,
  };
}

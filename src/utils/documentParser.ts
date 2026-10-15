import mammoth from 'mammoth';
import * as pdfjsLib from 'pdfjs-dist';
import Tesseract from 'tesseract.js';

// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js`;

export interface ParsedDocument {
  text: string;
  pages?: string[];
  format: 'docx' | 'pdf' | 'md' | 'image';
  filename: string;
  // For images: store the original image data and OCR positions
  imageData?: string; // base64 data URL
  imageWidth?: number;
  imageHeight?: number;
  ocrWords?: OcrWord[];
  // For PDF: store page info for redaction
  pdfPageInfo?: PdfPageInfo[];
}

export interface OcrWord {
  text: string;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  confidence: number;
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
  
  if (extension && IMAGE_EXTENSIONS.includes(extension)) {
    return parseImage(file);
  }
  
  switch (extension) {
    case 'docx':
      return parseDocx(file);
    case 'pdf':
      return parsePdf(file);
    case 'md':
      return parseMarkdown(file);
    default:
      throw new Error(`Неподдерживаемый формат файла: ${extension}`);
  }
}

async function parseDocx(file: File): Promise<ParsedDocument> {
  const arrayBuffer = await file.arrayBuffer();
  const result = await mammoth.extractRawText({ arrayBuffer });
  
  return {
    text: result.value,
    format: 'docx',
    filename: file.name,
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

async function parseImage(file: File): Promise<ParsedDocument> {
  // Read image as base64
  const imageData = await fileToBase64(file);
  
  // Get image dimensions
  const { width, height } = await getImageDimensions(imageData);
  
  // Ограничение на размер изображения (максимум 4000x4000)
  const MAX_DIMENSION = 4000;
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    throw new Error(`Изображение слишком большое (${width}x${height}). Максимум ${MAX_DIMENSION}x${MAX_DIMENSION}`);
  }
  
  // Таймаут для OCR (90 секунд)
  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error('Превышено время распознавания текста (90 секунд)')), 90000);
  });
  
  const ocrPromise = Tesseract.recognize(imageData, 'rus+eng', {
    logger: (m: any) => {
      if (m.status === 'recognizing text') {
        console.log(`OCR progress: ${Math.round(m.progress * 100)}%`);
      }
    },
  });
  
  const result = await Promise.race([ocrPromise, timeoutPromise]);
  
  // Extract words with bounding boxes
  const data = result.data as any;
  const ocrWords: OcrWord[] = (data.words || []).map((word: any) => ({
    text: word.text,
    bbox: {
      x0: word.bbox.x0,
      y0: word.bbox.y0,
      x1: word.bbox.x1,
      y1: word.bbox.y1,
    },
    confidence: word.confidence,
  }));
  
  // Build text from words
  const text = result.data.text;
  
  return {
    text,
    format: 'image',
    filename: file.name,
    imageData,
    imageWidth: width,
    imageHeight: height,
    ocrWords,
  };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function getImageDimensions(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.width, height: img.height });
    img.onerror = reject;
    img.src = dataUrl;
  });
}

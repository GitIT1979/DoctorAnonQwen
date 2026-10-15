import mammoth from 'mammoth';
import * as pdfjsLib from 'pdfjs-dist';

// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js`;

export interface ParsedDocument {
  text: string;
  pages?: string[];
  format: 'docx' | 'pdf' | 'md';
  filename: string;
}

export async function parseDocument(file: File): Promise<ParsedDocument> {
  const extension = file.name.split('.').pop()?.toLowerCase();
  
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
  
  const pages: string[] = [];
  let fullText = '';
  
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const textContent = await page.getTextContent();
    const pageText = textContent.items
      .map((item: any) => item.str)
      .join(' ');
    pages.push(pageText);
    fullText += pageText + '\n\n';
  }
  
  return {
    text: fullText.trim(),
    pages,
    format: 'pdf',
    filename: file.name,
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

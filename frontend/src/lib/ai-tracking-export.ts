import type { AiGenerationTrackingItem } from './api-client.ts';

type JsonRecord = Record<string, unknown>;

export interface AiTrackingExportRow {
  id: number;
  created_at: string;
  user_id: string;
  country_id: string;
  app_version: string;
  prompt: string;
  for_you_prompt: string;
  style: string;
  status: string;
  duration_seconds: number | '';
  reference_file_name: string;
  reference_content_type: string;
  provider: string;
  fallback_used: boolean | '';
  output_image_urls: string;
  error_code: string;
  error_status: number | string | '';
  error_message: string;
}

const AI_TRACKING_EXPORT_HEADERS: Array<keyof AiTrackingExportRow> = [
  'id',
  'created_at',
  'user_id',
  'country_id',
  'app_version',
  'prompt',
  'for_you_prompt',
  'style',
  'status',
  'duration_seconds',
  'reference_file_name',
  'reference_content_type',
  'provider',
  'fallback_used',
  'output_image_urls',
  'error_code',
  'error_status',
  'error_message',
];

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const readString = (record: JsonRecord | null, key: string): string => {
  const value = record?.[key];
  return typeof value === 'string' ? value : '';
};

const readBooleanOrEmpty = (record: JsonRecord | null, key: string): boolean | '' => {
  const value = record?.[key];
  return typeof value === 'boolean' ? value : '';
};

const readNumberOrStringOrEmpty = (record: JsonRecord | null, key: string): number | string | '' => {
  const value = record?.[key];
  if (typeof value === 'number' || typeof value === 'string') {
    return value;
  }
  return '';
};

const readImageUrls = (record: JsonRecord | null): string => {
  const images = record?.images;
  if (!Array.isArray(images)) {
    return '';
  }

  return images
    .map((image) => (isRecord(image) && typeof image.imageUrl === 'string' ? image.imageUrl : ''))
    .filter(Boolean)
    .join('\n');
};

export function parseJsonString<T>(value: string | null): T | null {
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function formatCsvValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return '';
  }

  const stringValue = String(value);
  if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }

  return stringValue;
}

export function buildAiTrackingExportRow(item: AiGenerationTrackingItem): AiTrackingExportRow {
  const imageReference = parseJsonString<unknown>(item.imageReference);
  const output = parseJsonString<unknown>(item.output);

  const imageReferenceRecord = isRecord(imageReference) ? imageReference : null;
  const outputRecord = isRecord(output) ? output : null;

  return {
    id: item.id,
    created_at: item.createdAt,
    user_id: item.userId ?? '',
    country_id: item.countryId ?? '',
    app_version: item.appVersion ?? '',
    prompt: item.prompt,
    for_you_prompt: item.forYouPrompt ?? '',
    style: item.style ?? '',
    status: item.status,
    duration_seconds: Number.isFinite(item.durationSeconds) ? item.durationSeconds : '',
    reference_file_name: readString(imageReferenceRecord, 'fileName'),
    reference_content_type: readString(imageReferenceRecord, 'contentType'),
    provider: item.status === 'SUCCESS' ? readString(outputRecord, 'provider') : '',
    fallback_used: item.status === 'SUCCESS' ? readBooleanOrEmpty(outputRecord, 'fallbackUsed') : '',
    output_image_urls: item.status === 'SUCCESS' ? readImageUrls(outputRecord) : '',
    error_code: item.status === 'FAIL' ? readString(outputRecord, 'code') : '',
    error_status: item.status === 'FAIL' ? readNumberOrStringOrEmpty(outputRecord, 'status') : '',
    error_message: item.status === 'FAIL' ? readString(outputRecord, 'message') : '',
  };
}

export function buildAiTrackingCsv(items: AiGenerationTrackingItem[]): string {
  const rows = items.map((item) => buildAiTrackingExportRow(item));

  return [
    '\ufeff' + AI_TRACKING_EXPORT_HEADERS.join(','),
    ...rows.map((row) => AI_TRACKING_EXPORT_HEADERS.map((header) => formatCsvValue(row[header])).join(',')),
  ].join('\n');
}

export function getAiTrackingExportFilename(now = new Date()): string {
  return `ai-tracking-${now.toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
}

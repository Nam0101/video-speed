import test from 'node:test';
import assert from 'node:assert/strict';

import type { AiGenerationTrackingItem } from './api-client.ts';
import {
  buildAiTrackingCsv,
  buildAiTrackingExportRow,
  getAiTrackingExportFilename,
  parseJsonString,
} from './ai-tracking-export.ts';

const baseItem: AiGenerationTrackingItem = {
  id: 42,
  createdAt: '2026-04-22T10:15:30.000Z',
  appVersion: '2.4.1',
  userId: 'user-123',
  countryId: 'VN',
  prompt: 'Create "cinematic", moody scene',
  style: 'cinematic',
  forYouPrompt: 'Extra lighting',
  imageReference: JSON.stringify({
    fileName: 'portrait.png',
    contentType: 'image/png',
  }),
  output: JSON.stringify({
    provider: 'openai',
    fallbackUsed: true,
    images: [
      { imageUrl: 'https://cdn.example.com/1.png' },
      { imageUrl: 'https://cdn.example.com/2.png' },
    ],
  }),
  durationSeconds: 12.34,
  status: 'SUCCESS',
};

test('parseJsonString returns null for invalid json', () => {
  assert.equal(parseJsonString('not-json'), null);
});

test('buildAiTrackingExportRow flattens successful ai generation output', () => {
  const row = buildAiTrackingExportRow(baseItem);

  assert.deepEqual(row, {
    id: 42,
    created_at: '2026-04-22T10:15:30.000Z',
    user_id: 'user-123',
    country_id: 'VN',
    app_version: '2.4.1',
    prompt: 'Create "cinematic", moody scene',
    for_you_prompt: 'Extra lighting',
    style: 'cinematic',
    status: 'SUCCESS',
    duration_seconds: 12.34,
    reference_file_name: 'portrait.png',
    reference_content_type: 'image/png',
    provider: 'openai',
    fallback_used: true,
    output_image_urls: 'https://cdn.example.com/1.png\nhttps://cdn.example.com/2.png',
    error_code: '',
    error_status: '',
    error_message: '',
  });
});

test('buildAiTrackingExportRow handles failed records and malformed json safely', () => {
  const row = buildAiTrackingExportRow({
    ...baseItem,
    id: 99,
    imageReference: '{',
    output: JSON.stringify({
      code: 'bad_request',
      status: 400,
      message: 'Prompt is invalid',
    }),
    status: 'FAIL',
  });

  assert.deepEqual(row, {
    id: 99,
    created_at: '2026-04-22T10:15:30.000Z',
    user_id: 'user-123',
    country_id: 'VN',
    app_version: '2.4.1',
    prompt: 'Create "cinematic", moody scene',
    for_you_prompt: 'Extra lighting',
    style: 'cinematic',
    status: 'FAIL',
    duration_seconds: 12.34,
    reference_file_name: '',
    reference_content_type: '',
    provider: '',
    fallback_used: '',
    output_image_urls: '',
    error_code: 'bad_request',
    error_status: 400,
    error_message: 'Prompt is invalid',
  });
});

test('buildAiTrackingCsv emits utf-8 bom, header row, and escaped values', () => {
  const csv = buildAiTrackingCsv([baseItem]);

  assert.ok(csv.startsWith('\ufeffid,created_at,user_id,country_id,app_version,prompt,for_you_prompt,style,status,duration_seconds,reference_file_name,reference_content_type,provider,fallback_used,output_image_urls,error_code,error_status,error_message'));
  assert.match(csv, /"Create ""cinematic"", moody scene"/);
  assert.match(csv, /"https:\/\/cdn\.example\.com\/1\.png\nhttps:\/\/cdn\.example\.com\/2\.png"/);
});

test('getAiTrackingExportFilename produces a stable csv filename', () => {
  const filename = getAiTrackingExportFilename(new Date('2026-04-22T17:45:30.000Z'));
  assert.equal(filename, 'ai-tracking-2026-04-22-17-45-30.csv');
});

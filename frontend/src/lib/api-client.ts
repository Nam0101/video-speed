const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const ANALYTICS_BASE_URL =
    (process.env.NEXT_PUBLIC_ANALYTICS_URL || 'https://plant.cemsoftwareltd.com').replace(
        /\/$/,
        ''
    );

export interface ConversionResponse {
    file_id?: string;
    file_url?: string;
    message?: string;
}

export interface TrackingItem {
    date: string;
    country_code: string;
    app_version: string;
    device_id: string;
    function: string;
    image_url: string;
    response_time_seconds: number | null;
    is_plant_healthy: boolean | null;
    result: string;
}

export interface TrackingResponse {
    data: TrackingItem[];
    pagination: {
        page: number;
        limit: number;
        total: number;
        total_pages: number;
    };
}

export interface Log {
    timestamp: string;
    eventName: string;
    deviceName: string;
    versionCode: string;
    params: Record<string, any>;
}

export interface AnalyticsStats {
    total_requests: number;
    avg_response_time: number;
    function_distribution: Record<string, number>;
    health_distribution: Record<string, number>;
    country_distribution: Record<string, number>;
    version_distribution: Record<string, number>;
}

export interface FailedFileInfo {
    file: string;
    error: string;
}

export interface BatchToWebpResult {
    success: boolean;
    blob: Blob | null;
    successfulCount: number;
    successfulFiles?: string[];
    failedCount: number;
    failedFiles: FailedFileInfo[];
    message?: string;
    error?: string;
}

class APIClient {
    private baseURL: string;

    constructor() {
        this.baseURL = API_BASE_URL;
    }

    async uploadVideo(file: File): Promise<ConversionResponse> {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseURL}/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.json();
    }

    async convertFPS(fileId: string, fps: number): Promise<Blob> {
        const response = await fetch(`${this.baseURL}/convert`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_id: fileId, fps }),
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async exportVideo(fileId: string, fps: number, duration: number): Promise<Blob> {
        const response = await fetch(`${this.baseURL}/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_id: fileId, fps, duration }),
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async convertImageToWebP(file: File): Promise<Blob> {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseURL}/png-to-webp`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async convertGifToWebP(file: File, fps: number, width?: number, duration?: number): Promise<Blob> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('fps', fps.toString());
        if (width) formData.append('width', width.toString());
        if (duration) formData.append('duration', duration.toString());

        const response = await fetch(`${this.baseURL}/gif-to-webp`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async convertMp4ToAnimatedWebP(
        file: File,
        fps: number,
        width?: number,
        duration?: number
    ): Promise<Blob> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('fps', fps.toString());
        if (width) formData.append('width', width.toString());
        if (duration) formData.append('duration', duration.toString());

        const response = await fetch(`${this.baseURL}/mp4-to-animated-webp`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async convertWebmToGif(file: File, fps: number, width?: number): Promise<Blob> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('fps', fps.toString());
        if (width) formData.append('width', width.toString());

        const response = await fetch(`${this.baseURL}/webm-to-gif`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async imagesToAnimatedWebP(files: File[], fps: number, width?: number): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        formData.append('fps', fps.toString());
        if (width) formData.append('width', width.toString());

        const response = await fetch(`${this.baseURL}/images-to-animated-webp`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async imagesToWebPZip(files: File[]): Promise<BatchToWebpResult> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));

        const response = await fetch(`${this.baseURL}/images-to-webp-zip`, {
            method: 'POST',
            body: formData,
        });

        const contentType = response.headers.get('content-type') || '';

        // Check if response is JSON (partial success or all failed)
        if (contentType.includes('application/json')) {
            const jsonData = await response.json();

            if (!response.ok) {
                // All files failed
                return {
                    success: false,
                    blob: null,
                    successfulCount: 0,
                    failedCount: jsonData.failed_count || 0,
                    failedFiles: jsonData.failed_files || [],
                    error: jsonData.error || 'Có lỗi xảy ra',
                };
            }

            // Partial success - need to download from URL
            const downloadUrl = `${this.baseURL}${jsonData.download_url}`;
            const downloadResponse = await fetch(downloadUrl);

            if (!downloadResponse.ok) {
                throw new Error('Không thể tải file ZIP');
            }

            const blob = await downloadResponse.blob();
            return {
                success: true,
                blob,
                successfulCount: jsonData.successful_count || 0,
                successfulFiles: jsonData.successful_files || [],
                failedCount: jsonData.failed_count || 0,
                failedFiles: jsonData.failed_files || [],
                message: jsonData.message,
            };
        }

        // Full success - direct blob response
        if (!response.ok) {
            throw new Error(await response.text());
        }

        const blob = await response.blob();
        return {
            success: true,
            blob,
            successfulCount: files.length,
            failedCount: 0,
            failedFiles: [],
        };
    }

    async imagesConvertZip(
        files: File[],
        options: {
            format: 'webp' | 'png' | 'jpg';
            width?: number;
            quality?: number;
            lossless?: boolean;
        }
    ): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        formData.append('format', options.format);
        if (options.width) formData.append('width', options.width.toString());
        if (options.quality) formData.append('quality', options.quality.toString());
        if (typeof options.lossless === 'boolean') {
            formData.append('lossless', options.lossless ? '1' : '0');
        }

        const response = await fetch(`${this.baseURL}/images-convert-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async tgsToGifZip(
        files: File[],
        options: {
            width?: number;
            quality?: number;
            fps?: number;
        }
    ): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        if (options.width) formData.append('width', options.width.toString());
        if (options.quality) formData.append('quality', options.quality.toString());
        if (options.fps) formData.append('fps', options.fps.toString());

        const response = await fetch(`${this.baseURL}/tgs-to-gif-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async filesToTgsZip(
        files: File[],
        options: {
            width?: number;
            fps?: number;
        }
    ): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        if (options.width) formData.append('width', options.width.toString());
        if (options.fps) formData.append('fps', options.fps.toString());

        const response = await fetch(`${this.baseURL}/files-to-tgs-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async removeBackground(file: File): Promise<Blob> {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseURL}/remove-background`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async removeBackgroundZip(files: File[]): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));

        const response = await fetch(`${this.baseURL}/remove-background-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async batchAnimatedResizeZip(
        files: File[],
        options: {
            width?: number;
            height?: number;
            targetSizeKb?: number;
            quality?: number;
        }
    ): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        if (options.width) formData.append('width', options.width.toString());
        if (options.height) formData.append('height', options.height.toString());
        if (options.targetSizeKb) {
            formData.append('target_size_kb', options.targetSizeKb.toString());
        }
        if (options.quality) formData.append('quality', options.quality.toString());

        const response = await fetch(`${this.baseURL}/batch-animated-resize-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async webpResizeZip(
        files: File[],
        options: {
            format?: 'webp' | 'png' | 'jpg';
            width?: number;
            targetSizeKb?: number;
            quality?: number;
        }
    ): Promise<Blob> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        if (options.format) formData.append('format', options.format);
        if (options.width) formData.append('width', options.width.toString());
        if (options.targetSizeKb) {
            formData.append('target_size_kb', options.targetSizeKb.toString());
        }
        if (options.quality) formData.append('quality', options.quality.toString());

        const response = await fetch(`${this.baseURL}/webp-resize-zip`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.blob();
    }

    async batchToWebpZip(
        files: File[],
        options: {
            width?: number;
            fps?: number;
            quality?: number;
        }
    ): Promise<BatchToWebpResult> {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        if (options.width) formData.append('width', options.width.toString());
        if (options.fps) formData.append('fps', options.fps.toString());
        if (options.quality) formData.append('quality', options.quality.toString());

        const response = await fetch(`${this.baseURL}/batch-to-webp-zip`, {
            method: 'POST',
            body: formData,
        });

        const contentType = response.headers.get('content-type') || '';

        // Check if response is JSON (partial success or all failed)
        if (contentType.includes('application/json')) {
            const jsonData = await response.json();

            if (!response.ok) {
                // All files failed
                return {
                    success: false,
                    blob: null,
                    successfulCount: 0,
                    failedCount: jsonData.failed_count || 0,
                    failedFiles: jsonData.failed_files || [],
                    error: jsonData.error || 'Có lỗi xảy ra',
                };
            }

            // Partial success - need to download from URL
            const downloadUrl = `${this.baseURL}${jsonData.download_url}`;
            const downloadResponse = await fetch(downloadUrl);

            if (!downloadResponse.ok) {
                throw new Error('Không thể tải file ZIP');
            }

            const blob = await downloadResponse.blob();
            return {
                success: true,
                blob,
                successfulCount: jsonData.successful_count || 0,
                successfulFiles: jsonData.successful_files || [],
                failedCount: jsonData.failed_count || 0,
                failedFiles: jsonData.failed_files || [],
                message: jsonData.message,
            };
        }

        // Full success - direct blob response
        if (!response.ok) {
            throw new Error(await response.text());
        }

        const blob = await response.blob();
        return {
            success: true,
            blob,
            successfulCount: files.length,
            failedCount: 0,
            failedFiles: [],
        };
    }

    async getTracking(page = 1, limit = 100): Promise<TrackingResponse> {
        const response = await fetch(
            `${ANALYTICS_BASE_URL}/api/analytics/v1/tracking?page=${page}&limit=${limit}`,
            { cache: 'no-store' }
        );

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.json();
    }

    async getAnalyticsStats(): Promise<AnalyticsStats> {
        const response = await fetch(`${this.baseURL}/api/analytics/stats`);

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.json();
    }

    async getLogs(): Promise<Log[]> {
        const response = await fetch(`${this.baseURL}/api/android-log`);

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return response.json();
    }

    async clearLogs(): Promise<void> {
        const response = await fetch(`${this.baseURL}/api/android-log`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }
    }

    getLogStreamURL(): string {
        return `${this.baseURL}/api/android-log/stream`;
    }
}

export const apiClient = new APIClient();

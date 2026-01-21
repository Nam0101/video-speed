# Tracking API Documentation

API documentation for posting tracking events from backend services.

## Base URL
```
https://video-speed.160.250.136.70.nip.io/api
```

---

## POST /android-log

Log a tracking event.

### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "eventName": "string",      // Required: Event name (e.g., "identify_plant", "app_open")
  "deviceName": "string",     // Optional: Device identifier (e.g., "Samsung Galaxy S24")
  "versionCode": "string",    // Optional: App version code (e.g., "156")
  "params": {                 // Optional: Additional parameters
    "key1": "value1",
    "key2": "value2"
  }
}
```

### Response

**Success (200):**
```json
{
  "status": "logged",
  "entry": {
    "timestamp": "2026-01-21 12:30:00",
    "eventName": "identify_plant",
    "deviceName": "Samsung Galaxy S24",
    "versionCode": "156",
    "params": {
      "plant_name": "Rose",
      "confidence": "0.95"
    }
  }
}
```

**Error (500):**
```json
{
  "status": "error",
  "message": "Error description"
}
```

---

## GET /android-log

Retrieve all logged events (last 1000).

### Response

```json
[
  {
    "timestamp": "2026-01-21 12:30:00",
    "eventName": "identify_plant",
    "deviceName": "Samsung Galaxy S24",
    "versionCode": "156",
    "params": { ... }
  },
  ...
]
```

---

## DELETE /android-log

Clear all logs.

### Response

```json
{
  "status": "cleared"
}
```

---

## Example Usage

### cURL
```bash
curl -X POST https://video-speed.160.250.136.70.nip.io/api/android-log \
  -H "Content-Type: application/json" \
  -d '{
    "eventName": "identify_plant",
    "deviceName": "Samsung Galaxy S24",
    "versionCode": "156",
    "params": {
      "plant_name": "Rose",
      "confidence": "0.95"
    }
  }'
```

### Kotlin (OkHttp)
```kotlin
val client = OkHttpClient()
val json = """
{
  "eventName": "identify_plant",
  "deviceName": "${Build.MANUFACTURER} ${Build.MODEL}",
  "versionCode": "${BuildConfig.VERSION_CODE}",
  "params": {
    "plant_name": "Rose"
  }
}
""".trimIndent()

val request = Request.Builder()
    .url("https://video-speed.160.250.136.70.nip.io/api/android-log")
    .post(json.toRequestBody("application/json".toMediaType()))
    .build()

client.newCall(request).enqueue(object : Callback {
    override fun onFailure(call: Call, e: IOException) {}
    override fun onResponse(call: Call, response: Response) {}
})
```

### Node.js (fetch)
```javascript
await fetch('https://video-speed.160.250.136.70.nip.io/api/android-log', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    eventName: 'identify_plant',
    deviceName: 'Server Backend',
    versionCode: '1.0.0',
    params: { source: 'api' }
  })
});
```

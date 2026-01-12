# Android Client Logging Implementation

Documentation for integrating Android logs with the `Media Converter Pro` backend.

## 1. Web View & Server Info
- **Web View URL**: `http://YOUR_SERVER_IP:5000/` (Tab **Android Logs**)
- **API Endpoint**: `POST /api/android-log`
- **Content-Type**: `application/json`

## 2. Dependencies
Add **OkHttp** and **Gson** (or Kotlin Serialization) to your `app/build.gradle`:

```kotlin
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.code.gson:gson:2.10.1")
}
```

## 3. Implementation Code

Create a helper object `LogSender` to handle network requests.

```kotlin
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import android.os.Build
import com.plant.identify.scanner.leaf.flower.tree.disease.garden.BuildConfig // Adjust to your package

object LogSender {
    // ⚠️ Replace with your computer's local IP (e.g. 192.168.1.x) if running locally
    // If deployed on Render, use your Render URL (e.g. https://your-app.onrender.com)
    private const val SERVER_URL = "http://192.168.1.10:5000" 
    
    private val client = OkHttpClient()
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    data class LogPayload(
        val eventName: String,
        val deviceName: String,
        val versionCode: Int,
        val params: Map<String, String?>
    )

    fun sendLog(eventName: String, params: Map<String, String?>?) {
        val payload = LogPayload(
            eventName = eventName,
            deviceName = "${Build.MANUFACTURER} ${Build.MODEL}",
            versionCode = BuildConfig.VERSION_CODE,
            params = params ?: emptyMap()
        )

        val jsonBody = gson.toJson(payload)
        val body = jsonBody.toRequestBody(jsonMediaType)

        val request = Request.Builder()
            .url("$SERVER_URL/api/android-log")
            .post(body)
            .build()

        // Execute in background to avoid blocking IO
        try {
            client.newCall(request).execute().close()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
```

## 4. Usage in EventLogger

Modify your `EventLoggerImpl` to call `LogSender`:

```kotlin
override fun logEvent(eventName: String, params: Map<String, String?>?) {
    appCoroutineScope.launch(appCoroutineDispatchers.io) {
        val typedParams: HashMap<String, String?>? = params?.takeIf { it.isNotEmpty() }?.let { HashMap(it) }
        
        // 1. Existing local log
        Timber.tag(TAG).d("Event logged: $eventName, params: $typedParams")

        // 2. Existing Firebase/Analytics log
        LogEventManager.logEventAndParams(
            context = applicationContext,
            eventName = eventName,
            params = typedParams,
        )

        // 3. [NEW] Send to Custom Web Server
        try {
            LogSender.sendLog(eventName, typedParams)
        } catch (e: Exception) {
            // Silently fail or log error
            Timber.e(e, "Failed to send log to server")
        }
    }
}
```

## 5. Deployment Note (Render)
If you deploy this Python server to **Render**:
- Logs are stored in **RAM**.
- They will disappear if the server restarts or sleeps (free tier sleeps after 15 mins of inactivity).
- To keep logs permanently, you would need to add a Database (SQLite/PostgreSQL) instead of using the `ANDROID_LOGS` list variable.

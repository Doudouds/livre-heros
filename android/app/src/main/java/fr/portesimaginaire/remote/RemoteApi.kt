package fr.portesimaginaire.remote

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URI
import java.net.URLDecoder

class ApiException(val status: Int, message: String) : IOException(message)

data class Endpoint(val base: String, val embeddedToken: String = "") {
    companion object {
        fun parse(input: String): Endpoint {
            val value = input.trim()
            require(value.isNotEmpty()) { "Saisissez l’adresse du lecteur affichée sur le PC." }
            val uri = try { URI(if ("://" in value) value else "http://$value") }
            catch (_: Exception) { throw IllegalArgumentException("Adresse du lecteur incorrecte.") }
            val scheme = uri.scheme?.lowercase()
            require(scheme in listOf("http", "https") && uri.host != null && uri.userInfo == null && uri.query == null &&
                uri.path.orEmpty() in listOf("", "/") && uri.port in -1..65535 && uri.port != 0) {
                "Utilisez une adresse de lecteur comme 192.168.1.20:8765."
            }
            val port = if (uri.port != -1) uri.port else if (scheme == "https") 443 else 8765
            val host = uri.host.lowercase().removePrefix("[").removeSuffix("]")
            require(host != "0.0.0.0" && host != "::") { "Utilisez l’adresse du PC sur le réseau local." }
            val authority = if (":" in host) "[$host]" else host
            val fragment = uri.rawFragment.orEmpty()
            val embedded = if (fragment.startsWith("connexion=")) URLDecoder.decode(fragment.substringAfter('='), "UTF-8") else ""
            require(embedded.length <= 128 && embedded.all { it.isLetterOrDigit() || it in "_-" }) { "Lien de connexion incorrect." }
            return Endpoint("$scheme://$authority:$port", embedded)
        }

        fun isLocal(address: InetAddress): Boolean {
            val bytes = address.address
            val privateV6 = bytes.size == 16 && (bytes[0].toInt() and 0xfe) == 0xfc
            return !address.isAnyLocalAddress && !address.isMulticastAddress &&
                (address.isSiteLocalAddress || address.isLinkLocalAddress || address.isLoopbackAddress || privateV6)
        }
    }
}

data class Choice(val index: Int, val text: String)
data class AudioProgress(val position: Long, val duration: Long)
data class Snapshot(
    val revision: Long, val active: Boolean, val title: String = "", val scene: String = "",
    val text: String = "", val mode: String = "interactive", val audioState: String = "unavailable",
    val completed: Boolean = false, val stopped: Boolean = false, val passage: Int = 0,
    val passages: Int = 0, val choices: List<Choice> = emptyList(), val question: String = "",
    val canAdvance: Boolean = false, val volume: Int = 70, val volumeSupported: Boolean = false,
    val progress: AudioProgress? = null, val error: String = ""
) {
    companion object {
        fun parse(json: JSONObject): Snapshot {
            val revision = json.getLong("revision")
            if (!json.getBoolean("active")) return Snapshot(revision, false, error = json.optionalText("error"))
            val automatic = json.optString("mode") == "automatic"
            val choices = json.optJSONArray("choices")
            val progress = json.optJSONObject("progress")
            return Snapshot(revision, true, json.getString("title"), json.optString("scene_title"),
                json.optString("text"), json.optString("mode"), json.optString("audio_state"),
                json.optBoolean("completed"), json.optBoolean("stopped"), json.optInt("passage"),
                json.optInt("passages"), if (automatic || choices == null) emptyList() else
                    (0 until choices.length()).map { val c = choices.getJSONObject(it); Choice(c.getInt("index"), c.getString("text")) },
                if (automatic) "" else json.optionalText("question"), !automatic && json.optBoolean("can_advance"),
                json.optInt("volume", 70).coerceIn(0, 100), json.optBoolean("volume_supported"),
                progress?.let { AudioProgress(it.optLong("position_ms").coerceAtLeast(0), it.optLong("duration_ms").coerceAtLeast(0)) },
                json.optionalText("error"))
        }
    }
}

data class Mode(val id: String, val available: Int, val total: Int, val complete: Boolean)
data class Book(val id: String, val title: String, val author: String, val description: String, val modes: List<Mode>)
data class Option(val id: String, val label: String)
data class Library(val books: List<Book>, val adventures: List<Option>, val catalogs: Map<String, List<Option>>) {
    companion object {
        fun parse(json: JSONObject): Library {
            val books = json.getJSONArray("books")
            val adventures = json.getJSONArray("adventures")
            val catalogs = json.getJSONObject("catalogs")
            return Library((0 until books.length()).map { i ->
                val b = books.getJSONObject(i)
                val modes = b.getJSONObject("modes")
                Book(b.getString("id"), b.getString("title"), b.optString("author"), b.optString("description"),
                    listOf("interactive", "automatic").filter { modes.has(it) }.map { key ->
                        val mode = modes.getJSONObject(key)
                        Mode(key, mode.getInt("available"), mode.getInt("total"), mode.getBoolean("complete"))
                    })
            }, (0 until adventures.length()).map { val a = adventures.getJSONObject(it); Option(a.getString("id"), a.getString("title")) },
                listOf("hero", "location", "item").associateWith { key ->
                    val values = catalogs.getJSONArray(key)
                    (0 until values.length()).map { val v = values.getJSONObject(it); Option(v.getString("id"), v.getString("label")) }
                })
        }
    }
}

private fun JSONObject.optionalText(key: String): String = if (isNull(key)) "" else optString(key, "")

class RemoteApi(val endpoint: Endpoint, val token: String = "") {
    fun connect(code: String): String {
        val digits = code.filterNot(Char::isWhitespace)
        require(digits.length == 8 && digits.all { it in '0'..'9' }) { "Saisissez le code à huit chiffres affiché sur le PC." }
        return request("/api/connect", JSONObject().put("code", digits), authenticated = false).getString("token")
    }

    fun state(): Snapshot = Snapshot.parse(request("/api/state"))
    fun library(): Library = Library.parse(request("/api/library"))
    fun command(action: String, revision: Long, values: Map<String, Any> = emptyMap()): Snapshot {
        val payload = JSONObject()
        values.forEach { (key, value) -> payload.put(key, value) }
        payload.put("action", action).put("revision", revision)
        return Snapshot.parse(request("/api/command", payload))
    }

    private fun request(path: String, payload: JSONObject? = null, authenticated: Boolean = true): JSONObject {
        val uri = URI(endpoint.base)
        val addresses = InetAddress.getAllByName(uri.host.removePrefix("[").removeSuffix("]"))
        require(addresses.isNotEmpty() && addresses.all(Endpoint::isLocal)) {
            "Cette application se connecte uniquement à un lecteur du réseau local."
        }
        val connection = URI(endpoint.base + path).toURL().openConnection() as HttpURLConnection
        connection.connectTimeout = 3000
        connection.readTimeout = 6000
        connection.instanceFollowRedirects = false
        connection.useCaches = false
        if (authenticated) connection.setRequestProperty("X-Remote-Token", token)
        connection.setRequestProperty("Accept", "application/json")
        try {
            if (payload != null) {
                val bytes = payload.toString().toByteArray(Charsets.UTF_8)
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
            }
            val status = connection.responseCode
            if (status in 300..399) throw ApiException(status, "Le lecteur a redirigé la connexion. Vérifiez son adresse.")
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (output.size() + count > 2 * 1024 * 1024) throw IOException("Réponse du lecteur trop volumineuse.")
                    output.write(buffer, 0, count)
                }
                output.toString("UTF-8")
            }.orEmpty()
            val json = try { JSONObject(body) } catch (_: Exception) {
                throw ApiException(status, "Cette adresse ne répond pas comme un lecteur d’histoires.")
            }
            if (status !in 200..299) throw ApiException(status, json.optString("error", "Commande refusée par le lecteur."))
            return json
        } finally { connection.disconnect() }
    }
}

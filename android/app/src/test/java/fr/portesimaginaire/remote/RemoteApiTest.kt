package fr.portesimaginaire.remote

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread

class RemoteApiTest {
    private val stateJson = """{"revision":3,"active":true,"title":"Le Roi-grenouille","scene_title":"La fontaine",
        "text":"Le récit.","mode":"interactive","audio_state":"paused","passage":1,"passages":11,
        "choices":[{"index":0,"text":"Observer"},{"index":1,"text":"Répondre"}],
        "question":"Que doit faire la princesse ?","can_advance":false,"volume":25,"volume_supported":true,
        "progress":{"position_ms":17000,"duration_ms":76000},"error":null}""".trimIndent()

    private fun <T> server(handler: (String, String, String) -> Pair<Int, String>, test: (Endpoint) -> T): T {
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        val failure = AtomicReference<Throwable?>()
        val worker = thread(isDaemon = true) {
            try {
                while (!server.isClosed) server.accept().use { socket ->
                    socket.soTimeout = 2000
                    val input = socket.getInputStream().buffered()
                    fun line(): String {
                        val text = StringBuilder()
                        while (true) {
                            val next = input.read()
                            if (next == -1 || next == 10) return text.toString().trimEnd('\r')
                            text.append(next.toChar())
                        }
                    }
                    val path = line().split(' ')[1]
                    val headers = mutableMapOf<String, String>()
                    while (true) {
                        val header = line()
                        if (header.isEmpty()) break
                        headers[header.substringBefore(':').lowercase()] = header.substringAfter(':').trim()
                    }
                    val bodyBytes = ByteArray(headers["content-length"]?.toInt() ?: 0)
                    var offset = 0
                    while (offset < bodyBytes.size) {
                        val read = input.read(bodyBytes, offset, bodyBytes.size - offset)
                        check(read > 0); offset += read
                    }
                    val result = handler(path, headers["x-remote-token"].orEmpty(), String(bodyBytes, Charsets.UTF_8))
                    val bytes = result.second.toByteArray(Charsets.UTF_8)
                    socket.getOutputStream().apply {
                        write("HTTP/1.1 ${result.first} Test\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                        write(bytes); flush()
                    }
                }
            } catch (error: Throwable) { if (!server.isClosed) failure.set(error) }
        }
        try { return test(Endpoint.parse("127.0.0.1:${server.localPort}")) }
        finally {
            server.close(); worker.join(1000)
            failure.get()?.let { throw AssertionError("Échec du serveur de test", it) }
        }
    }

    @Test fun normalizesReaderAddressesAndExtractsOnlyExplicitConnectionTokens() {
        assertEquals("http://192.168.1.20:8765", Endpoint.parse(" 192.168.1.20 ").base)
        assertEquals("http://livre.local:8766", Endpoint.parse("http://livre.local:8766/").base)
        assertEquals("https://lecteur.local:443", Endpoint.parse("https://lecteur.local").base)
        assertEquals("saved-token", Endpoint.parse("http://192.168.1.20:8765/#connexion=saved-token").embeddedToken)
        assertFalse(Endpoint.parse("http://192.168.1.20/#connexion=saved-token").base.contains("saved-token"))
        assertEquals("http://[fd00::1]:8765", Endpoint.parse("http://[fd00::1]/").base)
    }

    @Test fun rejectsAmbiguousOrUnsafeReaderAddresses() {
        for (input in listOf("", "javascript:alert(1)", "file:///tmp/test", "http://user:secret@192.168.1.2/",
            "http://192.168.1.2/private", "http://192.168.1.2/?token=secret", "http://192.168.1.2:0",
            "http://0.0.0.0/", "http://192.168.1.2/#connexion=bad%0d%0aheader")) {
            assertThrows("Accepted $input", IllegalArgumentException::class.java) { Endpoint.parse(input) }
        }
    }

    @Test fun acceptsLocalNetworksButNotPublicOrMulticastAddresses() {
        for (address in listOf("192.168.1.2", "10.0.2.2", "172.16.1.2", "127.0.0.1", "169.254.1.2", "fd00::1", "::1")) {
            assertTrue(address, Endpoint.isLocal(InetAddress.getByName(address)))
        }
        for (address in listOf("8.8.8.8", "0.0.0.0", "224.0.0.1", "2606:4700:4700::1111")) {
            assertFalse(address, Endpoint.isLocal(InetAddress.getByName(address)))
        }
        assertThrows(IllegalArgumentException::class.java) { RemoteApi(Endpoint.parse("http://8.8.8.8")).state() }
    }

    @Test fun pairsWithEightDigitsWithoutSendingAnOldToken() {
        server({ path, token, body ->
            assertEquals("/api/connect", path)
            assertEquals("", token)
            assertEquals("12345678", JSONObject(body).getString("code"))
            200 to """{"token":"temporary-reader-token"}"""
        }) { endpoint ->
            assertEquals("temporary-reader-token", RemoteApi(endpoint, "old-token").connect("1234 5678"))
            assertThrows(IllegalArgumentException::class.java) { RemoteApi(endpoint).connect("123") }
        }
    }

    @Test fun readsRealAudioProgressAndInteractiveChoices() {
        server({ path, token, _ ->
            assertEquals("/api/state", path); assertEquals("current-token", token)
            200 to stateJson
        }) { endpoint ->
            val state = RemoteApi(endpoint, "current-token").state()
            assertEquals(3L, state.revision)
            assertEquals("paused", state.audioState)
            assertEquals(17000L, state.progress!!.position)
            assertEquals(76000L, state.progress.duration)
            assertEquals(2, state.choices.size)
            assertEquals(25, state.volume)
            assertEquals("Que doit faire la princesse ?", state.question)
            assertEquals("", state.error)
        }
    }

    @Test fun automaticModeNeverExposesQuestionsChoicesOrManualAdvance() {
        val json = JSONObject(stateJson).put("mode", "automatic").put("can_advance", true)
        val state = Snapshot.parse(json)
        assertEquals(emptyList<Choice>(), state.choices)
        assertEquals("", state.question)
        assertFalse(state.canAdvance)
    }

    @Test fun inactiveStateAndMissingAudioAreNotMisreportedAsPlaying() {
        val empty = Snapshot.parse(JSONObject("""{"active":false,"revision":0,"error":null}"""))
        assertFalse(empty.active)
        assertNull(empty.progress)
        val missing = Snapshot.parse(JSONObject(stateJson).put("audio_state", "unavailable").put("progress", JSONObject.NULL)
            .put("error", "Audio absent : lecture suspendue."))
        assertEquals("unavailable", missing.audioState)
        assertEquals("Audio absent : lecture suspendue.", missing.error)
        assertNull(missing.progress)
    }

    @Test fun libraryKeepsBothIndependentAudioPlansAndPersonalization() {
        val catalog = Library.parse(JSONObject("""{
            "books":[{"id":"roi_grenouille","title":"Le Roi-grenouille","author":"Grimm","description":"Un conte.",
            "modes":{"interactive":{"available":1,"total":21,"complete":false},"automatic":{"available":11,"total":11,"complete":true}}}],
            "adventures":[{"id":"cages","title":"La Maison aux Sept Cages"}],
            "catalogs":{"hero":[{"id":"knight","label":"Chevalier"}],"location":[],"item":[]}}
        """))
        assertEquals(21, catalog.books.single().modes.first().total)
        assertFalse(catalog.books.single().modes.first().complete)
        assertTrue(catalog.books.single().modes.last().complete)
        assertEquals("cages", catalog.adventures.single().id)
        assertEquals("knight", catalog.catalogs.getValue("hero").single().id)
    }

    @Test fun commandsCarryTheDisplayedRevisionAndAreNeverRetriedAfterConflict() {
        val calls = AtomicInteger()
        server({ path, token, body ->
            calls.incrementAndGet()
            assertEquals("/api/command", path); assertEquals("current-token", token)
            val command = JSONObject(body)
            assertEquals("choose", command.getString("action"))
            assertEquals(3L, command.getLong("revision")); assertEquals(1, command.getInt("index"))
            409 to """{"error":"La lecture a changé."}"""
        }) { endpoint ->
            val error = assertThrows(ApiException::class.java) {
                RemoteApi(endpoint, "current-token").command("choose", 3, mapOf("index" to 1))
            }
            assertEquals(409, error.status)
            assertEquals(1, calls.get())
        }
    }

    @Test fun connectionErrorsAndRedirectsDoNotLeakTokensToAnotherLocation() {
        server({ _, _, _ -> 401 to """{"error":"Le code a expiré."}""" }) { endpoint ->
            val error = assertThrows(ApiException::class.java) { RemoteApi(endpoint, "old").state() }
            assertEquals(401, error.status); assertEquals("Le code a expiré.", error.message)
        }
        server({ _, _, _ -> 302 to "redirect" }) { endpoint ->
            assertEquals(302, assertThrows(ApiException::class.java) { RemoteApi(endpoint, "private").state() }.status)
        }
        server({ _, _, _ -> 200 to "<html>wrong service</html>" }) { endpoint ->
            assertThrows(ApiException::class.java) { RemoteApi(endpoint).state() }
        }
    }
}

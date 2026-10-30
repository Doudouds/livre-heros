package fr.portesimaginaire.remote

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread

class ReaderDiscoveryTest {
    private val local = InetAddress.getByName("127.0.0.1")
    private fun reply(nonce: String, port: Int = 8765, name: String = "Mon PC") = JSONObject()
        .put("service", ReaderDiscovery.SERVICE).put("version", 1).put("kind", "reader")
        .put("nonce", nonce).put("name", name).put("port", port)
    private fun packet(json: JSONObject, source: String = "192.168.1.20"): DatagramPacket {
        val bytes = json.toString().toByteArray()
        return DatagramPacket(bytes, bytes.size, InetAddress.getByName(source), ReaderDiscovery.PORT)
    }

    @Test fun acceptsOnlyCurrentReaderRepliesAndUsesTheSenderAddress() {
        val message = reply("fresh", 8766).put("host", "example.com")
        val reader = ReaderDiscovery.parseReply(packet(message), "fresh")!!
        assertEquals("Mon PC", reader.name)
        assertEquals("http://192.168.1.20:8766", reader.endpoint.base)
        assertNull(ReaderDiscovery.parseReply(packet(message), "old"))
        assertNull(ReaderDiscovery.parseReply(packet(message, "8.8.8.8"), "fresh"))
    }

    @Test fun rejectsWrongServiceInvalidFieldsAndOversizedMessages() {
        for (message in listOf(reply("fresh").put("service", "another-service"), reply("fresh").put("version", "1"),
            reply("fresh").put("port", "8765"), reply("fresh", 0), reply("fresh", 65536),
            reply("fresh", name = "bad\nname"), reply("fresh", name = ""), reply("fresh", name = "x".repeat(1100)))) {
            assertNull(ReaderDiscovery.parseReply(packet(message), "fresh"))
        }
    }

    @Test fun realUdpSearchIgnoresWrongNonceAndDeduplicatesSeveralReaders() {
        DatagramSocket(0, local).use { server ->
            val error = AtomicReference<Throwable?>()
            val responder = thread {
                try {
                    val query = DatagramPacket(ByteArray(1024), 1024)
                    server.soTimeout = 1000; server.receive(query)
                    val nonce = JSONObject(String(query.data, 0, query.length)).getString("nonce")
                    for (message in listOf(reply("wrong"), reply(nonce), reply(nonce), reply(nonce, 8766, "Mon Pi"))) {
                        val bytes = message.toString().toByteArray()
                        server.send(DatagramPacket(bytes, bytes.size, query.address, query.port))
                    }
                } catch (failure: Throwable) { error.set(failure) }
            }
            val readers = ReaderDiscovery(targets = listOf(local), port = server.localPort, durationMs = 300).search()
            responder.join(1500)
            error.get()?.let { throw AssertionError(it) }
            assertEquals(listOf("Mon PC", "Mon Pi"), readers.map { it.name })
            assertEquals(2, readers.map { it.endpoint.base }.distinct().size)
        }
    }

    @Test fun noReplyReturnsWithinDeadlineAndCancellationClosesTheSocket() {
        DatagramSocket(0, local).use { silent ->
            val started = System.nanoTime()
            assertTrue(ReaderDiscovery(targets = listOf(local), port = silent.localPort, durationMs = 150).search().isEmpty())
            assertTrue((System.nanoTime() - started) / 1_000_000 < 1200)
            val search = ReaderDiscovery(targets = listOf(local), port = silent.localPort, durationMs = 5000)
            val error = AtomicReference<Throwable?>()
            val worker = thread { try { search.search() } catch (failure: Throwable) { error.set(failure) } }
            Thread.sleep(50)
            search.close(); worker.join(1000)
            assertFalse(worker.isAlive)
            assertNull(error.get())
        }
    }
}

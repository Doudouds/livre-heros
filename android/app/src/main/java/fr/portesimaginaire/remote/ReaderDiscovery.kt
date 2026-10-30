package fr.portesimaginaire.remote

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.SocketException
import java.net.SocketTimeoutException
import java.util.UUID

data class DiscoveredReader(val name: String, val endpoint: Endpoint)

/** Recherche ciblée et bornée : trois demandes, aucune exploration des adresses IP. */
class ReaderDiscovery(
    private val context: Context? = null,
    private val targets: List<InetAddress>? = null,
    private val port: Int = PORT,
    private val durationMs: Long = 3000
) : AutoCloseable {
    @Volatile private var socket: DatagramSocket? = null
    @Volatile private var cancelled = false

    fun search(): List<DiscoveredReader> {
        val nonce = UUID.randomUUID().toString()
        val request = JSONObject().put("service", SERVICE).put("version", 1).put("kind", "discover")
            .put("nonce", nonce).toString().toByteArray(Charsets.UTF_8)
        val found = linkedMapOf<String, DiscoveredReader>()
        DatagramSocket().use { connection ->
            socket = connection
            if (cancelled) return emptyList()
            connection.broadcast = true
            connection.soTimeout = 120
            if (targets == null && context != null) {
                val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
                val network = connectivity.allNetworks.firstOrNull {
                    val capabilities = connectivity.getNetworkCapabilities(it)
                    capabilities?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true ||
                        capabilities?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true
                }
                network?.bindSocket(connection)
            }
            val destinations = targets ?: broadcastAddresses()
            val started = System.nanoTime()
            var nextSend = 0L
            while (!cancelled) {
                val elapsed = (System.nanoTime() - started) / 1_000_000
                if (elapsed >= durationMs) break
                if (elapsed >= nextSend && nextSend < 2400) {
                    for (address in destinations) {
                        try { connection.send(DatagramPacket(request, request.size, address, port)) }
                        catch (_: java.io.IOException) { /* Une interface peut disparaître pendant la recherche. */ }
                    }
                    nextSend += 800
                }
                val buffer = ByteArray(1025)
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    connection.receive(packet)
                    parseReply(packet, nonce)?.let { found[it.endpoint.base] = it }
                } catch (_: SocketTimeoutException) { /* Attendre d’autres lecteurs jusqu’à l’échéance. */ }
                catch (error: SocketException) { if (!cancelled) throw error }
            }
        }
        socket = null
        return found.values.sortedWith(compareBy({ it.name.lowercase() }, { it.endpoint.base }))
    }

    override fun close() { cancelled = true; socket?.close() }

    companion object {
        const val PORT = 18766
        const val SERVICE = "portes-imaginaire-reader"

        fun parseReply(packet: DatagramPacket, nonce: String): DiscoveredReader? {
            if (packet.length > 1024 || packet.address !is Inet4Address || !Endpoint.isLocal(packet.address)) return null
            return runCatching {
                val json = JSONObject(String(packet.data, packet.offset, packet.length, Charsets.UTF_8))
                if (json.optString("service") != SERVICE || json.opt("version") != 1 ||
                    json.optString("kind") != "reader" || json.optString("nonce") != nonce) return null
                val port = json.opt("port") as? Int ?: return null
                val name = json.getString("name")
                if (port !in 1..65535 || name.isBlank() || name.length > 100 || name.any { it.isISOControl() }) return null
                // L’adresse vient du paquet reçu, jamais d’un hôte arbitraire fourni dans le JSON.
                DiscoveredReader(name, Endpoint.parse("http://${packet.address.hostAddress}:$port"))
            }.getOrNull()
        }

        private fun broadcastAddresses(): List<InetAddress> {
            val addresses = linkedSetOf<InetAddress>()
            runCatching {
                NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }.forEach { network ->
                    network.interfaceAddresses.filter { it.address is Inet4Address && Endpoint.isLocal(it.address) }
                        .mapNotNullTo(addresses) { it.broadcast }
                }
            }
            addresses.add(InetAddress.getByName("255.255.255.255"))
            return addresses.toList()
        }
    }
}

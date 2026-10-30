package fr.portesimaginaire.remote

import android.content.Context
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.net.InetAddress
import java.net.URI

/** Intégration sur Android réel : aucun événement tactile ou état d’interface simulé. */
@RunWith(AndroidJUnit4::class)
class ReaderDeviceTest {
    @Test fun discoversThePcReaderThroughTheNativeUdpClient() {
        val args = InstrumentationRegistry.getArguments()
        val target = args.getString("discoveryTarget").orEmpty()
        assumeTrue("Fournir une cible UDP de test accessible depuis l’émulateur.", target.isNotEmpty())
        val port = args.getString("discoveryPort")?.toInt() ?: ReaderDiscovery.PORT
        val readers = if (target == "broadcast") ReaderDiscovery(InstrumentationRegistry.getInstrumentation().targetContext, port = port).search()
            else ReaderDiscovery(targets = listOf(InetAddress.getByName(target)), port = port).search()
        val httpPort = URI(args.getString("readerAddress")).port
        assertTrue("Le lecteur PC doit être découvert.", readers.any { URI(it.endpoint.base).port == httpPort })
        assertTrue(readers.all { it.name.isNotEmpty() && it.endpoint.embeddedToken.isEmpty() })
    }

    @Test fun nativeClientAndLifecycleControlThePcWithoutDependingOnTheActivity() {
        val args = InstrumentationRegistry.getArguments()
        val address = args.getString("readerAddress").orEmpty()
        val code = args.getString("readerCode").orEmpty()
        assumeTrue("Fournir un lecteur de test et son code temporaire.", address.isNotEmpty() && code.length == 8)
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        lateinit var model: RemoteCoordinator
        fun main(block: () -> Unit) = instrumentation.runOnMainSync(block)
        fun await(label: String, condition: () -> Boolean) {
            val deadline = SystemClock.elapsedRealtime() + 10000
            while (SystemClock.elapsedRealtime() < deadline) {
                var passed = false
                main { passed = condition() }
                if (passed) return
                SystemClock.sleep(30)
            }
            fail("État attendu : $label")
        }
        main {
            model = RemoteCoordinator(instrumentation.targetContext) { }
            model.start()
            model.connect(address, code)
        }
        try {
            await("connexion et catalogue") { model.connected && !model.busy && model.library != null }
            assertTrue(model.library!!.books.any { it.id == "roi_grenouille" && it.modes.any { m -> m.id == "automatic" && m.complete } })
            main { model.command("start", mapOf("kind" to "book", "id" to "roi_grenouille", "mode" to "automatic")) }
            await("lecture automatique") { !model.busy && model.state?.audioState == "playing" }
            assertEquals("automatic", model.state!!.mode)
            assertTrue(model.state!!.choices.isEmpty())
            assertEquals("", model.state!!.question)
            main { model.command("pause") }
            await("pause") { !model.busy && model.state?.audioState == "paused" }
            val paused = model.state!!.progress!!.position
            main { model.stop() }
            val preferences = instrumentation.targetContext.getSharedPreferences("reader_connection", Context.MODE_PRIVATE)
            val api = RemoteApi(Endpoint.parse(preferences.getString("address", "").orEmpty()), preferences.getString("token", "").orEmpty())
            SystemClock.sleep(200)
            assertEquals("paused", api.state().audioState)
            assertEquals(paused, api.state().progress!!.position)
            main { model.start() }
            await("retour au premier plan") { model.connected && model.state?.audioState == "paused" }
            main { model.command("resume") }
            await("reprise") { !model.busy && model.state?.audioState == "playing" }
            if (model.state!!.volumeSupported) {
                main { model.command("volume", mapOf("value" to 35)) }
                await("volume") { !model.busy && model.state?.volume == 35 }
            }
            val revision = model.state!!.revision
            main { model.command("replay") }
            await("rejouer") { !model.busy && model.state!!.revision > revision }
            assertEquals(1, model.state!!.passage)
            main { model.command("stop") }
            await("arrêt") { !model.busy && model.state?.stopped == true }
            main { model.command("restart") }
            await("recommencer") { !model.busy && model.state?.audioState == "playing" }
            assertEquals("automatic", model.state!!.mode)
            main { model.command("pause") }
            await("pause finale pour inspection") { !model.busy && model.state?.audioState == "paused" }
        } finally { main { model.close() } }
    }
}

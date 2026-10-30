package fr.portesimaginaire.remote

import android.content.Context
import android.os.Handler
import android.os.Looper
import java.util.concurrent.Executors

/** Le cycle de vie du téléphone ne commande jamais l’arrêt du lecteur. */
class RemoteCoordinator(context: Context, private val changed: (Boolean) -> Unit) {
    private val appContext = context.applicationContext
    private val preferences = context.getSharedPreferences("reader_connection", Context.MODE_PRIVATE)
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val discoveryWorker = Executors.newSingleThreadExecutor()
    private var discovery: ReaderDiscovery? = null
    private var discoveryGeneration = 0
    private var api: RemoteApi? = null
    private var running = false
    private var polling = false
    private var epoch = 0
    private val poll = Runnable { refresh() }

    var address: String = preferences.getString("address", "").orEmpty()
        private set
    var connected = false
        private set
    var busy = false
        private set
    var message = ""
        private set
    var library: Library? = null
        private set
    var state: Snapshot? = null
        private set
    val needsConnection: Boolean get() = api == null
    var findingReaders = false
        private set
    var foundReaders: List<DiscoveredReader> = emptyList()
        private set
    var discoveryMessage = ""
        private set

    init {
        val token = preferences.getString("token", "").orEmpty()
        if (address.isNotEmpty() && token.isNotEmpty()) {
            api = runCatching { RemoteApi(Endpoint.parse(address), token) }.getOrNull()
        }
    }

    fun start() { running = true; changed(false); refresh() }
    fun stop() {
        cancelDiscovery()
        running = false
        epoch++
        main.removeCallbacks(poll)
        polling = false
        busy = false
        connected = false
    }
    fun close() { stop(); worker.shutdownNow(); discoveryWorker.shutdownNow() }

    private fun cancelDiscovery() {
        discoveryGeneration++
        discovery?.close(); discovery = null
        if (findingReaders) discoveryMessage = "Recherche interrompue. Vous pouvez la relancer."
        findingReaders = false
    }

    fun findReaders() {
        if (!running || busy || findingReaders || !needsConnection) return
        cancelDiscovery()
        val generation = discoveryGeneration
        val search = ReaderDiscovery(appContext)
        discovery = search
        findingReaders = true; foundReaders = emptyList(); discoveryMessage = "Recherche des lecteurs sur le Wi-Fi…"
        message = ""; changed(false)
        discoveryWorker.execute {
            val result = runCatching { search.search() }
            search.close()
            main.post {
                if (!running || generation != discoveryGeneration || !needsConnection) return@post
                discovery = null; findingReaders = false
                foundReaders = result.getOrDefault(emptyList())
                discoveryMessage = when {
                    result.isFailure -> "Recherche indisponible. Vous pouvez saisir l’adresse du lecteur ci-dessous."
                    foundReaders.isEmpty() -> "Aucun lecteur trouvé. Vérifiez le Wi-Fi et le lanceur sur le PC, puis réessayez."
                    else -> "${foundReaders.size} lecteur(s) trouvé(s). Touchez celui que vous voulez utiliser."
                }
                changed(false)
            }
        }
    }

    private fun schedule() {
        main.removeCallbacks(poll)
        if (running && api != null) main.postDelayed(poll, if (connected) 900 else 2500)
    }

    private fun <T> submit(foreground: Boolean = true, isPoll: Boolean = false, block: () -> T, success: (T) -> Unit) {
        val generation = epoch
        worker.execute {
            val result = runCatching(block)
            main.post {
                if (!running || generation != epoch) return@post
                if (foreground) busy = false
                if (isPoll) polling = false
                result.fold(success, ::failure)
                schedule()
            }
        }
    }

    fun connect(input: String, code: String) {
        if (busy) return
        val endpoint = try { Endpoint.parse(input) } catch (error: IllegalArgumentException) {
            message = error.message.orEmpty(); changed(false); return
        }
        cancelDiscovery()
        busy = true; message = ""; changed(false)
        submit(block = {
            val token = endpoint.embeddedToken.ifEmpty { RemoteApi(endpoint).connect(code) }
            val client = RemoteApi(Endpoint(endpoint.base), token)
            Triple(client, client.state(), client.library())
        }) { (client, snapshot, catalog) ->
            api = client
            address = client.endpoint.base
            preferences.edit().putString("address", address).putString("token", client.token).apply()
            state = snapshot; library = catalog; connected = true; message = snapshot.error
            changed(true)
        }
    }

    fun disconnect() {
        cancelDiscovery()
        foundReaders = emptyList(); discoveryMessage = ""
        epoch++
        main.removeCallbacks(poll)
        api = null; state = null; library = null; connected = false; busy = false; polling = false; message = ""
        preferences.edit().remove("token").apply()
        changed(true)
    }

    fun refresh(reloadLibrary: Boolean = false) {
        val client = api ?: return
        if (!running || busy || polling) { schedule(); return }
        polling = true
        val fetchLibrary = reloadLibrary || library == null
        if (reloadLibrary) { busy = true; message = ""; changed(false) }
        submit(foreground = reloadLibrary, isPoll = true,
            block = { client.state() to if (fetchLibrary) client.library() else null }) { (snapshot, catalog) ->
            val structural = catalog != null || state?.revision != snapshot.revision || state?.active != snapshot.active
            if (!connected && message.startsWith("Connexion")) message = ""
            connected = true
            if (state == null || snapshot.revision >= state!!.revision) state = snapshot
            if (catalog != null) library = catalog
            if (snapshot.error.isNotEmpty()) message = snapshot.error
            changed(structural)
        }
    }

    fun command(action: String, values: Map<String, Any> = emptyMap()) {
        val client = api ?: return
        val snapshot = state ?: return
        if (!connected || busy) return
        main.removeCallbacks(poll)
        busy = true; message = ""; changed(false)
        submit(block = {
            try { client.command(action, snapshot.revision, values) to "" }
            catch (error: ApiException) {
                if (error.status != 409) throw error
                client.state() to "La lecture a changé. Son état a été actualisé ; réessayez votre commande."
            }
        }) { (next, note) ->
            state = next; connected = true; message = next.error.ifEmpty { note }; changed(true)
        }
    }

    private fun failure(error: Throwable) {
        if (error is ApiException && error.status == 401 && api != null) {
            preferences.edit().remove("token").apply()
            api = null; state = null; library = null; connected = false
            message = "Le lecteur a redémarré. Saisissez le nouveau code affiché sur le PC."
            changed(true)
        } else {
            if (error is ApiException) message = error.message.orEmpty()
            else if (error is IllegalArgumentException) message = error.message.orEmpty()
            else {
                connected = false
                message = "Connexion interrompue. Vérifiez que le lecteur est lancé et que les deux appareils partagent le même Wi-Fi."
            }
            changed(false)
        }
    }
}

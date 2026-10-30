package fr.portesimaginaire.remote

import android.app.Activity
import android.app.AlertDialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.view.inputmethod.InputMethodManager
import android.widget.*
import java.util.Locale

/** Interface Android native. Aucun navigateur ou WebView n’est embarqué. */
class MainActivity : Activity() {
    private val paper = Color.rgb(246, 242, 233)
    private val white = Color.rgb(255, 252, 246)
    private val green = Color.rgb(36, 79, 73)
    private val ink = Color.rgb(40, 61, 56)
    private val muted = Color.rgb(105, 113, 106)
    private val soft = Color.rgb(233, 238, 230)
    private val gold = Color.rgb(161, 107, 56)
    private lateinit var coordinator: RemoteCoordinator
    private lateinit var root: LinearLayout
    private lateinit var body: LinearLayout
    private lateinit var scroll: ScrollView
    private lateinit var connectionStatus: TextView
    private lateinit var notice: TextView
    private lateinit var libraryTab: Button
    private lateinit var playerTab: Button
    private var progress: ProgressBar? = null
    private var timing: TextView? = null
    private var audioStatus: TextView? = null
    private val controls = mutableListOf<Pair<View, () -> Boolean>>()
    private val selectedModes = mutableMapOf<String, String>()
    private var page = "library"
    private var openedSession = false
    private var screenBuilt = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page = savedInstanceState?.getString("page") ?: "library"
        coordinator = RemoteCoordinator(this, ::render)
        root = column().apply { setBackgroundColor(paper) }
        val header = row().apply { setPadding(dp(20), dp(12), dp(16), dp(12)); gravity = Gravity.CENTER_VERTICAL }
        val icon = ImageView(this).apply {
            setImageResource(R.drawable.ic_portal); background = rounded(green, 12)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        header.addView(icon, LinearLayout.LayoutParams(dp(38), dp(38)))
        val name = text("Les Portes\nde l’Imaginaire", 17, serif = true).apply { setPadding(dp(12), 0, 0, 0) }
        header.addView(name, LinearLayout.LayoutParams(0, -2, 1f))
        header.addView(button("Lecteur", primary = false) {
            if (!coordinator.needsConnection) confirm("Changer de lecteur ?", "La lecture continuera sur le lecteur actuel.") {
                coordinator.disconnect()
            }
        }.apply { textSize = 12f; minWidth = 0 }, LinearLayout.LayoutParams(dp(82), dp(46)))
        root.addView(header)
        connectionStatus = text("Connexion au lecteur…", 12, muted).apply { setPadding(dp(22), 0, dp(22), dp(10)) }
        root.addView(connectionStatus)
        notice = text("", 13, Color.rgb(116, 68, 44)).apply {
            setPadding(dp(18), dp(12), dp(18), dp(12)); setBackgroundColor(Color.rgb(255, 241, 226))
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        }
        root.addView(notice)
        scroll = ScrollView(this).apply { isFillViewport = true; clipToPadding = false }
        body = column().apply { setPadding(dp(20), dp(16), dp(20), dp(24)) }
        scroll.addView(body)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val navigation = row().apply { setPadding(dp(16), dp(6), dp(16), dp(8)) }
        libraryTab = button("Bibliothèque", false) { page = "library"; render(true); scroll.smoothScrollTo(0, 0) }
        playerTab = button("Lecture en cours", false) { page = "player"; render(true); scroll.smoothScrollTo(0, 0) }
        navigation.addView(libraryTab, LinearLayout.LayoutParams(0, dp(50), 1f))
        navigation.addView(playerTab, LinearLayout.LayoutParams(0, dp(50), 1f).apply { leftMargin = dp(8) })
        root.addView(navigation)
        root.setOnApplyWindowInsetsListener { view, insets ->
            if (Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.ime())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else {
                @Suppress("DEPRECATION")
                view.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                    insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            }
            insets
        }
        setContentView(root)
        render(true)
    }

    override fun onStart() { super.onStart(); coordinator.start() }
    override fun onStop() { coordinator.stop(); super.onStop() }
    override fun onDestroy() { coordinator.close(); super.onDestroy() }
    override fun onSaveInstanceState(outState: Bundle) { outState.putString("page", page); super.onSaveInstanceState(outState) }

    private fun render(structural: Boolean) {
        if (!::body.isInitialized || isDestroyed) return
        val state = coordinator.state
        if (!openedSession && state != null) {
            if (state.active) page = "player"
            openedSession = true
        }
        if (coordinator.needsConnection) { page = "connection"; openedSession = false }
        else if (page == "connection") page = if (state?.active == true) "player" else "library"
        if (structural || !screenBuilt) {
            val offset = scroll.scrollY
            body.removeAllViews(); controls.clear(); progress = null; timing = null; audioStatus = null
            when {
                page == "connection" -> connectionScreen()
                page == "player" && state?.active == true -> playerScreen(state)
                else -> libraryScreen()
            }
            screenBuilt = true
            scroll.post { scroll.scrollTo(0, offset) }
        }
        connectionStatus.text = when {
            coordinator.needsConnection -> "●  Connexion requise"
            coordinator.connected -> "●  Connecté au lecteur · ${coordinator.address.substringAfter("://")}"
            else -> "●  Recherche du lecteur…"
        }
        connectionStatus.setTextColor(if (coordinator.connected) green else muted)
        notice.text = coordinator.message
        notice.visibility = if (coordinator.message.isEmpty()) View.GONE else View.VISIBLE
        libraryTab.isEnabled = !coordinator.needsConnection
        playerTab.isEnabled = state?.active == true && !coordinator.needsConnection
        libraryTab.setTextColor(if (page == "library") green else muted)
        playerTab.setTextColor(if (page == "player") green else muted)
        controls.forEach { (view, enabled) -> view.isEnabled = !coordinator.busy && enabled(); view.alpha = if (view.isEnabled) 1f else .4f }
        updateProgress(state)
    }

    private fun connectionScreen() {
        body.addView(text("VOTRE TÉLÉCOMMANDE ANDROID", 10, gold, bold = true).apply { letterSpacing = .15f })
        space(body, 16)
        body.addView(text("Ouvrir la porte.", 36, serif = true))
        space(body, 12)
        body.addView(text("Retrouvez les histoires du lecteur et pilotez l’écoute depuis votre téléphone.", 15, muted))
        space(body, 26)
        val card = card(body)
        card.addView(text("Adresse du lecteur", 13, bold = true))
        val address = EditText(this).apply {
            hint = "192.168.1.20:8765"; setText(coordinator.address)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true); contentDescription = "Adresse du lecteur"; textSize = 16f
        }
        card.addView(address, matchWrap())
        space(card, 20)
        card.addView(text("Code affiché sur le PC", 13, bold = true))
        val code = EditText(this).apply {
            hint = "1234 5678"; inputType = InputType.TYPE_CLASS_NUMBER; setSingleLine(true)
            contentDescription = "Code à huit chiffres"; textSize = 20f; letterSpacing = .15f; isSaveEnabled = false
        }
        card.addView(code, matchWrap())
        space(card, 20)
        val connect = button("Se connecter au lecteur  →") {
            (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(code.windowToken, 0)
            coordinator.connect(address.text.toString(), code.text.toString())
        }
        card.addView(connect, LinearLayout.LayoutParams(-1, dp(52)))
        controls.add(connect to { true })
        space(body, 22)
        body.addView(text("Sur le PC, lancez Telecommande_Telephone.cmd. Les deux appareils doivent partager le même Wi-Fi. Le son est joué par le PC.", 13, muted))
        space(body, 12)
        body.addView(text("Vous pouvez aussi coller le lien complet affiché par le lecteur : le code ne sera alors pas nécessaire.", 12, muted))
    }

    private fun libraryScreen() {
        body.addView(text("LE TEMPS D’UNE HISTOIRE", 10, gold, bold = true).apply { letterSpacing = .15f })
        space(body, 14)
        body.addView(text("Où allons-nous\naujourd’hui ?", 35, serif = true))
        space(body, 10)
        body.addView(text("Choisissez une histoire. Installez-vous. Écoutez.", 14, muted))
        space(body, 20)
        val refresh = button("↻  Actualiser les audio", false) { coordinator.refresh(true) }
        body.addView(refresh, matchWrap()); controls.add(refresh to { coordinator.connected })
        val library = coordinator.library
        if (library == null) { body.addView(text("Chargement de la bibliothèque…", 14, muted)); return }
        library.books.forEachIndexed { index, book ->
            space(body, 16)
            val card = card(body)
            card.addView(text("LIVRE ${String.format(Locale.ROOT, "%02d", index + 1)}  ·  ✦", 10, gold, bold = true))
            space(card, 14)
            card.addView(text(book.title, 27, serif = true))
            if (book.author.isNotEmpty()) { space(card, 6); card.addView(text(book.author, 12, muted)) }
            if (book.description.isNotEmpty()) { space(card, 14); card.addView(text(book.description, 13, muted)) }
            space(card, 18)
            card.addView(text("Comment voulez-vous écouter ?", 12, muted))
            val modes = RadioGroup(this).apply { orientation = LinearLayout.VERTICAL }
            val selected = selectedModes[book.id] ?: book.modes.firstOrNull { it.id == "automatic" && it.complete }?.id ?: "interactive"
            var selection = book.modes.first { it.id == selected }
            val availability = text("", 12, muted)
            val start = button("Ouvrir cette histoire  →") {
                startStory(mapOf("kind" to "book", "id" to book.id, "mode" to selection.id))
            }
            fun updateMode() {
                availability.text = if (selection.complete) "Audio complet · ${selection.available}/${selection.total} fichiers prêts" else
                    "Audio incomplet · ${selection.available}/${selection.total} fichiers prêts. " +
                        if (selection.id == "automatic") "Préparez les fichiers sur le PC pour écouter en continu." else "Le texte et les choix restent disponibles."
                availability.setTextColor(if (selection.complete) green else muted)
                start.isEnabled = !coordinator.busy && coordinator.connected && (selection.id != "automatic" || selection.complete)
                start.alpha = if (start.isEnabled) 1f else .4f
            }
            book.modes.forEach { mode ->
                val radio = RadioButton(this).apply {
                    id = View.generateViewId(); text = if (mode.id == "automatic") "Écoute automatique · sans choix" else "Jeu à deux choix"
                    textSize = 13f; buttonTintList = ColorStateList.valueOf(green); minHeight = dp(46)
                    isChecked = mode.id == selected
                    setOnCheckedChangeListener { _, checked ->
                        if (checked) { selection = mode; selectedModes[book.id] = mode.id; updateMode() }
                    }
                }
                modes.addView(radio)
            }
            card.addView(modes); space(card, 10); card.addView(availability); space(card, 16)
            card.addView(start, LinearLayout.LayoutParams(-1, dp(52)))
            controls.add(start to { coordinator.connected && (selection.id != "automatic" || selection.complete) })
            updateMode()
        }
        space(body, 22)
        val adventures = button("Les aventures à personnaliser  +", false) { adventureDialog(library) }
        body.addView(adventures, matchWrap()); controls.add(adventures to { coordinator.connected })
        space(body, 14)
        body.addView(text("La lecture continue si vous verrouillez le téléphone ou quittez l’application.", 12, muted))
    }

    private fun startStory(values: Map<String, Any>) {
        val start = { page = "player"; coordinator.command("start", values) }
        if (coordinator.state?.active == true) confirm("Changer de lecture ?", "Remplacer l’histoire en cours par cette nouvelle écoute ?", start)
        else start()
    }

    private fun playerScreen(state: Snapshot) {
        body.addView(text(if (state.mode == "automatic") "ÉCOUTE AUTOMATIQUE · SANS CHOIX" else "HISTOIRE INTERACTIVE", 10, gold, bold = true))
        space(body, 12)
        body.addView(text(state.title, 30, serif = true))
        space(body, 12)
        body.addView(text("Passage ${state.passage} sur ${state.passages}", 13, muted))
        space(body, 20)
        val card = card(body)
        audioStatus = text("", 14, green, bold = true).apply { gravity = Gravity.CENTER }
        card.addView(audioStatus)
        space(card, 20)
        val transport = row().apply { gravity = Gravity.CENTER }
        val replay = button("↺", false) { coordinator.command("replay") }.apply { contentDescription = "Rejouer le passage"; textSize = 27f }
        val play = button("▶") { coordinator.command("resume") }.apply { contentDescription = "Lecture ou reprise"; textSize = 22f }
        val pause = button("Ⅱ", false) { coordinator.command("pause") }.apply { contentDescription = "Pause"; textSize = 25f }
        transport.addView(replay, LinearLayout.LayoutParams(0, dp(58), 1f))
        transport.addView(play, LinearLayout.LayoutParams(0, dp(64), 1.2f).apply { leftMargin = dp(12); rightMargin = dp(12) })
        transport.addView(pause, LinearLayout.LayoutParams(0, dp(58), 1f))
        card.addView(transport)
        controls.add(replay to { coordinator.connected })
        controls.add(play to { coordinator.connected && coordinator.state?.audioState != "playing" })
        controls.add(pause to { coordinator.connected && coordinator.state?.audioState == "playing" })
        space(card, 8)
        card.addView(text("Rejouer                 Lecture / reprise                 Pause", 10, muted).apply { gravity = Gravity.CENTER })
        space(card, 16)
        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply { max = 1000; progressTintList = ColorStateList.valueOf(green); contentDescription = "Progression du son" }
        card.addView(progress, LinearLayout.LayoutParams(-1, dp(8)))
        timing = text("", 11, muted)
        card.addView(timing)
        if (state.volumeSupported) {
            space(card, 16)
            val label = text("Volume · ${state.volume} %", 12, muted)
            card.addView(label)
            val volume = SeekBar(this).apply {
                max = 100; progress = state.volume; contentDescription = "Volume de l’histoire"
                progressTintList = ColorStateList.valueOf(green); thumbTintList = ColorStateList.valueOf(green)
                setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                    override fun onProgressChanged(bar: SeekBar?, value: Int, fromUser: Boolean) { label.text = getString(R.string.volume_label, value) }
                    override fun onStartTrackingTouch(bar: SeekBar?) {}
                    override fun onStopTrackingTouch(bar: SeekBar) { coordinator.command("volume", mapOf("value" to bar.progress)) }
                })
            }
            card.addView(volume, LinearLayout.LayoutParams(-1, dp(44)))
            controls.add(volume to { coordinator.connected })
        }
        space(card, 12)
        val more = row()
        val stop = button("■  Arrêter", false) { coordinator.command("stop") }
        val restart = button("Recommencer", false) {
            confirm("Recommencer l’histoire ?", "La lecture repartira au premier passage, dans le même mode.") { coordinator.command("restart") }
        }
        more.addView(stop, LinearLayout.LayoutParams(0, dp(48), 1f))
        more.addView(restart, LinearLayout.LayoutParams(0, dp(48), 1f).apply { leftMargin = dp(8) })
        card.addView(more)
        controls.add(stop to { coordinator.connected && coordinator.state?.stopped != true })
        controls.add(restart to { coordinator.connected })
        space(card, 12)
        card.addView(text("Le son est joué par le lecteur connecté.", 11, muted).apply { gravity = Gravity.CENTER })
        space(body, 18)
        val reading = card(body)
        reading.addView(text(state.scene, 24, serif = true))
        if (state.mode != "automatic" && state.choices.isNotEmpty()) {
            space(reading, 16); reading.addView(text(state.question, 14, bold = true))
            state.choices.forEach { choice ->
                space(reading, 10)
                val button = button("${choice.index + 1} · ${choice.text}", false) { coordinator.command("choose", mapOf("index" to choice.index)) }
                    .apply { gravity = Gravity.CENTER_VERTICAL or Gravity.START; minHeight = dp(52) }
                reading.addView(button, matchWrap()); controls.add(button to { coordinator.connected })
            }
        }
        if (state.canAdvance) {
            space(reading, 16)
            val advance = button("Poursuivre  →") { coordinator.command("advance") }
            reading.addView(advance, matchWrap()); controls.add(advance to { coordinator.connected })
        }
        space(reading, 16)
        val transcript = text(state.text, 17, serif = true).apply { visibility = View.GONE; setLineSpacing(dp(5).toFloat(), 1.15f); setTextIsSelectable(true) }
        val toggle = button("Lire le passage  +", false) {
            transcript.visibility = if (transcript.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
        reading.addView(toggle, matchWrap()); reading.addView(transcript)
    }

    private fun updateProgress(state: Snapshot?) {
        if (state == null) return
        audioStatus?.text = when {
            state.completed -> "Écoute terminée"
            state.stopped -> "Lecture arrêtée"
            state.audioState == "playing" -> "Lecture en cours"
            state.audioState == "paused" -> "En pause"
            state.audioState == "ready" -> "Passage terminé"
            else -> "Audio indisponible · lecture suspendue"
        }
        val audio = state.progress
        progress?.visibility = if (audio == null) View.GONE else View.VISIBLE
        timing?.visibility = if (audio == null) View.GONE else View.VISIBLE
        if (audio != null) {
            progress?.progress = if (audio.duration > 0) (audio.position * 1000 / audio.duration).toInt().coerceIn(0, 1000) else 0
            timing?.text = getString(R.string.playback_time, formatTime(audio.position), formatTime(audio.duration))
        }
    }

    private fun adventureDialog(library: Library) {
        val form = column().apply { setPadding(dp(22), dp(8), dp(22), dp(12)) }
        val fields = mutableMapOf<String, Pair<Spinner, List<Option>>>()
        val entries = listOf(Triple("id", "L’aventure", library.adventures),
            Triple("hero", "Votre héros", library.catalogs["hero"].orEmpty()),
            Triple("location", "Votre lieu", library.catalogs["location"].orEmpty()),
            Triple("item", "Votre objet", library.catalogs["item"].orEmpty()))
        entries.forEach { (key, label, options) ->
            form.addView(text(label, 13, bold = true))
            val spinner = Spinner(this).apply {
                adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Choisir…") + options.map { it.label })
                contentDescription = label; minimumHeight = dp(48)
            }
            form.addView(spinner, matchWrap()); space(form, 12); fields[key] = spinner to options
        }
        val container = ScrollView(this).apply { addView(form) }
        val dialog = AlertDialog.Builder(this).setTitle("Une aventure à votre image").setView(container)
            .setNegativeButton("Annuler", null).setPositiveButton("Commencer", null).create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                if (fields.values.any { it.first.selectedItemPosition == 0 }) {
                    Toast.makeText(this, "Choisissez une proposition dans chaque liste.", Toast.LENGTH_SHORT).show()
                } else {
                    val values = mutableMapOf<String, Any>("kind" to "adventure")
                    fields.forEach { (key, pair) -> values[key] = pair.second[pair.first.selectedItemPosition - 1].id }
                    dialog.dismiss(); startStory(values)
                }
            }
        }
        dialog.show()
    }

    private fun confirm(title: String, message: String, accepted: () -> Unit) {
        AlertDialog.Builder(this).setTitle(title).setMessage(message).setNegativeButton("Annuler", null)
            .setPositiveButton("Continuer") { _, _ -> accepted() }.show()
    }
    private fun dp(value: Int) = (value * resources.displayMetrics.density + .5f).toInt()
    private fun column() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun row() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
    private fun matchWrap() = LinearLayout.LayoutParams(-1, -2)
    private fun text(value: String, size: Int, color: Int = ink, bold: Boolean = false, serif: Boolean = false) = TextView(this).apply {
        text = value; textSize = size.toFloat(); setTextColor(color)
        typeface = Typeface.create(if (serif) "serif" else "sans-serif", if (bold) Typeface.BOLD else Typeface.NORMAL)
        setLineSpacing(dp(2).toFloat(), 1.1f)
    }
    private fun rounded(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat() }
    private fun button(label: String, primary: Boolean = true, action: () -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; textSize = 13f; setTextColor(if (primary) white else green)
        background = rounded(if (primary) green else soft, 12); setPadding(dp(14), dp(12), dp(14), dp(12))
        minHeight = dp(48); minimumHeight = dp(48); setOnClickListener { action() }
    }
    private fun card(parent: LinearLayout) = column().apply {
        background = rounded(white, 18); setPadding(dp(22), dp(22), dp(22), dp(22))
        parent.addView(this, matchWrap())
    }
    private fun space(parent: LinearLayout, height: Int) { parent.addView(View(this), LinearLayout.LayoutParams(1, dp(height))) }
    private fun formatTime(ms: Long): String = "${ms / 60000}:${String.format(Locale.ROOT, "%02d", (ms / 1000) % 60)}"
}

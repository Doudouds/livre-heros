'use strict';
const $ = id => document.getElementById(id);
const storageKey = 'imaginaire-remote-token';
let token = '';
try { token = localStorage.getItem(storageKey) || ''; } catch (_) { /* Stockage privé indisponible. */ }
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('connexion')) {
  token = fragment.get('connexion');
  try { localStorage.setItem(storageKey, token); } catch (_) { /* Connexion valable pour cet onglet. */ }
  history.replaceState(null, '', location.pathname);
}
let state = null, library = null, connected = false, busy = false, page = 'library';
let lastRendered = -1, timer = null, polling = false;

function notice(message = '') {
  $('notice').textContent = message;
  $('notice').hidden = !message;
}

function connection(ok, message) {
  connected = ok;
  $('connection').textContent = message;
  $('connection').className = `connection ${ok ? 'connected' : 'offline'}`;
  updateButtons();
}

async function api(path, payload, authenticate = true) {
  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(), 12000);
  try {
    const response = await fetch(path, {
      method: payload === undefined ? 'GET' : 'POST',
      headers: { ...(authenticate ? { 'X-Remote-Token': token } : {}), ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: abort.signal, cache: 'no-store', credentials: 'omit'
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || 'Commande refusée.');
      error.status = response.status;
      throw error;
    }
    return data;
  } finally { clearTimeout(timeout); }
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showPage(next) {
  page = next;
  $('library-view').hidden = next !== 'library';
  $('player-view').hidden = next !== 'player';
  $('library-nav').classList.toggle('selected', next === 'library');
  $('player-nav').classList.toggle('selected', next === 'player');
}

function updateButtons() {
  const locked = busy || !connected;
  document.querySelectorAll('#books button, #adventures button').forEach(button => {
    button.disabled = locked || button.dataset.unavailable === 'true';
  });
  $('refresh-library').disabled = locked;
  $('player-nav').disabled = !state?.active;
  const active = !!state?.active;
  const playing = state?.audio_state === 'playing';
  $('resume').disabled = locked || !active || playing;
  $('pause').disabled = locked || !active || !playing;
  $('replay').disabled = locked || !active;
  $('restart').disabled = locked || !active;
  $('stop').disabled = locked || !active || state?.stopped;
  $('advance').disabled = locked;
  $('volume').disabled = locked || !state?.volume_supported;
  document.querySelectorAll('#choices button').forEach(button => { button.disabled = locked; });
}

function renderLibrary() {
  $('books').replaceChildren();
  library.books.forEach((book, index) => {
    const card = element('article', undefined, 'book panel');
    const top = element('div', undefined, 'book-top');
    top.append(element('span', `LIVRE ${String(index + 1).padStart(2, '0')}`, 'book-number'), element('span', '✦', 'book-symbol'));
    card.append(top, element('h3', book.title), element('p', book.author, 'author'), element('p', book.description, 'description'));
    const modes = element('fieldset', undefined, 'mode-options');
    modes.append(element('legend', 'Comment voulez-vous écouter ?'));
    const availability = element('p', '', 'availability');
    const start = element('button', 'Ouvrir cette histoire →', 'primary');
    start.type = 'button';
    let selected = book.modes.automatic?.complete ? 'automatic' : 'interactive';
    function update() {
      const coverage = book.modes[selected];
      availability.textContent = coverage.complete ? `Audio complet · ${coverage.available}/${coverage.total} fichiers prêts` :
        `Audio incomplet · ${coverage.available}/${coverage.total} fichiers prêts. ${selected === 'automatic' ? 'Préparez les fichiers sur le PC pour écouter en continu.' : 'Le texte et les choix restent disponibles.'}`;
      availability.classList.toggle('complete', coverage.complete);
      start.dataset.unavailable = String(selected === 'automatic' && !coverage.complete);
      updateButtons();
    }
    for (const mode of Object.keys(book.modes)) {
      const label = element('label', undefined, 'mode-option');
      const input = element('input');
      input.type = 'radio'; input.name = `mode-${book.id}`; input.value = mode; input.checked = mode === selected;
      input.addEventListener('change', () => { selected = mode; update(); });
      label.append(input, document.createTextNode(mode === 'automatic' ? 'Écoute automatique' : 'Jeu à deux choix'));
      modes.append(label);
    }
    start.addEventListener('click', () => startStory({ kind: 'book', id: book.id, mode: selected }));
    card.append(modes, availability, start);
    $('books').append(card);
    update();
  });
  const form = element('form', undefined, 'adventure-form');
  const fields = {};
  for (const [name, label, records] of [['id', 'L’aventure', library.adventures], ['hero', 'Votre héros', library.catalogs.hero],
    ['location', 'Votre lieu', library.catalogs.location], ['item', 'Votre objet', library.catalogs.item]]) {
    const wrapper = element('label', label);
    const select = element('select'); select.name = name; select.required = true;
    select.append(new Option('Choisir…', ''));
    for (const record of records) select.append(new Option(record.label || record.title, record.id));
    fields[name] = select; wrapper.append(select); form.append(wrapper);
  }
  const submit = element('button', 'Commencer l’aventure →', 'primary'); submit.type = 'submit';
  form.append(element('p', 'Les audio disponibles sont joués. Un passage sans audio reste accessible en texte.'), submit);
  form.addEventListener('submit', event => {
    event.preventDefault();
    const spec = { kind: 'adventure' };
    for (const [key, field] of Object.entries(fields)) spec[key] = field.value;
    startStory(spec);
  });
  $('adventures').replaceChildren(form);
  updateButtons();
}

async function startStory(spec) {
  if (state?.active && !await confirmAction('Remplacer l’histoire en cours par cette nouvelle écoute ?')) return;
  if (await command('start', spec)) {
    showPage('player');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function confirmAction(message) {
  const dialog = $('confirmation');
  if (dialog.open) return Promise.resolve(false);
  $('confirmation-message').textContent = message;
  dialog.returnValue = 'cancel';
  return new Promise(resolve => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
    dialog.showModal();
  });
}

function formatTime(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

function renderState(next) {
  if (state && next.revision < state.revision) return;
  const firstState = state === null;
  state = next;
  $('player-nav').disabled = !next.active;
  if (!next.active) { showPage('library'); updateButtons(); return; }
  if (firstState) showPage('player');
  if (lastRendered !== next.revision) {
    lastRendered = next.revision;
    $('story-title').textContent = next.title;
    $('scene-title').textContent = next.scene_title;
    $('story-text').textContent = next.text;
    $('playback-mode').textContent = next.mode === 'automatic' ? 'ÉCOUTE AUTOMATIQUE · SANS CHOIX' : 'HISTOIRE INTERACTIVE';
    $('passage-label').textContent = `Passage ${next.passage} sur ${next.passages}`;
    $('audio-status').textContent = next.completed ? 'Écoute terminée' : next.stopped ? 'Lecture arrêtée' :
      ({ playing: 'Lecture en cours', paused: 'En pause', ready: 'Passage terminé', unavailable: 'Audio indisponible · lecture suspendue' }[next.audio_state] || 'Prêt à écouter');
    $('choices').replaceChildren();
    for (const choice of next.choices) {
      const button = element('button', `${choice.index + 1} · ${choice.text}`, 'choice'); button.type = 'button';
      button.addEventListener('click', () => command('choose', { index: choice.index }));
      $('choices').append(button);
    }
    $('question').textContent = next.choices.length ? next.question : '';
    $('question').hidden = !next.choices.length;
    $('advance').hidden = !next.can_advance;
    $('decisions').hidden = !next.choices.length && !next.can_advance;
    $('volume-control').hidden = !next.volume_supported;
    $('volume-help').hidden = next.volume_supported;
    $('volume').value = next.volume ?? 70;
    $('volume-label').textContent = `${next.volume ?? 70} %`;
  }
  $('time-progress').hidden = !next.progress;
  if (next.progress) {
    $('audio-progress').max = Math.max(1, next.progress.duration_ms);
    $('audio-progress').value = next.progress.position_ms;
    $('position').textContent = formatTime(next.progress.position_ms);
    $('duration').textContent = formatTime(next.progress.duration_ms);
  }
  if (next.error) notice(next.error);
  updateButtons();
}

async function command(action, extra = {}) {
  if (busy || !connected || !state) return false;
  busy = true; notice(); updateButtons();
  try {
    renderState(await api('/api/command', { ...extra, action, revision: state.revision }));
    return true;
  } catch (error) {
    notice(error.status ? error.message : 'Connexion interrompue. Vérifiez l’état du lecteur avant de réessayer.');
    if (!error.status) connection(false, 'Lecteur déconnecté');
    await refresh();
    return false;
  } finally { busy = false; updateButtons(); }
}

async function refresh() {
  if (!token) { $('login').hidden = false; connection(false, 'Connexion requise'); return; }
  try {
    const next = await api('/api/state');
    if (!library) { library = await api('/api/library'); renderLibrary(); }
    $('login').hidden = true; $('app').hidden = false;
    connection(true, 'Connecté au PC');
    renderState(next);
  } catch (error) {
    if (error.status === 401) {
      token = ''; try { localStorage.removeItem(storageKey); } catch (_) { /* Rien à effacer. */ }
      state = null; library = null; lastRendered = -1;
      $('login').hidden = false; $('app').hidden = true;
      connection(false, 'Connexion requise');
      notice('Saisissez le code du lancement actuel affiché sur le PC.');
    } else connection(false, 'Lecteur déconnecté · nouvel essai…');
  }
}

async function poll() {
  if (polling) return;
  polling = true;
  try { if (!busy) await refresh(); }
  finally {
    polling = false;
    clearTimeout(timer);
    timer = setTimeout(poll, connected ? 800 : 1800);
  }
}

$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); notice();
  const button = event.submitter; button.disabled = true;
  try {
    const result = await api('/api/connect', { code: $('access-code').value.replace(/\s/g, '') }, false);
    token = result.token;
    try { localStorage.setItem(storageKey, token); } catch (_) { /* Connexion en mémoire. */ }
    await refresh();
  } catch (error) { notice(error.status ? error.message : 'Le PC ne répond pas. Vérifiez le réseau et le lanceur.'); }
  finally { button.disabled = false; }
});
$('library-nav').addEventListener('click', () => showPage('library'));
$('player-nav').addEventListener('click', () => showPage('player'));
$('refresh-library').addEventListener('click', async () => {
  if (busy) return;
  busy = true; updateButtons();
  try { library = await api('/api/library'); renderLibrary(); notice(); }
  catch (error) { notice(error.message); }
  finally { busy = false; updateButtons(); }
});
for (const action of ['resume', 'pause', 'replay', 'stop', 'advance']) $(action).addEventListener('click', () => command(action));
$('restart').addEventListener('click', async () => { if (await confirmAction('Recommencer cette histoire depuis le début ?')) command('restart'); });
$('volume').addEventListener('input', () => { $('volume-label').textContent = `${$('volume').value} %`; });
$('volume').addEventListener('change', () => command('volume', { value: Number($('volume').value) }));
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) { clearTimeout(timer); poll(); }
});
poll();

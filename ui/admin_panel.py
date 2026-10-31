"""Atelier PC : catalogue audio, nouvelles prises et import assisté par Codex."""
import json
from pathlib import Path
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from audio.audio_player import LocalAudioPlayer
from engine.audio_admin import AudioInventory, AdminJobs, codex_executable, hidden_process_options, read_optional, within
from audio.tts_batch import digest, file_hash, receipt_matches, receipt_path
from engine.content import Content
from engine.story_import import StoryImports


STATUS = {'ready':'Prêt', 'missing':'À générer', 'failed':'En échec', 'invalid':'À vérifier', 'running':'En cours'}
JOB_STATUS = {'running':'En cours', 'succeeded':'Terminé', 'failed':'En échec', 'stopped':'Arrêté', 'interrupted':'Interrompu'}
EMOTIONS = dict(neutral='Neutre',joie='Joie',tristesse='Tristesse',colere='Colère',peur='Peur',
                emerveillement='Émerveillement',tendresse='Tendresse',surprise='Surprise',
                determination='Détermination',soulagement='Soulagement',
                soulagement_apaisement='Soulagement apaisé',malice='Malice')


class AdminPanel:
    def __init__(self, owner, jobs=None):
        self.owner = owner
        self.root = owner.content.root
        self.jobs = jobs or AdminJobs(self.root)
        self.inventory = AudioInventory(self.root)
        self.imports = StoryImports(self.root)
        self.audio = LocalAudioPlayer(self.root,lead_in_ms=0)
        self.window = tk.Toplevel(owner.root)
        self.window.transient(owner.root)
        self.window.title('Administration des contes')
        self.window.geometry('1240x850')
        self.window.minsize(940,660)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.rows_by_id = {}
        self.draft_ids = []
        self.draft_id = None
        self.poll_id = None
        self.last_finished = None
        self.last_log = None
        self.last_refresh = 0
        self.last_detail = None
        self.book = tk.StringVar()
        self.mode = tk.StringVar(value='Jeu interactif')
        outer = ttk.Frame(self.window,padding=18)
        outer.pack(fill='both',expand=True)
        heading = ttk.Frame(outer)
        heading.pack(fill='x')
        ttk.Label(heading,text='Atelier des contes',font=('Georgia',24)).pack(side='left')
        ttk.Button(heading,text='Actualiser',command=self.refresh_all,style='Audio.TButton').pack(side='right')
        ttk.Label(outer,text='Préparer les textes, suivre les deux versions et écouter chaque prise.',style='Sub.TLabel').pack(anchor='w',pady=(4,12))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both',expand=True)
        audio_tab = ttk.Frame(self.tabs,padding=12)
        import_tab = ttk.Frame(self.tabs,padding=12)
        self.tabs.add(audio_tab,text='Audio des contes')
        self.tabs.add(import_tab,text='Importer un conte')
        self._audio_tab(audio_tab)
        self._import_tab(import_tab)
        footer = ttk.Frame(outer)
        footer.pack(side='bottom',fill='x',pady=(10,0),before=self.tabs)
        self.job_text = tk.StringVar(value='Aucune tâche en cours.')
        ttk.Label(footer,textvariable=self.job_text,wraplength=850).pack(side='left',fill='x',expand=True)
        self.stop_button = ttk.Button(footer,text='Arrêter la tâche',command=self.jobs.stop,style='Audio.TButton')
        self.stop_button.pack(side='right')
        self.resume_button = ttk.Button(footer,text='Reprendre',command=self.resume,style='Audio.TButton')
        self.resume_button.pack(side='right',padx=6)
        self.refresh_all()
        self.poll()

    def _audio_tab(self, frame):
        bar = ttk.Frame(frame)
        bar.pack(fill='x',pady=(0,10))
        ttk.Label(bar,text='Conte').pack(side='left')
        self.book_combo = ttk.Combobox(bar,textvariable=self.book,state='readonly',width=48)
        self.book_combo.pack(side='left',padx=(8,20))
        self.book_combo.bind('<<ComboboxSelected>>',lambda event:self.refresh_rows())
        self.mode_combo = ttk.Combobox(bar,textvariable=self.mode,values=['Jeu interactif','Écoute automatique'],state='readonly',width=21)
        self.mode_combo.pack(side='left')
        self.mode_combo.bind('<<ComboboxSelected>>',lambda event:self.refresh_rows())
        self.counts = tk.StringVar()
        ttk.Label(frame,textvariable=self.counts,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,8))
        panes = ttk.Panedwindow(frame,orient='horizontal')
        panes.pack(fill='both',expand=True)
        left,right = ttk.Frame(panes),ttk.Frame(panes,padding=(14,0,0,0))
        panes.add(left,weight=3)
        panes.add(right,weight=4)
        self.tree = ttk.Treeview(left,columns=('passage','variant','status'),show='headings',selectmode='browse',height=13)
        for key,title,width in (('passage','Passage',180),('variant','Version',125),('status','Audio',95)):
            self.tree.heading(key,text=title)
            self.tree.column(key,width=width,minwidth=65)
        scroll = ttk.Scrollbar(left,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.tree.pack(fill='both',expand=True)
        for key,color in (('ready','#247149'),('failed','#ad3333'),('invalid','#a56813'),('running','#245ab0'),('missing','#666666')):
            self.tree.tag_configure(key,foreground=color)
        self.tree.bind('<<TreeviewSelect>>',lambda event:self.show_selected())
        self.tree.bind('<Double-1>',lambda event:self.show_selected())
        self.detail_title = tk.StringVar(value='Sélectionner un morceau')
        ttk.Label(right,textvariable=self.detail_title,font=('Segoe UI',13,'bold'),wraplength=560).pack(anchor='w')
        self.detail_status = tk.StringVar()
        ttk.Label(right,textvariable=self.detail_status,wraplength=560).pack(anchor='w',pady=(4,8))
        detail_tabs = ttk.Notebook(right,height=220)
        detail_tabs.pack(fill='both',expand=True)
        detail_frame = ttk.Frame(detail_tabs)
        portions_frame = ttk.Frame(detail_tabs)
        history_frame = ttk.Frame(detail_tabs)
        journal_frame = ttk.Frame(detail_tabs)
        detail_tabs.add(detail_frame,text='Texte et tons')
        detail_tabs.add(portions_frame,text='Portions à reprendre')
        detail_tabs.add(history_frame,text='Historique · 10 prises')
        detail_tabs.add(journal_frame,text='Journal de la tâche')
        self.detail = self._text(detail_frame)
        self._portions_tab(portions_frame)
        self._history_tab(history_frame)
        self.journal = self._text(journal_frame)
        actions = ttk.Frame(right)
        actions.pack(fill='x',pady=(8,0))
        self.listen_button = ttk.Button(actions,text='Écouter',command=self.listen,style='Audio.TButton')
        self.listen_button.pack(side='left')
        ttk.Button(actions,text='Arrêter l’écoute',command=self.audio.stop,style='Audio.TButton').pack(side='left',padx=5)
        self.generate_button = ttk.Button(actions,text='Générer ce morceau',command=self.generate_selected,style='Audio.TButton')
        self.generate_button.pack(side='left')
        self.regenerate_button = ttk.Button(right,text='Refaire tout le segment',command=self.regenerate_selected,style='Audio.TButton')
        self.regenerate_button.pack(fill='x',pady=(8,0))
        ttk.Label(right,text='Pour ne refaire qu’un passage, ouvrir « Portions à reprendre ». L’historique conserve 10 prises validées, version actuelle comprise.',wraplength=560,style='Sub.TLabel').pack(anchor='w',pady=(6,0))
        bottom = ttk.Frame(frame)
        bottom.pack(side='bottom',fill='x',pady=(12,0),before=panes)
        self.first_button = ttk.Button(bottom,text='Générer les premiers audios · 2 modes',command=self.generate_first,style='Audio.TButton')
        self.first_button.pack(side='left')
        self.approve_button = ttk.Button(bottom,text='Valider les premiers audios écoutés',command=self.approve,style='Audio.TButton')
        self.approve_button.pack(side='left',padx=8)
        self.all_button = ttk.Button(bottom,text='Compléter les deux versions',command=self.generate_all,style='Audio.TButton')
        self.all_button.pack(side='left')

    def _portions_tab(self, frame):
        ttk.Label(frame,text='Choisir une portion ; Ctrl + clic pour en choisir plusieurs.',wraplength=560).pack(anchor='w',pady=6)
        self.portion_tree = ttk.Treeview(frame,columns=('number','tone','text'),show='headings',selectmode='extended',height=3)
        for key,title,width in (('number','N°',35),('tone','Ton',105),('text','Texte',350)):
            self.portion_tree.heading(key,text=title)
            self.portion_tree.column(key,width=width,minwidth=30)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=self.portion_tree.yview)
        self.portion_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.portion_tree.pack(fill='both',expand=True)
        self.portion_tree.bind('<<TreeviewSelect>>',lambda event:self.show_portions())
        actions = ttk.Frame(frame)
        actions.pack(fill='x',pady=6)
        self.listen_portion_button = ttk.Button(actions,text='Écouter la portion',command=self.listen_portion,style='Audio.TButton')
        self.listen_portion_button.pack(side='left')
        self.regenerate_portions_button = ttk.Button(actions,text='Refaire la sélection',command=self.regenerate_portions,style='Audio.TButton')
        self.regenerate_portions_button.pack(side='left',padx=6)
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill='both',expand=True)
        self.portion_text = self._text(text_frame)
        self.portion_text.configure(height=4)

    def _history_tab(self, frame):
        ttk.Label(frame,text='Versions validées du segment. Une restauration repasse les contrôles audio.',wraplength=560).pack(anchor='w',pady=6)
        self.history_tree = ttk.Treeview(frame,columns=('date','scope','status'),show='headings',selectmode='browse',height=6)
        for key,title,width in (('date','Date',145),('scope','Reprise',220),('status','Version',95)):
            self.history_tree.heading(key,text=title)
            self.history_tree.column(key,width=width,minwidth=60)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.history_tree.pack(fill='both',expand=True)
        self.history_tree.bind('<<TreeviewSelect>>',lambda event:self.update_buttons())
        actions = ttk.Frame(frame)
        actions.pack(fill='x',pady=8)
        self.listen_take_button = ttk.Button(actions,text='Écouter cette prise',command=self.listen_take,style='Audio.TButton')
        self.listen_take_button.pack(side='left')
        self.restore_button = ttk.Button(actions,text='Restaurer cette prise',command=self.restore_selected_take,style='Audio.TButton')
        self.restore_button.pack(side='left',padx=6)
        self.take_rows = {}
        self.take_signature = None
        self.portion_segment = None

    def _import_tab(self, frame):
        ttk.Label(frame,text='Un texte fidèle, des choix et des voix',font=('Georgia',18)).pack(anchor='w')
        ttk.Label(frame,text='Codex prépare un brouillon avec les passages, deux choix par étape et les tons. Vous le relisez avant de l’ajouter à la bibliothèque.',wraplength=1050,style='Sub.TLabel').pack(anchor='w',pady=(4,10))
        form = ttk.Frame(frame)
        form.pack(fill='x')
        form.columnconfigure(1,weight=1)
        self.import_title,self.import_author = tk.StringVar(),tk.StringVar()
        for row,label,var in ((0,'Titre du conte',self.import_title),(1,'Auteur(s)',self.import_author)):
            ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',padx=(0,12),pady=4)
            ttk.Entry(form,textvariable=var).grid(row=row,column=1,sticky='ew',pady=4)
        draft_bar = ttk.Frame(frame)
        draft_bar.pack(fill='x',pady=(10,6))
        ttk.Label(draft_bar,text='Brouillons locaux').pack(side='left')
        self.draft_combo = ttk.Combobox(draft_bar,state='readonly',width=55)
        self.draft_combo.pack(side='left',padx=8)
        self.draft_combo.bind('<<ComboboxSelected>>',self.load_draft)
        ttk.Button(draft_bar,text='Charger un .txt',command=self.load_text,style='Audio.TButton').pack(side='right')
        self.import_tabs = ttk.Notebook(frame)
        self.import_tabs.pack(fill='both',expand=True)
        source_frame,preview_frame = ttk.Frame(self.import_tabs),ttk.Frame(self.import_tabs)
        self.import_tabs.add(source_frame,text='Texte intégral à importer')
        self.import_tabs.add(preview_frame,text='Brouillon préparé · à relire')
        self.source = self._text(source_frame,readonly=False)
        self.preview = self._text(preview_frame)
        self.codex_status = tk.StringVar(value='Codex CLI : '+('installé sur ce PC' if codex_executable() else 'installation requise'))
        ttk.Label(frame,textvariable=self.codex_status,wraplength=1050).pack(anchor='w',pady=(8,4))
        ttk.Label(frame,text='« Préparer avec Codex » utilise votre connexion Codex et transmet le texte au service. Le brouillon reste local ; aucun audio n’est lancé pendant cette préparation.',wraplength=1050,style='Sub.TLabel').pack(anchor='w')
        actions = ttk.Frame(frame)
        actions.pack(fill='x',pady=(8,0))
        self.save_draft_button = ttk.Button(actions,text='Enregistrer un brouillon',command=self.save_draft,style='Audio.TButton')
        actions.columnconfigure(0,weight=1)
        actions.columnconfigure(1,weight=1)
        self.save_draft_button.grid(row=0,column=0,sticky='ew',padx=(0,6),pady=3)
        self.codex_button = ttk.Button(actions,text='Préparer avec Codex',command=self.prepare_import,style='Audio.TButton')
        self.codex_button.grid(row=0,column=1,sticky='ew',padx=(6,0),pady=3)
        self.publish_button = ttk.Button(actions,text='Intégrer le brouillon relu',command=self.publish_import,style='Audio.TButton')
        self.publish_button.grid(row=1,column=0,sticky='ew',padx=(0,6),pady=3)
        ttk.Button(actions,text='Vérifier la connexion Codex',command=self.check_codex,style='Audio.TButton').grid(row=1,column=1,sticky='ew',padx=(6,0),pady=3)

    @staticmethod
    def _text(frame, readonly=True):
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side='right',fill='y')
        text = tk.Text(frame,wrap='word',font=('Segoe UI',11),padx=10,pady=10,height=10,undo=not readonly,yscrollcommand=scroll.set)
        scroll.configure(command=text.yview)
        text.pack(fill='both',expand=True)
        if readonly:
            text.configure(state='disabled')
        return text

    @staticmethod
    def put(widget, value):
        widget.configure(state='normal')
        widget.delete('1.0','end')
        widget.insert('1.0',value)
        widget.configure(state='disabled')

    def selected_book(self):
        return self.book_ids[self.book_combo.current()] if self.book_combo.current()>=0 else None

    def selected(self):
        selected = self.tree.selection()
        return self.rows_by_id.get(selected[0]) if selected else None

    def refresh_all(self):
        try:
            self.inventory.cache.clear()
            current = self.selected_book() if hasattr(self,'book_ids') else None
            books = self.inventory.books()
            self.book_ids = list(books)
            self.book_combo.configure(values=[b['title'] for b in books.values()])
            if self.book_ids:
                self.book_combo.current(self.book_ids.index(current) if current in self.book_ids else 0)
            self.refresh_drafts()
            self.refresh_rows()
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showerror('Administration',str(exc),parent=self.window)

    def refresh_rows(self):
        book = self.selected_book()
        if not book:
            self.counts.set('Aucun conte balisé. Utiliser l’onglet Importer un conte pour en préparer un.')
            return
        selection = self.tree.selection()
        mode = self.mode.get()=='Écoute automatique'
        rows = self.inventory.rows(book,mode)
        state = self.jobs.snapshot()
        if self.jobs.busy and state.get('intent',{}).get('book_id') == book:
            specs = state.get('commands',[])
            active = specs[min(state.get('command_index',0),len(specs)-1)] if specs else {}
            progress = read_optional(active.get('report',''))
            running = {r['segment_id']:r for r in progress.get('segments',[]) if r.get('status')=='generating'}
            for row in rows:
                record = running.get(row['plan']['segment_id'])
                if record:
                    row['status'] = 'running'
                    row['reason'] = 'Génération et contrôle en cours.'
        self.rows_by_id = {r['plan']['segment_id']:r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for key,row in self.rows_by_id.items():
            plan = row['plan']
            self.tree.insert('', 'end',iid=key,values=(str(row['rank'])+'. '+plan['title'],row['variant'],STATUS[row['status']]),tags=(row['status'],))
        ready = sum(r['status']=='ready' for r in rows)
        self.counts.set(f'{ready} / {len(rows)} audios prêts · '+('écoute sans choix' if mode else 'toutes les variantes des deux choix'))
        if selection and selection[0] in self.rows_by_id:
            self.tree.selection_set(selection[0])
        elif rows:
            self.tree.selection_set(rows[0]['plan']['segment_id'])
        self.show_selected()
        self.update_buttons()

    def show_selected(self):
        row = self.selected()
        if not row:
            return
        plan = row['plan']
        self.detail_title.set(f'{row["rank"]}. {plan["title"]} · {row["variant"]}')
        self.detail_status.set(STATUS[row['status']]+' · '+row['reason']+
                               (f' · {row["seconds"]:.1f} s' if row['seconds'] else ''))
        value = '\n\n'.join('['+EMOTIONS.get(s['emotion'],s['emotion'])+' · '+s['speaker']+']\n'+s['text'] for s in plan['spans'])
        if value != self.last_detail:
            self.put(self.detail,value)
            self.last_detail = value
        self.refresh_portions_and_history(row)
        self.update_buttons()

    def refresh_portions_and_history(self, row):
        plan = row['plan']
        portion_signature = (plan['segment_id'],digest(plan['spans']))
        if self.portion_segment != portion_signature:
            self.portion_tree.delete(*self.portion_tree.get_children())
            for number,span in enumerate(plan['spans'],1):
                self.portion_tree.insert('','end',iid=str(number),values=(number,EMOTIONS.get(span['emotion'],span['emotion']),' '.join(span['text'].split())))
            self.portion_segment = portion_signature
            self.show_portions()
        proof_path = receipt_path(plan['output_file'])
        proof = read_optional(proof_path)
        directory = self.root/'audio/experiments'/plan['book']/'cache/previous_versions'/proof.get('identity','missing')
        signature = (plan['segment_id'],proof_path.stat().st_mtime_ns if proof_path.exists() else None,
                     directory.stat().st_mtime_ns if directory.exists() else None)
        if signature != self.take_signature:
            selection = self.history_tree.selection()
            self.take_rows = {v['key']:v for v in self.inventory.takes(plan)}
            self.history_tree.delete(*self.history_tree.get_children())
            for key,version in self.take_rows.items():
                metadata = version['proof']
                portions = metadata.get('regenerated_spans')
                scope = 'Portion(s) '+', '.join(str(n+1) for n in portions) if portions else ('Segment entier' if metadata.get('regeneration_request') else 'Version initiale')
                self.history_tree.insert('','end',iid=key,values=(datetime.fromtimestamp(version['time']).strftime('%d/%m/%Y %H:%M'),scope,'Actuelle' if version['current'] else 'Conservée'))
            if self.take_rows:
                self.history_tree.selection_set(selection[0] if selection and selection[0] in self.take_rows else next(iter(self.take_rows)))
            self.take_signature = signature

    def show_portions(self):
        row = self.selected()
        numbers = sorted(int(n) for n in self.portion_tree.selection())
        text = '\n\n'.join(row['plan']['spans'][n-1]['text'] for n in numbers) if row else ''
        self.put(self.portion_text,text or 'Sélectionner la ou les portions à reprendre. Les autres resteront identiques.')
        self.update_buttons()

    def selected_take(self):
        selected = self.history_tree.selection()
        return self.take_rows.get(selected[0]) if selected else None

    def update_buttons(self):
        busy = self.jobs.busy
        row = self.selected()
        book = self.selected_book()
        valid = bool(row and row['status']=='ready')
        self.listen_button.configure(state='normal' if valid and not busy else 'disabled')
        self.generate_button.configure(state='normal' if row and not busy and not valid else 'disabled')
        self.regenerate_button.configure(state='normal' if valid and not busy else 'disabled')
        portions = self.portion_tree.selection()
        self.listen_portion_button.configure(state='normal' if valid and not busy and len(portions)==1 else 'disabled')
        self.regenerate_portions_button.configure(state='normal' if valid and not busy and portions else 'disabled')
        take = self.selected_take()
        self.listen_take_button.configure(state='normal' if take and not busy else 'disabled')
        self.restore_button.configure(state='normal' if take and not take['current'] and valid and not busy else 'disabled')
        for button in (self.first_button,self.all_button):
            button.configure(state='normal' if book and not busy else 'disabled')
        approved = self.inventory.preview_approved(book) if book else True
        self.all_button.configure(state='normal' if book and approved and not busy else 'disabled')
        self.approve_button.configure(state='normal' if book and not approved and not busy else 'disabled')
        self.approve_button.configure(text='Premiers audios validés' if approved else 'Valider les premiers audios écoutés')
        for button in (self.save_draft_button,self.codex_button):
            button.configure(state='disabled' if busy else 'normal')
        request = read_optional(self.imports.draft(self.draft_id)/'request.json') if self.draft_id else {}
        self.publish_button.configure(state='normal' if not busy and request.get('status')=='prepared' else 'disabled')

    def _stop_players(self):
        self.audio.stop()
        if self.owner.audio.state != 'unavailable':
            self.owner.admin_stopped_audio = True
            self.owner.audio.stop()
            self.owner.update_audio_controls()

    def listen(self):
        row = self.selected()
        if row:
            self.audio.audio_root = Path(row['plan']['output_file']).parent
            if not self.audio.play(row['plan']['segment_id'],row['plan']['output_file']):
                messagebox.showerror('Écoute',self.audio.last_error or 'Audio indisponible.',parent=self.window)

    def listen_portion(self):
        row = self.selected()
        selected = self.portion_tree.selection()
        if row and len(selected)==1:
            try:
                self.play_path(self.inventory.portion_file(row['plan'],int(selected[0])))
            except (OSError,ValueError,KeyError) as exc:
                messagebox.showerror('Écoute de la portion',str(exc),parent=self.window)

    def play_path(self, path):
        self.audio.audio_root = path.parent
        if not self.audio.play(path.stem,str(path)):
            raise ValueError(self.audio.last_error or 'Audio indisponible.')

    def listen_take(self):
        take = self.selected_take()
        if take:
            try:
                path = within(self.root,take['file'])
                if file_hash(path)!=take['proof']['sha256'] or not receipt_matches(path,take['proof']['identity']):
                    raise ValueError('Cette prise a changé ; actualiser l’historique.')
                self.play_path(path)
            except (OSError,ValueError) as exc:
                messagebox.showerror('Écoute historique',str(exc),parent=self.window)

    def regenerate_portions(self):
        row = self.selected()
        if row and self.portion_tree.selection():
            self.audio_job(automatic=row['automatic'],segment_id=row['plan']['segment_id'],regenerate=True,
                           spans=sorted(int(n) for n in self.portion_tree.selection()))

    def restore_selected_take(self):
        row,take = self.selected(),self.selected_take()
        if row and take and not take['current']:
            self.audio_job(automatic=row['automatic'],segment_id=row['plan']['segment_id'],restore_take=take['key'])

    def audio_job(self, **options):
        try:
            self._stop_players()
            self.jobs.start_audio(self.selected_book(),**options)
            self.update_buttons()
        except (OSError,RuntimeError,ValueError) as exc:
            messagebox.showerror('Génération audio',str(exc),parent=self.window)

    def generate_selected(self):
        row = self.selected()
        if row:
            self.audio_job(automatic=row['automatic'],segment_id=row['plan']['segment_id'])

    def regenerate_selected(self):
        row = self.selected()
        if row:
            self.audio_job(automatic=row['automatic'],segment_id=row['plan']['segment_id'],regenerate=True)

    def generate_first(self):
        self.audio_job(first=True)

    def generate_all(self):
        self.audio_job(both=True)

    def approve(self):
        try:
            self.inventory.approve_previews(self.selected_book())
            self.update_buttons()
        except (OSError,ValueError) as exc:
            messagebox.showerror('Premiers audios',str(exc),parent=self.window)

    def refresh_drafts(self):
        drafts = self.imports.list_drafts()
        self.draft_ids = [d['id'] for d in drafts]
        self.draft_combo.configure(values=[d['title']+' · '+{'draft':'à préparer','prepared':'à relire','published':'intégré'}.get(d['status'],d['status']) for d in drafts])
        if self.draft_id in self.draft_ids:
            self.draft_combo.current(self.draft_ids.index(self.draft_id))

    def load_draft(self, event=None):
        if self.draft_combo.current()<0:
            return
        self.draft_id = self.draft_ids[self.draft_combo.current()]
        folder = self.imports.draft(self.draft_id)
        request = Content.read(folder/'request.json')
        self.import_title.set(request['title'])
        self.import_author.set(request['author'])
        self.source.delete('1.0','end')
        self.source.insert('1.0',(folder/'source.txt').read_text(encoding='utf-8'))
        self.show_draft_preview()

    def show_draft_preview(self):
        if not self.draft_id:
            return
        folder = self.imports.draft(self.draft_id)
        book = read_optional(folder/'prepared_book.json')
        lines = []
        if book:
            lines = [book['audio_intro']['text']]
            for scene in book['scenes']:
                lines += [f'\n{scene["rank"]}. {scene["title"]}',scene['text'],
                          'Tons : '+', '.join(dict.fromkeys(EMOTIONS.get(s['emotion'],s['emotion']) for s in scene['audio_spans']))]
                for i,choice in enumerate(scene.get('choices',[]),1):
                    lines.append(f'Choix {i} : {choice["text"]}\n→ {choice["consequence"]}')
        self.put(self.preview,'\n\n'.join(lines) if lines else 'Ce brouillon attend sa préparation par Codex.')
        self.update_buttons()

    def load_text(self):
        path = filedialog.askopenfilename(parent=self.window,title='Texte du conte',filetypes=[('Texte UTF-8','*.txt'),('Tous les fichiers','*.*')])
        if path:
            try:
                text = Path(path).read_text(encoding='utf-8-sig')
                self.source.delete('1.0','end')
                self.source.insert('1.0',text)
                self.draft_id = None
            except (OSError,UnicodeError) as exc:
                messagebox.showerror('Importer',str(exc),parent=self.window)

    def save_draft(self):
        try:
            self.draft_id = self.imports.create(self.import_title.get(),self.import_author.get(),self.source.get('1.0','end-1c'))
            self.refresh_drafts()
            self.show_draft_preview()
            return self.draft_id
        except (OSError,ValueError) as exc:
            messagebox.showerror('Brouillon',str(exc),parent=self.window)
            return None

    def prepare_import(self):
        try:
            # Sauvegarder les éventuelles modifications du formulaire dans un nouveau brouillon.
            existing = read_optional(self.imports.draft(self.draft_id)/'request.json') if self.draft_id else {}
            same = bool(existing and existing['title']==self.import_title.get().strip() and existing['author']==self.import_author.get().strip()
                        and (self.imports.draft(self.draft_id)/'source.txt').read_text(encoding='utf-8').strip()==self.source.get('1.0','end-1c').strip())
            if not same or existing.get('status')=='published':
                if not self.save_draft():
                    return
            self.imports.prepare(self.jobs,self.draft_id)
            self.update_buttons()
        except (OSError,RuntimeError,ValueError) as exc:
            messagebox.showerror('Codex',str(exc),parent=self.window)

    def publish_import(self):
        if not self.draft_id or self.jobs.busy:
            return
        try:
            folder = self.imports.draft(self.draft_id)
            request = Content.read(folder/'request.json')
            if (request['title'] != self.import_title.get().strip() or
                    request['author'] != self.import_author.get().strip() or
                    (folder/'source.txt').read_text(encoding='utf-8').strip() != self.source.get('1.0','end-1c').strip()):
                raise ValueError('Le formulaire a changé. Préparer ce texte avec Codex puis relire le nouveau brouillon avant de l’intégrer.')
            self.imports.publish(self.draft_id)
            self.owner.content = Content(self.root)
            if self.owner.engine is None and self.owner.setup_kind == 'library':
                self.owner.home()
            self.refresh_all()
            self.tabs.select(0)
            self.book_combo.current(self.book_ids.index(self.draft_id))
            self.refresh_rows()
            messagebox.showinfo('Conte intégré','Le conte est dans la bibliothèque. Générez et écoutez ses premiers audios dans les deux modes, puis validez le rendu avant de compléter la génération.',parent=self.window)
        except (OSError,RuntimeError,ValueError,KeyError) as exc:
            messagebox.showerror('Intégration',str(exc),parent=self.window)

    def check_codex(self):
        self.codex_status.set('Vérification de la connexion Codex…')
        def check():
            executable = codex_executable()
            try:
                result = subprocess.run([executable,'login','status'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15,**hidden_process_options()) if executable else None
                self.connection_result = 'Codex connecté · connexion existante utilisable.' if result and result.returncode==0 else 'Codex n’est pas connecté. Ouvrir Codex et se connecter, ou utiliser codex login.'
            except (OSError,subprocess.TimeoutExpired):
                self.connection_result = 'Codex indisponible. Vérifier son installation et sa connexion.'
        threading.Thread(target=check,daemon=True,name='codex-login-status').start()

    def resume(self):
        try:
            self._stop_players()
            self.jobs.resume()
        except (OSError,RuntimeError,ValueError) as exc:
            messagebox.showerror('Reprise',str(exc),parent=self.window)

    def poll(self):
        import time
        if hasattr(self,'connection_result'):
            self.codex_status.set(self.connection_result)
            del self.connection_result
        state = self.jobs.snapshot()
        status = state.get('status')
        self.job_text.set((state.get('label','')+' · '+JOB_STATUS.get(status,status or '')+('\n'+state['error'] if state.get('error') else '')) if state else 'Aucune tâche en cours.')
        self.stop_button.configure(state='normal' if self.jobs.busy else 'disabled')
        self.resume_button.configure(state='normal' if not self.jobs.busy and status in ('failed','stopped','interrupted') else 'disabled')
        log = self.jobs.log_tail()
        if log != self.last_log:
            self.put(self.journal,log)
            self.journal.see('end')
            self.last_log = log
        if status in ('succeeded','failed','stopped') and state.get('finished') != self.last_finished:
            self.last_finished = state.get('finished')
            self.refresh_all()
            self.show_draft_preview()
        elif self.jobs.busy and time.monotonic()-self.last_refresh>2:
            self.last_refresh = time.monotonic()
            self.refresh_rows()
        self.update_buttons()
        self.poll_id = self.window.after(800,self.poll)

    def close(self):
        self.audio.stop()
        if self.poll_id:
            self.window.after_cancel(self.poll_id)
            self.poll_id = None
        self.window.destroy()
        self.owner.admin_window = None

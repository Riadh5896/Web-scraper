import tkinter as tk
from tkinter import ttk, filedialog
import threading
import concurrent.futures
import requests
import csv
import random
import time
import json
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


# 0. Configuration du Logging

logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)



class URLCollector:
    """
    Classe pour collecter les URLs avec une limite globale.
    """
    def __init__(self, limit=0):
        self.limit = limit  # 0 = illimité
        self.urls = []
    
    def add_urls(self, new_urls):
        """
        Ajoute des URLs au collecteur en respectant la limite.
        Retourne False si la limite est atteinte, True sinon.
        """
        if self.limit <= 0:
            self.urls.extend(new_urls)
            return True
        remaining = self.limit - len(self.urls)
        if remaining <= 0:
            return False
        if len(new_urls) > remaining:
            self.urls.extend(new_urls[:remaining])
            return False
        else:
            self.urls.extend(new_urls)
            return True

def is_allowed(url: str, disallowed_fragments: list) -> bool:
    """Retourne False si l'URL contient un fragment interdit, True sinon."""
    return not any(fragment in url for fragment in disallowed_fragments)

def get_sitemap_urls(sitemap_url: str, collector: URLCollector, disallowed: list, log_callback=None) -> list:
    """
    Récupère (récursivement) toutes les URLs (<loc>) depuis un sitemap:
      - Si on trouve un <sitemapindex>, parcourt chaque sous-sitemap.
      - Sinon, on suppose un <urlset> et on récupère les <loc>.
    Ajoute uniquement les URLs autorisées dans le collector jusqu'à la limite.
    """
    if collector.limit > 0 and len(collector.urls) >= collector.limit:
        return collector.urls
    
    try:
        resp = requests.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        message = f"[OK] Récupération sitemap: {sitemap_url} (status={resp.status_code})"
        logging.info(message)
        if log_callback:
            log_callback(message)
    except requests.RequestException as e:
        message = f"[ERREUR] Impossible de récupérer '{sitemap_url}': {e}"
        logging.error(message)
        if log_callback:
            log_callback(message)
        return []
    
    soup = BeautifulSoup(resp.content, "xml")
    
    # Vérifier s'il y a un <sitemapindex>
    sitemapindex_tag = soup.find(lambda t: t.name and t.name.lower().endswith("sitemapindex"))
    if sitemapindex_tag:
        sitemap_tags = sitemapindex_tag.find_all(
            lambda t: t.name and t.name.lower().endswith("sitemap"), recursive=True
        )
        for tag in sitemap_tags:
            if collector.limit > 0 and len(collector.urls) >= collector.limit:
                break
            loc_tag = tag.find(lambda x: x.name and x.name.lower().endswith("loc"))
            if loc_tag:
                sub_sitemap_url = loc_tag.text.strip()
                if log_callback:
                    log_callback(f"[INFO] Traitement du sous-sitemap: {sub_sitemap_url}")
                get_sitemap_urls(sub_sitemap_url, collector, disallowed, log_callback)
        return collector.urls
    
    # Sinon, supposer un <urlset>
    urlset_tag = soup.find(lambda t: t.name and t.name.lower().endswith("urlset"))
    if urlset_tag:
        loc_tags = urlset_tag.find_all(lambda x: x.name and x.name.lower().endswith("loc"))
        urls = [tag.get_text(strip=True) for tag in loc_tags]
        # Filtrer les URLs autorisées
        allowed_urls = [u for u in urls if is_allowed(u, disallowed)]
        # Ajouter au collector
        collector.add_urls(allowed_urls)
        if log_callback:
            log_callback(f"[INFO] Ajout de {len(allowed_urls)} URLs autorisées depuis {sitemap_url}")
        return collector.urls
    
    # Si aucun <sitemapindex> ni <urlset>
    message = f"[WARN] '{sitemap_url}' n'est pas un sitemapindex ni un urlset reconnu."
    logging.warning(message)
    if log_callback:
        log_callback(message)
    return collector.urls

def get_allowed_urls(sitemap_or_url: str, disallowed: list, limit=0, log_callback=None) -> list:
    """
    1. Si 'sitemap_or_url' contient '.xml', le traiter comme un sitemap.
    2. Sinon, c'est une URL unique.
    3. Filtrer via 'disallowed'.
    4. Retourner la liste finale, limitée si nécessaire.
    """
    collector = URLCollector(limit)
    if ".xml" in sitemap_or_url.lower():
        get_sitemap_urls(sitemap_or_url, collector, disallowed, log_callback)
    else:
        if is_allowed(sitemap_or_url, disallowed):
            collector.add_urls([sitemap_or_url])
            if log_callback:
                log_callback(f"[INFO] Ajout de l'URL unique: {sitemap_or_url}")
    return collector.urls

def scrape_content(url: str, min_delay: float, max_delay: float,
                   pause_event: threading.Event,
                   stop_event: threading.Event,
                   log_callback=None,
                   js_enabled=False) -> dict:
    """
    Scrape le contenu d'une page (titres, paragraphes, images, métadonnées).
    Retourne un dict. Gère pause/arrêt en vérifiant pause_event/stop_event.
    Ajoute l'exécution JavaScript via Playwright si js_enabled est True.
    """
    # Vérifier 'Stop' avant de commencer
    if stop_event.is_set():
        return {}
    
    # Vérifier 'Pause'
    while pause_event.is_set():
        time.sleep(0.2)
        if stop_event.is_set():
            return {}

    if js_enabled:
        # Utilisation de Playwright pour exécuter JavaScript
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle")
                # Récupérer le contenu rendu
                content = page.content()
                browser.close()
            message = f"[OK] Scraping (JS) de: {url}"
            logging.info(message)
            if log_callback:
                log_callback(message)
        except Exception as e:
            message = f"[ERREUR] Playwright a échoué pour {url}: {e}"
            logging.error(message)
            if log_callback:
                log_callback(message)
            return {}
        soup = BeautifulSoup(content, 'html.parser')
    else:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            message = f"[OK] Scraping de: {url} (status={response.status_code})"
            logging.info(message)
            if log_callback:
                log_callback(message)
        except requests.RequestException as e:
            message = f"[ERREUR] Échec requête: {url} -> {e}"
            logging.error(message)
            if log_callback:
                log_callback(message)
            return {}
        soup = BeautifulSoup(response.text, 'html.parser')
    
    # Titres
    headings_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    headings = [tag.get_text(strip=True) for tag in headings_tags]
    
    # Paragraphes
    paragraphs_tags = soup.find_all('p')
    paragraphs = [p.get_text(strip=True) for p in paragraphs_tags if p.get_text(strip=True)]
    
    # Images (src + alt)
    images_tags = soup.find_all('img', src=True)
    images = []
    for img in images_tags:
        src_abs = urljoin(url, img['src'])
        alt = img.get('alt', '')
        images.append({'src': src_abs, 'alt': alt})
    
    # Métadonnées
    meta_description = ""
    meta_keywords = ""
    meta_og_title = ""
    
    desc_tag = soup.find('meta', attrs={'name': 'description'})
    if desc_tag and 'content' in desc_tag.attrs:
        meta_description = desc_tag['content']
    
    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_tag and 'content' in keywords_tag.attrs:
        meta_keywords = keywords_tag['content']
    
    og_title_tag = soup.find('meta', property='og:title')
    if og_title_tag and 'content' in og_title_tag.attrs:
        meta_og_title = og_title_tag['content']
    
    # Vérifier 'Stop'/'Pause' avant d'attendre
    if stop_event.is_set():
        return {}
    while pause_event.is_set():
        time.sleep(0.2)
        if stop_event.is_set():
            return {}
    
    # Respect d'un délai aléatoire
    delay = random.uniform(min_delay, max_delay)
    if log_callback:
        log_callback(f"[INFO] Pause de {delay:.2f} secondes avant la prochaine requête.")
    time.sleep(delay)
    
    return {
        'url': url,
        'headings': headings,
        'paragraphs': paragraphs,
        'images': images,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'meta_og_title': meta_og_title
    }

def scrape_all_urls(urls, min_delay=1.0, max_delay=3.0, workers=1,
                   progress_callback=None,
                   pause_event=None,
                   stop_event=None,
                   log_callback=None,
                   data_callback=None,
                   js_enabled=False):  # Ajout du paramètre js_enabled
    """
    Scrape toutes les URLs en utilisant ThreadPoolExecutor.
    Gère pause/arrêt via pause_event et stop_event.
    Retourne une liste de dicts.
    """
    results = []
    total = len(urls)
    if total == 0:
        return results
    
    if pause_event is None:
        pause_event = threading.Event()
    if stop_event is None:
        stop_event = threading.Event()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {
            executor.submit(
                scrape_content, url, min_delay, max_delay, pause_event, stop_event, log_callback, js_enabled
            ): url
            for url in urls
        }
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_url), start=1):
            url = future_to_url[future]
            if stop_event.is_set():
                # Si "Arrêter" est cliqué, on abandonne les futures restantes
                break
            
            try:
                data = future.result()
                if data:
                    results.append(data)
                    msg = f"[{i}/{total}] OK: {url}"
                    if data_callback:
                        data_callback(data)  # Append data to scraped_data
                else:
                    msg = f"[{i}/{total}] Échec ou annulé: {url}"
            except Exception as exc:
                msg = f"[{i}/{total}] Exception pour {url}: {exc}"
            
            logging.info(msg)
            if progress_callback:
                progress_callback(i, total, msg)
            if log_callback:
                log_callback(msg)
    
    return results

def save_results_to_csv(data_list, csv_filename):
    """
    Sauvegarde les résultats dans un fichier CSV.
    Les listes/dicts sont encodés en JSON pour éviter les problèmes de séparateur.
    """
    fieldnames = [
        'url',
        'headings',
        'paragraphs',
        'images',
        'meta_description',
        'meta_keywords',
        'meta_og_title'
    ]
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in data_list:
            row = {
                'url': item['url'],
                'headings': json.dumps(item['headings'], ensure_ascii=False),
                'paragraphs': json.dumps(item['paragraphs'], ensure_ascii=False),
                'images': json.dumps(item['images'], ensure_ascii=False),
                'meta_description': item['meta_description'],
                'meta_keywords': item['meta_keywords'],
                'meta_og_title': item['meta_og_title']
            }
            writer.writerow(row)
    
    message = f"[FIN] {len(data_list)} lignes sauvegardées dans {csv_filename}"
    logging.info(message)

# Function to save data in JSON format
def save_results_to_json(data_list, json_filename):
    """
    Save the scraping results in a JSON file.
    """
    try:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        message = f"[FIN] Données sauvegardées en JSON dans '{json_filename}'"
        logging.info(message)
        return message
    except Exception as e:
        message = f"[ERREUR] Échec de la sauvegarde JSON: {e}"
        logging.error(message)
        return message



# 2. Interface Tkinter 

class ScraperGUI:
    def __init__(self, root):
        self.root = root
        root.title("Web Scraper")
    
        # Events pour pause/arrêt
        self.pause_event = threading.Event()  # True => en pause
        self.stop_event = threading.Event()   # True => arrêt demandé
        self.is_paused = False
    
        self.scraping_thread = None
        self.executor = None
    
        # Variables pour l'estimation
        self.start_time = None  # Enregistrer l'heure de début
        self.urls_scraped = 0
        self.elapsed_time = 0.0
        self.estimated_finish_time = None
    
        # Variables pour les données scrappées
        self.scraped_data = []          
        self.data_lock = threading.Lock()  
    
        # Cadre principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
    
        #  Sitemap ou URL
        ttk.Label(main_frame, text="Sitemap ou URL :").grid(row=0, column=0, sticky="w", pady=2)
        self.sitemap_url_var = tk.StringVar(value="https://www.brewbound.com/sitemap_index.xml")
        self.sitemap_url_entry = ttk.Entry(main_frame, textvariable=self.sitemap_url_var, width=50)
        self.sitemap_url_entry.grid(row=0, column=1, padx=5, pady=2)
    
        #  Motifs non autorisés
        ttk.Label(main_frame, text="Motifs non autorisés (séparés par des virgules) :").grid(row=1, column=0, sticky="w", pady=2)
        self.disallowed_var = tk.StringVar()
        self.disallowed_entry = ttk.Entry(main_frame, textvariable=self.disallowed_var, width=50)
        self.disallowed_entry.grid(row=1, column=1, padx=5, pady=2)
    
        #  Fichier CSV de sortie
        ttk.Label(main_frame, text="Fichier CSV de sortie :").grid(row=2, column=0, sticky="w", pady=2)
        self.csv_var = tk.StringVar(value="resultats_scraping.csv")
        self.csv_entry = ttk.Entry(main_frame, textvariable=self.csv_var, width=50)
        self.csv_entry.grid(row=2, column=1, padx=5, pady=2)
    
        browse_btn = ttk.Button(main_frame, text="Parcourir...", command=self.browse_csv)
        browse_btn.grid(row=2, column=2, padx=5, pady=2)

        # Ficher Json de sortie
        # File output fields
        ttk.Label(main_frame, text="Fichier JSON de sortie :").grid(row=3, column=0, sticky="w", pady=2)
        self.json_var = tk.StringVar(value="resultats_scraping.json")
        self.json_entry = ttk.Entry(main_frame, textvariable=self.json_var, width=50)
        self.json_entry.grid(row=3, column=1, padx=5, pady=2)  
        
        browse_json_btn = ttk.Button(main_frame, text="Parcourir...", command=self.browse_json)
        browse_json_btn.grid(row=3, column=2, padx=5, pady=2)
        
        # Buttons
        self.export_json_button = ttk.Button(main_frame, text="Exporter en JSON", command=self.on_export_json)
        self.export_json_button.grid(row=9, column=0, pady=10, sticky="w")
    
        #  Délai minimum
        ttk.Label(main_frame, text="Délai minimum (s) :").grid(row=4, column=0, sticky="w", pady=2)
        self.min_delay_var = tk.DoubleVar(value=1.0)
        self.min_delay_entry = ttk.Entry(main_frame, textvariable=self.min_delay_var, width=10)
        self.min_delay_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)
    
        #  Délai maximum
        ttk.Label(main_frame, text="Délai maximum (s) :").grid(row=5, column=0, sticky="w", pady=2)
        self.max_delay_var = tk.DoubleVar(value=3.0)
        self.max_delay_entry = ttk.Entry(main_frame, textvariable=self.max_delay_var, width=10)
        self.max_delay_entry.grid(row=5, column=1, sticky="w", padx=5, pady=2)
    
        #  Nombre de threads
        ttk.Label(main_frame, text="Nombre de threads :").grid(row=6, column=0, sticky="w", pady=2)
        self.concurrency_var = tk.IntVar(value=1)
        self.concurrency_entry = ttk.Entry(main_frame, textvariable=self.concurrency_var, width=10)
        self.concurrency_entry.grid(row=6, column=1, sticky="w", padx=5, pady=2)
    
        #  Limite de URLs
        ttk.Label(main_frame, text="Limite de URLs (0 = illimité) :").grid(row=7, column=0, sticky="w", pady=2)
        self.limit_var = tk.IntVar(value=0)
        self.limit_entry = ttk.Entry(main_frame, textvariable=self.limit_var, width=10)
        self.limit_entry.grid(row=7, column=1, sticky="w", padx=5, pady=2)
    
        # Activer JavaScript via Playwright
        self.js_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Activer JavaScript (Playwright)", variable=self.js_enabled_var)\
            .grid(row=8, column=0, columnspan=2, sticky="w", pady=2)
    
        # Boutons : Commencer, Pause/Reprendre, Arrêter, Sauvegarder
        self.start_button = ttk.Button(main_frame, text="Commencer", command=self.on_start)
        self.start_button.grid(row=10, column=0, pady=10, sticky="w")
    
        self.pause_button = ttk.Button(main_frame, text="Pause", command=self.on_pause)
        self.pause_button.grid(row=10, column=1, pady=10, sticky="w")
    
        self.stop_button = ttk.Button(main_frame, text="Arrêter", command=self.on_stop)
        self.stop_button.grid(row=10, column=2, pady=10, sticky="w")
    
        self.save_button = ttk.Button(main_frame, text="Sauvegarder", command=self.on_save)
        self.save_button.grid(row=10, column=3, pady=10, sticky="w")
    
        # Barre de progression
        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.grid(row=11, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
    
        # Label pour l'estimation du temps
        self.estimation_label = ttk.Label(main_frame, text="Estimation de fin: N/A")
        self.estimation_label.grid(row=12, column=0, columnspan=4, sticky="w", pady=2)
    
        # Zone de texte pour le statut
        self.status_text = tk.Text(root, height=10, width=80, state="disabled")
        self.status_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
    
        # Rendre la fenêtre redimensionnable
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)
    
    def browse_csv(self):
        """Ouvre une boîte de dialogue pour choisir le fichier CSV de sortie."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.csv_var.set(filename)
    
    def log_to_gui(self, message):
        """Insère un message dans la zone de statut."""
        def append_msg():
            self.status_text.config(state="normal")
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.config(state="disabled")
            self.status_text.see(tk.END)
        self.root.after(0, append_msg)
    
    def on_start(self):
        """Démarre le scraping dans un thread séparé."""
        # Vider la zone de statut
        self.status_text.config(state="normal")
        self.status_text.delete("1.0", tk.END)
        self.status_text.config(state="disabled")
        
        # Réinitialiser les events
        self.pause_event.clear()
        self.stop_event.clear()
        self.is_paused = False
        self.pause_button.config(text="Pause")
        
        # Réinitialiser les variables d'estimation
        self.start_time = time.time()  # Enregistrer le temps de début
        self.urls_scraped = 0
        self.estimation_label.config(text="Estimation de fin: N/A")  # Réinitialiser le label
        
        # Réinitialiser les données scrappées
        with self.data_lock:
            self.scraped_data = []
        
        # Récupérer les paramètres de l'interface
        sitemap_or_url = self.sitemap_url_var.get().strip()
        disallowed_string = self.disallowed_var.get().strip()
        csv_filename = self.csv_var.get().strip()
        min_delay = self.min_delay_var.get()
        max_delay = self.max_delay_var.get()
        workers = self.concurrency_var.get()
        limit = self.limit_var.get()
        js_enabled = self.js_enabled_var.get()
        
        # Vérifications basiques
        if not sitemap_or_url:
            self.log_to_gui("[ERREUR] Veuillez saisir un sitemap ou une URL.")
            return
        if min_delay < 0 or max_delay < min_delay:
            self.log_to_gui("[ERREUR] Les valeurs de délai min/max sont invalides.")
            return
        if workers < 1:
            self.log_to_gui("[ERREUR] Le nombre de threads doit être >= 1.")
            return
        if limit < 0:
            self.log_to_gui("[ERREUR] La limite doit être >= 0.")
            return
        
        # Convertir la chaîne en liste
        disallowed_list = []
        if disallowed_string:
            disallowed_list = [x.strip() for x in disallowed_string.split(",") if x.strip()]
        
        # Désactiver le bouton "Commencer" pendant le run
        self.start_button.config(state="disabled")
        
        # Réinitialiser la barre de progression
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 100  # sera ajusté plus tard
        
        def background_task():
            try:
                # 1) Récupérer les URLs autorisées avec limite globale
                urls = get_allowed_urls(sitemap_or_url, disallowed_list, limit=limit, log_callback=self.log_to_gui)
                total_urls = len(urls)
                msg_urls = f"[INFO] Total d'URLs trouvées : {total_urls}"
                logging.info(msg_urls)
                self.log_to_gui(msg_urls)
                
                if total_urls == 0:
                    self.log_to_gui("[INFO] Aucune URL à scraper.")
                    return
                
                # Ajuster la progress bar
                self.root.after(0, lambda: self.set_progress_max(total_urls))
                
                # 2) Scraping en parallèle
                # Mise à jour des URLs scrappées et estimation
                def progress_callback(current, total, message):
                    self.urls_scraped = current  # Mise à jour du nombre d'URLs scrappées
                    self.update_estimation()
                    self.update_progress(current, total, message)
                
                def data_callback(data):
                    with self.data_lock:
                        self.scraped_data.append(data)
                
                scraped_data = scrape_all_urls(
                    urls,
                    min_delay=min_delay,
                    max_delay=max_delay,
                    workers=workers,
                    progress_callback=progress_callback,
                    pause_event=self.pause_event,
                    stop_event=self.stop_event,
                    log_callback=self.log_to_gui,
                    data_callback=data_callback,
                    js_enabled=js_enabled
                )
                
                # 3) Sauvegarder le résultat (si pas d'arrêt)
                if not self.stop_event.is_set():
                    save_results_to_csv(scraped_data, csv_filename)
                    self.log_to_gui(f"[FIN] Scraping terminé. Résultats dans '{csv_filename}'")
                else:
                    self.log_to_gui("[INFO] Scraping interrompu par l'utilisateur.")
            
            finally:
                self.executor = None
                self.start_button.config(state="normal")
        
        # Lancer le thread
        self.scraping_thread = threading.Thread(target=background_task)
        self.scraping_thread.start()
    
    def set_progress_max(self, total):
        """Ajuste la barre de progression."""
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = total
    
    def update_progress(self, current, total, message):
        """Mise à jour de la barre de progression et du texte de statut."""
        def update():
            self.progress_bar["value"] = current
            self.log_to_gui(message)
        self.root.after(0, update)
    
    def on_pause(self):
        """Gère le bouton Pause/Reprendre."""
        if not self.is_paused:
            # Passer en pause
            self.is_paused = True
            self.pause_event.set()
            self.pause_button.config(text="Reprendre")
            self.log_to_gui("[INFO] Scraping mis en pause.")
        else:
            # Reprendre
            self.is_paused = False
            self.pause_event.clear()
            self.pause_button.config(text="Pause")
            self.log_to_gui("[INFO] Reprise du scraping.")
    
    def on_stop(self):
        """Demande l'arrêt du scraping."""
        self.stop_event.set()
        self.log_to_gui("[INFO] Arrêt demandé. Les tâches en attente seront annulées.")
    
        # Tente d'annuler les futures non commencées
        if self.executor is not None:
            self.executor.shutdown(cancel_futures=True)
            self.executor = None
    
    def on_save(self):
        """Sauvegarde les données scrappées jusqu'à présent."""
        with self.data_lock:
            if not self.scraped_data:
                self.log_to_gui("[INFO] Aucune donnée à sauvegarder.")
                return
            # Demander un emplacement de fichier
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Tous les fichiers", "*.*")]
            )
            if not filename:
                return
            # Copier les données
            data_to_save = list(self.scraped_data)
        # Sauvegarder en dehors du verrou pour éviter de bloquer
        try:
            save_results_to_csv(data_to_save, filename)
            self.log_to_gui(f"[FIN] Données sauvegardées dans '{filename}'")
        except Exception as e:
            self.log_to_gui(f"[ERREUR] Échec de la sauvegarde: {e}")
    
    def update_estimation(self):
        """Met à jour l'estimation du temps restant."""
        if self.start_time is None:
            self.estimation_label.config(text="Estimation de fin: N/A")
            return
        
        current_time = time.time()
        elapsed = current_time - self.start_time
        self.elapsed_time = elapsed
        if self.urls_scraped == 0:
            self.estimation_label.config(text="Estimation de fin: Calcul en cours...")
            return
        
        average_time_per_url = elapsed / self.urls_scraped
        remaining_urls = self.progress_bar["maximum"] - self.urls_scraped
        estimated_remaining = average_time_per_url * remaining_urls
        estimated_finish = datetime.now() + timedelta(seconds=estimated_remaining)
        estimation_str = estimated_finish.strftime("%H:%M:%S")
        self.estimation_label.config(text=f"Estimation de fin: {estimation_str}")
    
    def browse_json(self):
        """Open a file dialog to select JSON output file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.json_var.set(filename)  # Set the chosen file path to the input field
    
    def on_export_json(self):
        """Export scraped data to JSON."""
        with self.data_lock:
            if not self.scraped_data:
                self.log_to_gui("[INFO] Aucune donnée à sauvegarder en JSON.")
                return

        # Ask user for file location
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Tous les fichiers", "*.*")]
        )

        if not filename:
            self.log_to_gui("[ERREUR] Nom de fichier JSON invalide.")
            return

    # Save JSON
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_data, f, ensure_ascii=False, indent=4)
            self.log_to_gui(f"[FIN] Données sauvegardées en JSON dans '{filename}'")
        except Exception as e:
            self.log_to_gui(f"[ERREUR] Échec de la sauvegarde JSON: {e}")


def main():
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

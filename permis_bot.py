"""
Bot simplifié utilisant Scrapling + Playwright pour bypass automatique
Compatible avec l'API actuelle de Scrapling
"""
from playwright.sync_api import sync_playwright
import time
from datetime import datetime
import random
import os
from dotenv import load_dotenv

class PermisScraplingBot:
    def __init__(self, twocaptcha_api_key=None, proxy_config=None):
        self.playwright = None
        self.browser = None
        self.page = None
        self.twocaptcha_api_key = twocaptcha_api_key
        self.proxy_config = proxy_config
        self.previous_slots = []
        
    def setup_browser(self):
        """Configure Playwright avec mode furtif"""
        try:
            print("🚀 Initialisation de Playwright (mode furtif)...")
            
            self.playwright = sync_playwright().start()
            
            # Configuration du navigateur
            launch_options = {
                'headless': False,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--lang=fr-FR',
                ]
            }
            
            # Ajouter le proxy si configuré
            if self.proxy_config:
                proxy_dict = {
                    'server': f"http://{self.proxy_config['host']}:{self.proxy_config['port']}"
                }
                if self.proxy_config.get('username'):
                    proxy_dict['username'] = self.proxy_config['username']
                    proxy_dict['password'] = self.proxy_config['password']
                
                launch_options['proxy'] = proxy_dict
                print(f"🌐 Proxy configuré: {self.proxy_config['host']}")
            
            # Lancer Firefox (meilleur pour le bypass)
            self.browser = self.playwright.chromium.launch(**launch_options)
            
            # Créer un contexte avec headers français
            context = self.browser.new_context(
                locale='fr-FR',
                timezone_id='Europe/Paris',
                user_agent='Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept-Language': 'fr-FR,fr;q=0.9',
                }
            )
            
            self.page = context.new_page()
            
            # Masquer webdriver
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Masquer automation
                delete navigator.__proto__.webdriver;
                
                // Plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Langues
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['fr-FR', 'fr', 'en-US', 'en']
                });
            """)
            
            print("✅ Playwright initialisé")
            print("   • Mode furtif activé")
            print("   • Firefox (anti-détection)")
            print("   • Locale: fr-FR")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur d'initialisation: {e}")
            print("\n💡 Installation requise:")
            print("   pip install playwright")
            print("   playwright install firefox")
            import traceback
            traceback.print_exc()
            return False
    
    def test_bypass(self):
        """Test de bypass Cloudflare"""
        try:
            print("\n🧪 Test de bypass Cloudflare...")
            
            test_url = "https://nowsecure.nl"
            print(f"   📡 Chargement: {test_url}")
            
            self.page.goto(test_url, wait_until='networkidle', timeout=30000)
            
            # Attendre que Cloudflare soit résolu
            time.sleep(5)
            
            content = self.page.content()
            
            if "Checking your browser" in content or "Just a moment" in content:
                print("   ⏳ Challenge Cloudflare en cours...")
                time.sleep(10)
            
            # Vérifier le résultat
            if "nowsecure" in self.page.url.lower():
                print("   ✅ Bypass réussi!")
                return True
            else:
                print(f"   ⚠️  Status incertain")
                return False
                
        except Exception as e:
            print(f"   ⚠️  Erreur test: {e}")
            return False
    
    def detect_captcha(self):
        """Détecte si un CAPTCHA est présent"""
        try:
            print("🔍 Détection de CAPTCHA...")
            
            html = self.page.content()
            
            # Vérifier Cloudflare Turnstile (priorité car c'est ce que le site utilise)
            if 'challenges.cloudflare.com/turnstile' in html or 'cf-turnstile' in html or 'data-sitekey=' in html:
                print("   ✓ Cloudflare Turnstile détecté")
                
                # Extraire le sitekey
                import re
                sitekey_match = re.search(r'data-sitekey="([^"]+)"', html)
                sitekey = sitekey_match.group(1) if sitekey_match else None
                
                if sitekey:
                    print(f"   ✓ Sitekey: {sitekey}")
                
                return {
                    'type': 'turnstile',
                    'sitekey': sitekey,
                    'url': self.page.url,
                    'invisible': False  # Turnstile est visible mais automatique
                }
            
            # Vérifier reCAPTCHA v2 (visible)
            recaptcha = self.page.query_selector("iframe[src*='recaptcha']")
            if recaptcha:
                print("   ✓ reCAPTCHA v2 détecté")
                frame_src = recaptcha.get_attribute('src')
                if 'k=' in frame_src:
                    sitekey = frame_src.split('k=')[1].split('&')[0]
                    return {
                        'type': 'recaptcha_v2',
                        'sitekey': sitekey,
                        'url': self.page.url
                    }
            
            # Vérifier reCAPTCHA v3 (invisible)
            import re
            recaptcha_v3_match = re.search(r'grecaptcha\.execute\([\'"]([^\'\"]+)[\'"]', html)
            if recaptcha_v3_match or 'grecaptcha.ready' in html or 'grecaptcha.execute' in html:
                print("   ✓ reCAPTCHA v3 (invisible) détecté")
                return {
                    'type': 'recaptcha_v3',
                    'url': self.page.url,
                    'invisible': True
                }
            
            # Vérifier hCaptcha
            hcaptcha = self.page.query_selector("iframe[src*='hcaptcha']")
            if hcaptcha:
                print("   ✓ hCaptcha détecté")
                match = re.search(r'data-sitekey="([^"]+)"', html)
                if match:
                    return {
                        'type': 'hcaptcha',
                        'sitekey': match.group(1),
                        'url': self.page.url
                    }
            
            # Vérifier si le bouton submit est désactivé (signe de CAPTCHA)
            submit_button = self.page.query_selector("#kc-login")
            if submit_button and submit_button.get_attribute("disabled"):
                print("   ⚠️  Bouton désactivé - CAPTCHA non identifié")
                return {
                    'type': 'unknown',
                    'url': self.page.url,
                    'invisible': False
                }
            
            print("   ℹ️  Aucun CAPTCHA détecté")
            return None
            
        except Exception as e:
            print(f"   ⚠️  Erreur détection: {e}")
            return None
    
    def solve_captcha_with_2captcha(self, captcha_info):
        """Résout le CAPTCHA avec 2Captcha"""
        try:
            if not self.twocaptcha_api_key:
                print("⚠️  2Captcha non configuré")
                return None
            
            from twocaptcha import TwoCaptcha
            
            print("🤖 Résolution via 2Captcha...")
            solver = TwoCaptcha(self.twocaptcha_api_key)
            
            print(f"   Type: {captcha_info['type']}")
            print(f"   Sitekey: {captcha_info['sitekey'][:20]}...")
            print("   ⏳ Envoi à 2Captcha (30-60s)...")
            
            start = time.time()
            
            if captcha_info['type'] == 'recaptcha_v2':
                result = solver.recaptcha(
                    sitekey=captcha_info['sitekey'],
                    url=captcha_info['url']
                )
            elif captcha_info['type'] == 'hcaptcha':
                result = solver.hcaptcha(
                    sitekey=captcha_info['sitekey'],
                    url=captcha_info['url']
                )
            else:
                print(f"   ❌ Type non supporté: {captcha_info['type']}")
                return None
            
            elapsed = time.time() - start
            print(f"   ✅ Résolu en {elapsed:.1f}s!")
            
            return result['code']
            
        except Exception as e:
            print(f"   ❌ Erreur 2Captcha: {e}")
            return None
    
    def inject_captcha_token(self, token, captcha_info):
        """Injecte le token CAPTCHA"""
        try:
            print("💉 Injection du token...")
            
            if captcha_info['type'] == 'recaptcha_v2':
                script = f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    var clients = ___grecaptcha_cfg.clients;
                    for (var client in clients) {{
                        if (clients[client].callback) {{
                            clients[client].callback('{token}');
                        }}
                    }}
                }}
                """
                self.page.evaluate(script)
                
            elif captcha_info['type'] == 'hcaptcha':
                script = f"""
                document.querySelector('[name="h-captcha-response"]').innerHTML = '{token}';
                document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
                """
                self.page.evaluate(script)
            
            print("   ✅ Token injecté")
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur injection: {e}")
            return False
    
    def login(self, username, password):
        """Connexion avec bypass automatique"""
        try:
            print("\n🔐 CONNEXION")
            print("="*70)
            
            auth_url = "https://auth.permisdeconduire.gouv.fr/realms/formation/protocol/openid-connect/auth?client_id=formation_1&redirect_uri=https%3A%2F%2Fpro.permisdeconduire.gouv.fr%2Foidc-callback&response_type=code&scope=openid"
            
            print(f"📡 Navigation vers la page de login...")
            self.page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
            
            # Attente avec délai aléatoire
            wait_time = 8 + random.uniform(2, 4)
            print(f"⏳ Attente {wait_time:.1f}s...")
            time.sleep(wait_time)
            
            # Sauvegarder la page
            html = self.page.content()
            with open('page_login_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("📄 Page sauvegardée: page_login_debug.html")
            
            # Vérifier si on a passé les protections
            if "Checking your browser" in html or "Just a moment" in html:
                print("⏳ Challenge Cloudflare en cours...")
                time.sleep(10)
                html = self.page.content()
            
            # Attendre le formulaire
            try:
                self.page.wait_for_selector("#username", timeout=20000)
                print("✅ Formulaire détecté")
            except:
                print("❌ Timeout: formulaire absent")
                print(f"   URL actuelle: {self.page.url}")
                return False
            
            # Remplir le formulaire avec comportement humain
            print("✍️  Remplissage du formulaire...")
            
            # Username
            username_field = self.page.query_selector("#username")
            username_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            for char in username:
                username_field.type(char, delay=random.uniform(50, 150))
            print("   ✓ Username")
            
            # Password
            time.sleep(random.uniform(0.4, 0.8))
            password_field = self.page.query_selector("#password")
            password_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            for char in password:
                password_field.type(char, delay=random.uniform(50, 150))
            print("   ✓ Password")
            
            time.sleep(2)
            
            # Gestion du CAPTCHA
            print("\n🔒 Gestion du CAPTCHA")
            print("-"*70)
            
            captcha_info = self.detect_captcha()
            
            if not captcha_info:
                print("✅ Pas de CAPTCHA détecté")
                
            elif captcha_info.get('invisible'):
                # CAPTCHA invisible (reCAPTCHA v3, Turnstile, etc.)
                print(f"⚠️  CAPTCHA invisible détecté: {captcha_info['type']}")
                print("   Le bouton sera activé automatiquement après validation")
                print("\n⏳ Attente de la validation automatique...")
                
                # Attendre que le bouton soit activé (max 60 secondes)
                submit_button = self.page.query_selector("#kc-login")
                max_wait = 60
                elapsed = 0
                
                while elapsed < max_wait:
                    if not submit_button.get_attribute("disabled"):
                        print(f"   ✅ CAPTCHA résolu automatiquement après {elapsed}s!")
                        break
                    
                    time.sleep(2)
                    elapsed += 2
                    
                    if elapsed % 10 == 0:
                        print(f"   ⏳ {elapsed}s écoulées...")
                
                if submit_button.get_attribute("disabled"):
                    print("\n   ❌ Le CAPTCHA n'a pas été résolu automatiquement")
                    print("   Options:")
                    print("   1. Le site détecte peut-être l'automatisation")
                    print("   2. Le proxy pourrait être blacklisté")
                    print("   3. Résolution manuelle requise")
                    print("\n👉 Tentez de résoudre manuellement dans le navigateur")
                    input("   ⏸️  Appuyez sur Entrée une fois le CAPTCHA résolu...")
                
            else:
                # CAPTCHA visible (reCAPTCHA v2, hCaptcha)
                print(f"⚠️  CAPTCHA visible: {captcha_info['type']}")
                
                # Tentative avec 2Captcha si configuré
                if self.twocaptcha_api_key:
                    token = self.solve_captcha_with_2captcha(captcha_info)
                    
                    if token:
                        self.inject_captcha_token(token, captcha_info)
                        
                        # Attendre que le bouton soit activé
                        time.sleep(3)
                        submit_button = self.page.query_selector("#kc-login")
                        if submit_button.get_attribute("disabled"):
                            print("   ⚠️  Bouton toujours désactivé après injection")
                            print("   Résolution manuelle requise")
                            input("   ⏸️  Appuyez sur Entrée une fois résolu...")
                    else:
                        print("   Fallback: Résolution manuelle")
                        print("\n👉 Résolvez le CAPTCHA dans le navigateur")
                        input("   ⏸️  Appuyez sur Entrée une fois résolu...")
                
                else:
                    # Résolution manuelle
                    print("\n👉 Résolvez le CAPTCHA dans le navigateur")
                    print("   (Configurez TWOCAPTCHA_API_KEY pour l'automatisation)")
                    input("   ⏸️  Appuyez sur Entrée une fois résolu...")
            
            print("-"*70)
            
            # Soumettre le formulaire
            time.sleep(random.uniform(1, 2))
            print("\n🔄 Soumission du formulaire...")
            
            submit_button = self.page.query_selector("#kc-login")
            
            # Vérifier une dernière fois que le bouton est actif
            if submit_button.get_attribute("disabled"):
                print("⚠️  Le bouton de soumission est toujours désactivé")
                print("   Cela signifie que le CAPTCHA n'est pas résolu")
                print("\n👉 Vérifiez dans le navigateur et résolvez le CAPTCHA")
                input("   ⏸️  Appuyez sur Entrée une fois résolu...")
            
            # Tentative de clic avec retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    submit_button.click(timeout=10000)
                    print("   ✅ Formulaire soumis")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️  Tentative {attempt + 1} échouée, nouvelle tentative...")
                        time.sleep(2)
                    else:
                        print(f"   ❌ Impossible de cliquer sur le bouton après {max_retries} tentatives")
                        print("   Le CAPTCHA n'est probablement pas résolu")
                        print("\n👉 Résolvez manuellement puis appuyez sur Entrée dans le navigateur")
                        print("   Ou appuyez sur Entrée ici pour continuer")
                        input("   ⏸️  Entrée pour continuer...")
                        
                        # Tenter une soumission JavaScript en dernier recours
                        try:
                            print("   🔧 Tentative de soumission via JavaScript...")
                            self.page.evaluate("document.getElementById('kc-login').click()")
                            print("   ✅ Soumission JavaScript réussie")
                        except:
                            print("   ❌ Échec de la soumission JavaScript")
                            return False
            
            # Attendre la redirection
            time.sleep(5)
            
            # Vérifier le résultat
            current_url = self.page.url
            
            if "auth." in current_url or "login-actions" in current_url:
                print("❌ Échec de connexion")
                html = self.page.content()
                with open('erreur_login.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print("📄 Erreur sauvegardée: erreur_login.html")
                return False
            
            print(f"✅ CONNEXION RÉUSSIE!")
            print(f"   URL: {current_url}")
            
            # Sauvegarder la page après connexion
            with open('page_apres_connexion.html', 'w', encoding='utf-8') as f:
                f.write(self.page.content())
            print("📄 Page sauvegardée: page_apres_connexion.html")
            
            print("="*70)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def navigate_to_reservations(self):
        """Navigation vers les réservations"""
        try:
            print("\n🔍 Navigation vers réservations...")
            
            # Sauvegarder le dashboard
            with open('page_dashboard.html', 'w', encoding='utf-8') as f:
                f.write(self.page.content())
            print("📄 Dashboard sauvegardé")
            
            # Chercher les liens
            possible_texts = ["Réservation", "Réserver", "Créneaux", "Examens", "Planning"]
            
            for text in possible_texts:
                try:
                    link = self.page.query_selector(f"a:has-text('{text}')")
                    if link:
                        print(f"✅ Lien '{text}' trouvé")
                        link.click()
                        time.sleep(3)
                        return True
                except:
                    continue
            
            print("⚠️  Navigation automatique échouée")
            return False
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def check_available_slots(self):
        """Vérifier les créneaux"""
        try:
            slots = []
            
            # Sélecteurs possibles
            selectors = [
                ".slot-disponible",
                ".disponible",
                "[data-disponible='true']",
                ".slot.available"
            ]
            
            for selector in selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        print(f"   ✓ Trouvé avec: {selector}")
                        for elem in elements[:10]:
                            text = elem.inner_text()
                            if text:
                                slots.append(text)
                        break
                except:
                    continue
            
            return slots
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []
    
    def monitor_loop(self, check_interval_minutes=5):
        """Surveillance continue"""
        print(f"\n🔍 SURVEILLANCE ACTIVE")
        print(f"⏰ Intervalle: {check_interval_minutes} minutes")
        print(f"⌨️  Arrêt: Ctrl+C\n")
        
        try:
            while True:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] 🔄 Vérification...")
                
                current_slots = self.check_available_slots()
                
                if current_slots:
                    print(f"✅ {len(current_slots)} créneau(x) trouvé(s)")
                    
                    new_slots = [s for s in current_slots if s not in self.previous_slots]
                    
                    if new_slots:
                        print(f"\n{'🎉'*20}")
                        print(f"🆕 {len(new_slots)} NOUVEAU(X) CRÉNEAU(X)!")
                        print(f"{'🎉'*20}")
                        for slot in new_slots:
                            print(f"   📅 {slot}")
                        print(f"{'🎉'*20}\n")
                    
                    self.previous_slots = current_slots
                else:
                    print("⏸️  Aucun créneau disponible")
                
                print(f"💤 Pause de {check_interval_minutes} minutes...")
                time.sleep(check_interval_minutes * 60)
                
                # Rafraîchir la page
                self.page.reload()
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt de la surveillance")
        finally:
            self.close()
    
    def close(self):
        """Fermer le navigateur"""
        if self.browser:
            print("🚪 Fermeture du navigateur...")
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def main():
    load_dotenv()
    
    username = os.getenv('PDC_USERNAME')
    password = os.getenv('PDC_PASSWORD')
    
    if not username or not password:
        print("❌ PDC_USERNAME et PDC_PASSWORD requis dans .env")
        return
    
    print("\n" + "="*70)
    print("🚗 BOT SURVEILLANCE - PLAYWRIGHT + 2CAPTCHA")
    print("="*70)
    print("🎭 Playwright = Anti-détection + Bypass Cloudflare")
    print("🤖 2Captcha = Résolution automatique CAPTCHA (optionnel)")
    print("="*70)
    
    # Config proxy (optionnel)
    proxy_config = None
    if os.getenv('PROXY_HOST'):
        proxy_config = {
            'host': os.getenv('PROXY_HOST'),
            'port': os.getenv('PROXY_PORT'),
            'username': os.getenv('PROXY_USERNAME'),
            'password': os.getenv('PROXY_PASSWORD')
        }
        print(f"🌐 Proxy: {proxy_config['host']}")
    else:
        print("ℹ️  Pas de proxy configuré")
    
    # Config 2Captcha (optionnel)
    twocaptcha_key = os.getenv('TWOCAPTCHA_API_KEY')
    if twocaptcha_key:
        print(f"🤖 2Captcha: Configuré")
    else:
        print("ℹ️  2Captcha non configuré (résolution manuelle)")
    
    print("="*70 + "\n")
    
    bot = PermisScraplingBot(
        twocaptcha_api_key=twocaptcha_key,
        proxy_config=proxy_config
    )
    
    if not bot.setup_browser():
        return
    
    # Test de bypass (optionnel)
    print("\n📋 Voulez-vous tester le bypass Cloudflare d'abord?")
    test_choice = input("   Taper 'o' pour oui, Entrée pour passer: ").lower()
    if test_choice == 'o':
        bot.test_bypass()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
    
    try:
        # Connexion
        if not bot.login(username, password):
            print("\n❌ Échec de la connexion")
            return
        
        print("\n✅ Connecté avec succès!\n")
        input("⏸️  Appuyez sur Entrée pour continuer...")
        
        # Navigation
        if bot.navigate_to_reservations():
            print("\n✅ Navigation réussie!")
            input("⏸️  Appuyez sur Entrée pour démarrer la surveillance...")
            bot.monitor_loop(check_interval_minutes=5)
        else:
            print("\n⚠️  Navigation automatique échouée")
            print("📝 Naviguez manuellement vers la page des réservations")
            input("⏸️  Appuyez sur Entrée une fois sur la bonne page...")
            bot.monitor_loop(check_interval_minutes=5)
        
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du programme")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bot.close()

if __name__ == "__main__":
    main()
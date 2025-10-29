"""
Bot hybride: Connexion SANS proxy, puis surveillance AVEC proxy
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from datetime import datetime
import random
import os
from dotenv import load_dotenv

class HybridPermisBot:
    def __init__(self, proxy_config=None):
        self.driver = None
        self.previous_slots = []
        self.proxy_config = proxy_config
        self.proxy_enabled = False
        
    def setup_driver(self, use_proxy=False):
        """Configure le driver avec ou sans proxy"""
        try:
            if use_proxy and self.proxy_config:
                print("🌐 Initialisation avec PROXY...")
            else:
                print("🔍 Initialisation SANS PROXY (connexion)...")
            
            options = uc.ChromeOptions()
            
            # Proxy uniquement si demandé
            if use_proxy and self.proxy_config:
                proxy_string = f"{self.proxy_config['host']}:{self.proxy_config['port']}"
                
                if self.proxy_config.get('username') and self.proxy_config.get('password'):
                    # Proxy avec authentification
                    proxy_auth = f"{self.proxy_config['username']}:{self.proxy_config['password']}@{proxy_string}"
                    options.add_argument(f'--proxy-server=http://{proxy_auth}')
                else:
                    # Proxy sans authentification
                    options.add_argument(f'--proxy-server=http://{proxy_string}')
                
                print(f"   Proxy: {proxy_string}")
                self.proxy_enabled = True
            
            # Options anti-détection
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            # User agent français
            options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Créer le driver
            self.driver = uc.Chrome(options=options, version_main=None)
            
            print("✅ Navigateur prêt")
            return True
            
        except Exception as e:
            print(f"❌ Erreur d'initialisation: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def login(self, username, password):
        """Connexion SANS proxy pour éviter le blocage Turnstile"""
        try:
            print("\n🔐 CONNEXION (sans proxy)")
            print("="*70)
            
            auth_url = "https://auth.permisdeconduire.gouv.fr/realms/formation/protocol/openid-connect/auth?client_id=formation_1&redirect_uri=https%3A%2F%2Fpro.permisdeconduire.gouv.fr%2Foidc-callback&response_type=code&scope=openid"
            
            print(f"📡 Chargement de la page de login...")
            self.driver.get(auth_url)
            
            # Attente pour éviter la détection
            wait_time = 5 + random.uniform(1, 3)
            print(f"⏳ Attente {wait_time:.1f}s...")
            time.sleep(wait_time)
            
            # Sauvegarder
            with open('page_login.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Page sauvegardée: page_login.html")
            
            # Attendre le formulaire
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                print("✅ Formulaire détecté")
            except TimeoutException:
                print("❌ Timeout: formulaire absent")
                return False
            
            # Remplir avec comportement humain
            print("✍️  Remplissage du formulaire...")
            
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            
            # Username
            username_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            for char in username:
                username_field.send_keys(char)
                time.sleep(random.uniform(0.08, 0.15))
            print("   ✓ Username")
            
            # Password
            time.sleep(random.uniform(0.3, 0.7))
            password_field.click()
            time.sleep(random.uniform(0.5, 1.0))
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.08, 0.15))
            print("   ✓ Password")
            
            time.sleep(2)
            
            # Gestion du Turnstile
            print("\n🔒 Gestion du Cloudflare Turnstile")
            print("-"*70)
            print("⏳ Attente de la validation automatique...")
            print("   (Sans proxy, ça devrait être rapide - 5-30s)")
            
            submit_button = self.driver.find_element(By.ID, "kc-login")
            
            max_wait = 90
            elapsed = 0
            check_interval = 2
            
            while elapsed < max_wait:
                is_disabled = submit_button.get_attribute("disabled")
                
                if not is_disabled:
                    print(f"\n✅ Turnstile validé automatiquement après {elapsed}s!")
                    break
                
                time.sleep(check_interval)
                elapsed += check_interval
                
                if elapsed % 10 == 0:
                    print(f"   ⏳ {elapsed}s écoulées...")
            
            if submit_button.get_attribute("disabled"):
                print(f"\n⚠️  Turnstile non validé après {max_wait}s")
                print("👉 Résolvez manuellement dans le navigateur")
                print("   (Cliquez sur la checkbox si visible)")
                input("   ⏸️  Appuyez sur Entrée une fois validé...")
            
            print("-"*70)
            
            # Soumettre
            time.sleep(random.uniform(1, 2))
            print("\n🔄 Soumission du formulaire...")
            
            submit_button = self.driver.find_element(By.ID, "kc-login")
            
            # Vérifier une dernière fois que le bouton n'est pas désactivé
            if submit_button.get_attribute("disabled"):
                print("   ⚠️  Le bouton est toujours désactivé!")
                print("   Le Turnstile n'a peut-être pas été correctement validé")
                print("👉 Vérifiez dans le navigateur")
                input("   ⏸️  Appuyez sur Entrée une fois que vous voyez le bouton actif...")
            
            try:
                # Méthode 1: Clic normal
                submit_button.click()
                print("   ✅ Clic effectué")
            except Exception as e:
                print(f"   ⚠️  Erreur de clic: {e}")
                print("   Tentative avec JavaScript...")
                try:
                    self.driver.execute_script("document.getElementById('kc-login').click()")
                    print("   ✅ Clic JavaScript effectué")
                except Exception as e2:
                    print(f"   ❌ Échec JavaScript: {e2}")
                    return False
            
            # Attendre redirection (plus long)
            print("   ⏳ Attente de la redirection...")
            time.sleep(8)
            
            # Vérifier résultat
            current_url = self.driver.current_url
            print(f"   URL après soumission: {current_url}")
            
            # Sauvegarder la page pour debug
            with open('page_apres_submit.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("   📄 Page sauvegardée: page_apres_submit.html")
            
            # Vérifier si on est toujours sur la page de login
            if "auth." in current_url or "login-actions" in current_url:
                print("\n⚠️  Toujours sur la page d'authentification")
                
                # Chercher les erreurs
                errors_found = False
                try:
                    error = self.driver.find_element(By.CLASS_NAME, "kc-feedback-text")
                    print(f"   ❌ Erreur: {error.text}")
                    errors_found = True
                except:
                    pass
                
                try:
                    error = self.driver.find_element(By.ID, "kc-error-message")
                    print(f"   ❌ Erreur: {error.text}")
                    errors_found = True
                except:
                    pass
                
                if not errors_found:
                    print("   ℹ️  Aucun message d'erreur trouvé")
                    print("   💡 Causes possibles:")
                    print("      • Identifiants incorrects")
                    print("      • Le formulaire n'a pas été soumis correctement")
                    print("      • Cloudflare a bloqué la requête")
                
                with open('erreur_login.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print("   📄 Erreur sauvegardée: erreur_login.html")
                
                # Laisser une chance de voir ce qui se passe
                print("\n👉 Le navigateur reste ouvert pour inspection")
                print("   Vérifiez si vous voyez un message d'erreur")
                input("   ⏸️  Appuyez sur Entrée pour continuer ou Ctrl+C pour quitter...")
                
                return False
            
            print(f"✅ CONNEXION RÉUSSIE!")
            print(f"   URL: {current_url}")
            print("="*70)
            
            # Sauvegarder
            with open('page_apres_connexion.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def switch_to_proxy(self):
        """Redémarre le navigateur avec le proxy après connexion"""
        try:
            if not self.proxy_config:
                print("ℹ️  Pas de proxy configuré, continuation sans proxy")
                return True
            
            print("\n🔄 ACTIVATION DU PROXY")
            print("="*70)
            print("⚠️  Le navigateur va redémarrer avec le proxy")
            print("   Vos cookies de session seront conservés")
            
            # Sauvegarder les cookies
            print("📦 Sauvegarde des cookies...")
            cookies = self.driver.get_cookies()
            current_url = self.driver.current_url
            
            # Fermer le navigateur actuel
            print("🚪 Fermeture du navigateur...")
            self.driver.quit()
            time.sleep(2)
            
            # Redémarrer avec proxy
            print("🌐 Redémarrage avec PROXY...")
            if not self.setup_driver(use_proxy=True):
                print("❌ Échec du redémarrage avec proxy")
                return False
            
            # Aller sur le site
            print("📡 Navigation vers le site...")
            self.driver.get("https://pro.permisdeconduire.gouv.fr/")
            time.sleep(3)
            
            # Restaurer les cookies
            print("🔧 Restauration des cookies...")
            for cookie in cookies:
                try:
                    # Nettoyer les attributs incompatibles
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"   ⚠️  Cookie ignoré: {e}")
            
            # Retourner à l'URL
            print(f"🔄 Retour à: {current_url}")
            self.driver.get(current_url)
            time.sleep(3)
            
            # Vérifier qu'on est toujours connecté
            if "auth." in self.driver.current_url:
                print("❌ Session expirée, reconnexion nécessaire")
                return False
            
            print("✅ Proxy activé avec succès!")
            print("   Vous êtes maintenant en surveillance avec proxy")
            print("="*70)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors du switch proxy: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def navigate_to_reservations(self):
        """Navigation vers les réservations"""
        try:
            print("\n🔍 Navigation vers les réservations...")
            
            # Sauvegarder
            with open('page_dashboard.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Dashboard sauvegardé")
            
            # Chercher les liens
            possible_texts = [
                "Réservation", "Réserver", "Créneaux", 
                "Disponibilités", "Rendez-vous", "Planning", "Examens"
            ]
            
            for text in possible_texts:
                try:
                    link = self.driver.find_element(By.PARTIAL_LINK_TEXT, text)
                    print(f"✅ Lien '{text}' trouvé")
                    link.click()
                    time.sleep(3)
                    return True
                except NoSuchElementException:
                    continue
            
            print("⚠️  Navigation automatique échouée")
            return False
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def check_available_slots(self):
        """Vérifier les créneaux disponibles"""
        try:
            slots = []
            
            # Sélecteurs possibles
            selectors = [
                (By.CLASS_NAME, "slot-disponible"),
                (By.CLASS_NAME, "disponible"),
                (By.CSS_SELECTOR, "[data-disponible='true']"),
                (By.CSS_SELECTOR, ".slot.available"),
                (By.XPATH, "//*[contains(@class, 'slot') and contains(@class, 'dispo')]")
            ]
            
            slot_elements = []
            for by, selector in selectors:
                try:
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        slot_elements = elements
                        break
                except:
                    continue
            
            for elem in slot_elements[:10]:
                try:
                    text = elem.text
                    if text:
                        slots.append(text)
                except:
                    continue
            
            return slots
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []
    
    def monitor_loop(self, check_interval_minutes=5):
        """Boucle de surveillance continue"""
        proxy_status = "AVEC PROXY" if self.proxy_enabled else "SANS PROXY"
        
        print(f"\n{'='*70}")
        print(f"🔍 SURVEILLANCE ACTIVE ({proxy_status})")
        print(f"{'='*70}")
        print(f"⏰ Intervalle: {check_interval_minutes} minutes")
        print(f"⌨️  Arrêt: Ctrl+C")
        print(f"{'='*70}\n")
        
        try:
            while True:
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                print(f"\n[{timestamp}] 🔄 Vérification...")
                
                current_slots = self.check_available_slots()
                
                if current_slots:
                    print(f"✅ {len(current_slots)} créneau(x) disponible(s)")
                    
                    # Détecter nouveaux créneaux
                    new_slots = [s for s in current_slots if s not in self.previous_slots]
                    
                    if new_slots:
                        print(f"\n{'🎉'*20}")
                        print(f"🆕 {len(new_slots)} NOUVEAU(X) CRÉNEAU(X) !")
                        print(f"{'🎉'*20}")
                        for slot in new_slots:
                            print(f"   📅 {slot}")
                        print(f"{'🎉'*20}\n")
                        
                        # TODO: Notifications (email, Telegram, etc.)
                    
                    self.previous_slots = current_slots
                else:
                    print("⏸️  Aucun créneau disponible")
                
                print(f"💤 Pause de {check_interval_minutes} minutes...")
                time.sleep(check_interval_minutes * 60)
                
                # Rafraîchir
                self.driver.refresh()
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt de la surveillance")
        finally:
            self.close()
    
    def close(self):
        """Fermer le navigateur"""
        if self.driver:
            print("🚪 Fermeture du navigateur...")
            self.driver.quit()

def main():
    load_dotenv()
    
    username = os.getenv('PDC_USERNAME')
    password = os.getenv('PDC_PASSWORD')
    
    if not username or not password:
        print("❌ PDC_USERNAME et PDC_PASSWORD requis dans .env")
        return
    
    print("\n" + "="*70)
    print("🚗 BOT HYBRIDE - CONNEXION SANS PROXY, SURVEILLANCE AVEC PROXY")
    print("="*70)
    print("💡 Stratégie:")
    print("   1. Connexion SANS proxy (bypass facile du Turnstile)")
    print("   2. Switch vers proxy APRÈS connexion (pour surveillance)")
    print("="*70)
    
    # Configuration proxy (optionnel)
    proxy_config = None
    if os.getenv('PROXY_HOST'):
        proxy_config = {
            'host': os.getenv('PROXY_HOST'),
            'port': os.getenv('PROXY_PORT'),
            'username': os.getenv('PROXY_USERNAME'),
            'password': os.getenv('PROXY_PASSWORD')
        }
        print(f"🌐 Proxy configuré: {proxy_config['host']}")
        print("   (Sera activé APRÈS la connexion)")
    else:
        print("ℹ️  Pas de proxy configuré")
        print("   Surveillance se fera depuis votre IP")
    
    print("="*70 + "\n")
    
    bot = HybridPermisBot(proxy_config=proxy_config)
    
    # ÉTAPE 1: Connexion SANS proxy
    print("\n📍 ÉTAPE 1: CONNEXION SANS PROXY")
    print("-"*70)
    
    if not bot.setup_driver(use_proxy=False):
        return
    
    try:
        if not bot.login(username, password):
            print("\n❌ Échec de la connexion")
            return
        
        print("\n✅ Connexion réussie!\n")
        
        # ÉTAPE 2: Switch vers proxy (si configuré)
        if proxy_config:
            print("\n📍 ÉTAPE 2: ACTIVATION DU PROXY")
            print("-"*70)
            input("⏸️  Appuyez sur Entrée pour activer le proxy...")
            
            if not bot.switch_to_proxy():
                print("\n⚠️  Échec du switch proxy")
                print("   Continuation sans proxy? (o/n)")
                choice = input("   > ").lower()
                if choice != 'o':
                    return
        
        # ÉTAPE 3: Navigation
        print("\n📍 ÉTAPE 3: NAVIGATION VERS RÉSERVATIONS")
        print("-"*70)
        input("⏸️  Appuyez sur Entrée pour continuer...")
        
        if not bot.navigate_to_reservations():
            print("\n⚠️  Navigation automatique échouée")
            print("📝 Naviguez manuellement vers la page des réservations")
            input("⏸️  Appuyez sur Entrée une fois sur la bonne page...")
        
        # ÉTAPE 4: Surveillance
        print("\n📍 ÉTAPE 4: SURVEILLANCE")
        print("-"*70)
        input("⏸️  Appuyez sur Entrée pour démarrer la surveillance...")
        
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
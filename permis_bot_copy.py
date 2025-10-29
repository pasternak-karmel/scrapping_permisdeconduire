"""
Bot de surveillance avec undetected-chromedriver pour bypasser la détection Cloudflare
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from datetime import datetime

class PermisBot:
    def __init__(self):
        self.driver = None
        self.previous_slots = []
        
    def setup_driver(self):
        """Configure undetected-chromedriver"""
        try:
            print("🔍 Initialisation du navigateur anti-détection...")
            
            options = uc.ChromeOptions()
            
            # Options pour ressembler à un vrai utilisateur
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            # Utiliser un user agent réaliste
            options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Créer le driver
            self.driver = uc.Chrome(options=options, version_main=None)
            
            print("✅ Navigateur prêt (mode furtif activé)")
            return True
            
        except Exception as e:
            print(f"❌ Erreur d'initialisation: {e}")
            print("\n💡 Solution:")
            print("   pip install undetected-chromedriver")
            return False
    
    def login(self, username, password):
        """Connexion avec contournement de la détection"""
        try:
            print("🔐 Connexion...")
            
            # URL directe vers le formulaire de login
            auth_url = "https://auth.permisdeconduire.gouv.fr/realms/formation/protocol/openid-connect/auth?client_id=formation_1&redirect_uri=https%3A%2F%2Fpro.permisdeconduire.gouv.fr%2Foidc-callback&response_type=code&scope=openid"
            
            print(f"📡 Chargement de la page de login...")
            self.driver.get(auth_url)
            
            # Attendre plus longtemps pour éviter la détection
            print("⏳ Attente du chargement complet (contournement Cloudflare)...")
            time.sleep(5)
            
            # Sauvegarder la page
            with open('page_login_undetected.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Page sauvegardée dans page_login_undetected.html")
            
            # Attendre le formulaire
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                print("✅ Formulaire détecté")
            except TimeoutException:
                print("❌ Timeout: le formulaire n'apparaît pas")
                print(f"   URL actuelle: {self.driver.current_url}")
                return False
            
            # Remplir les champs avec des délais naturels
            print("✍️  Remplissage du formulaire...")
            
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            
            # Simuler une saisie humaine (avec délais)
            username_field.click()
            time.sleep(0.5)
            for char in username:
                username_field.send_keys(char)
                time.sleep(0.1)  # Délai entre chaque caractère
            print("   ✓ Username saisi")
            
            time.sleep(0.3)
            password_field.click()
            time.sleep(0.5)
            for char in password:
                password_field.send_keys(char)
                time.sleep(0.1)
            print("   ✓ Password saisi")
            
            # Attendre le CAPTCHA
            print("\n" + "="*70)
            print("🔒 CAPTCHA - ACTION REQUISE")
            print("="*70)
            print("👉 Résolvez le CAPTCHA dans le navigateur")
            print("   (Le mode furtif devrait permettre la validation)")
            print("⏳ Attente (max 3 minutes)...")
            print("="*70 + "\n")
            
            # Attendre que le bouton soit activé
            submit_button = self.driver.find_element(By.ID, "kc-login")
            
            try:
                # Attendre jusqu'à 3 minutes
                WebDriverWait(self.driver, 180).until(
                    lambda driver: not submit_button.get_attribute("disabled")
                )
                print("✅ CAPTCHA résolu!")
                
            except TimeoutException:
                print("❌ Timeout: CAPTCHA non résolu en 3 minutes")
                return False
            
            # Petit délai avant de soumettre (comportement humain)
            time.sleep(1)
            
            # Soumettre le formulaire
            print("🔄 Soumission du formulaire...")
            submit_button.click()
            
            # Attendre la redirection
            time.sleep(5)
            
            # Vérifier le résultat
            current_url = self.driver.current_url
            
            if "auth." in current_url or "login-actions" in current_url:
                # Erreur de connexion
                try:
                    error = self.driver.find_element(By.CLASS_NAME, "kc-feedback-text")
                    print(f"❌ Erreur: {error.text}")
                except:
                    try:
                        error = self.driver.find_element(By.ID, "kc-error-message")
                        print(f"❌ Erreur: {error.text}")
                    except:
                        print("❌ Échec (toujours sur page login)")
                
                with open('erreur_login.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print("📄 Page d'erreur sauvegardée")
                return False
            
            print(f"✅ CONNEXION RÉUSSIE!")
            print(f"   URL: {current_url}")
            
            # Sauvegarder la page après connexion
            with open('page_apres_connexion.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Page connectée sauvegardée")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def navigate_to_reservations(self):
        """Navigation vers la page des réservations"""
        try:
            print("\n🔍 Navigation vers les réservations...")
            
            # Sauvegarder la page actuelle
            with open('page_dashboard.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Page dashboard sauvegardée")
            
            # Chercher les liens possibles
            possible_texts = [
                "Réservation", "Réserver", "Créneaux", 
                "Disponibilités", "Rendez-vous", "Planning",
                "Examens"
            ]
            
            found = False
            for text in possible_texts:
                try:
                    link = self.driver.find_element(By.PARTIAL_LINK_TEXT, text)
                    print(f"✅ Lien '{text}' trouvé")
                    link.click()
                    time.sleep(2)
                    found = True
                    break
                except NoSuchElementException:
                    continue
            
            if not found:
                print("⚠️  Aucun lien trouvé automatiquement")
                print("   Analysez page_dashboard.html pour trouver le bon lien")
                return False
            
            # Sauvegarder la page des réservations
            with open('page_reservations.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 Page réservations sauvegardée")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def check_available_slots(self):
        """Vérifier les créneaux disponibles"""
        try:
            print("🔍 Recherche de créneaux...")
            
            slots = []
            
            # Essayer plusieurs sélecteurs
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
                        print(f"   ✓ Trouvé avec: {selector}")
                        break
                except:
                    continue
            
            print(f"   {len(slot_elements)} élément(s) trouvé(s)")
            
            if not slot_elements:
                print("   ⚠️  Aucun créneau trouvé avec les sélecteurs par défaut")
                print("   📊 Analysez page_reservations.html pour adapter les sélecteurs")
                return []
            
            # Parser les créneaux
            for i, element in enumerate(slot_elements[:10]):  # Limiter à 10 pour l'affichage
                try:
                    text = element.text
                    if text:
                        print(f"   • Créneau {i+1}: {text[:100]}")
                        slots.append(text)
                except:
                    continue
            
            return slots
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []
    
    def monitor_loop(self, check_interval_minutes=5):
        """Boucle de surveillance continue"""
        print(f"\n{'='*70}")
        print(f"🔍 SURVEILLANCE ACTIVE")
        print(f"{'='*70}")
        print(f"⏰ Intervalle: {check_interval_minutes} minutes")
        print(f"⌨️  Arrêt: Ctrl+C")
        print(f"{'='*70}\n")
        
        try:
            while True:
                try:
                    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    print(f"\n[{timestamp}] 🔄 Vérification...")
                    
                    current_slots = self.check_available_slots()
                    
                    if current_slots:
                        print(f"✅ {len(current_slots)} créneau(x) disponible(s)")
                        
                        # Détecter les nouveaux
                        new_slots = [s for s in current_slots if s not in self.previous_slots]
                        
                        if new_slots:
                            print(f"\n{'🎉'*20}")
                            print(f"🆕 {len(new_slots)} NOUVEAU(X) CRÉNEAU(X) !")
                            print(f"{'🎉'*20}")
                            for slot in new_slots:
                                print(f"   📅 {slot}")
                            print(f"{'🎉'*20}\n")
                            
                            # TODO: Ajouter ici l'envoi de notifications
                            # (email, Telegram, webhook, etc.)
                        
                        self.previous_slots = current_slots
                    else:
                        print("⏸️  Aucun créneau disponible")
                    
                    print(f"💤 Pause de {check_interval_minutes} minutes...")
                    time.sleep(check_interval_minutes * 60)
                    
                    # Rafraîchir la page périodiquement
                    self.driver.refresh()
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"❌ Erreur dans la boucle: {e}")
                    print("⏰ Nouvelle tentative dans 1 minute...")
                    time.sleep(60)
                    
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
    """Point d'entrée principal"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    username = os.getenv('PDC_USERNAME')
    password = os.getenv('PDC_PASSWORD')
    
    if not username or not password:
        print("❌ PDC_USERNAME et PDC_PASSWORD requis dans .env")
        return
    
    print("\n" + "="*70)
    print("🚗 BOT DE SURVEILLANCE PERMIS - MODE FURTIF")
    print("="*70)
    print("📦 Utilise undetected-chromedriver pour contourner la détection")
    print("="*70 + "\n")
    
    bot = PermisBot()
    
    if not bot.setup_driver():
        return
    
    try:
        # Connexion
        if not bot.login(username, password):
            print("\n❌ Échec de la connexion")
            return
        
        print("\n✅ CONNEXION RÉUSSIE!\n")
        
        # Navigation
        print("="*70)
        print("📍 ÉTAPE SUIVANTE: Navigation")
        print("="*70)
        input("⏸️  Appuyez sur Entrée pour naviguer vers les réservations...")
        
        if not bot.navigate_to_reservations():
            print("\n⚠️  Navigation automatique échouée")
            print("📝 Actions manuelles requises:")
            print("   1. Dans le navigateur, naviguez vers la page des réservations")
            print("   2. Revenez ici et appuyez sur Entrée")
            input("\n⏸️  Entrée quand vous êtes sur la page des réservations...")
        
        # Surveillance
        print("\n" + "="*70)
        print("📊 ÉTAPE FINALE: Surveillance")
        print("="*70)
        print("Une fois lancée, la surveillance tournera en continu")
        input("⏸️  Entrée pour démarrer (ou Ctrl+C pour quitter)...")
        
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

#rm -rf ~/.wdm

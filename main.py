import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urlencode
import time
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

@dataclass
class ExamSlot:
    """Représente un créneau d'examen disponible"""
    date: str
    hour: str
    location: str
    exam_type: str  # 'code' ou 'conduite'
    places_available: int
    
    def __str__(self):
        return f"{self.date} à {self.hour} - {self.location} ({self.places_available} places)"

class PermisNotificationBot:
    """
    Bot de notification pour les places d'examen du permis de conduire
    """
    
    def __init__(self, base_url, auth_url, client_id, redirect_uri):
        self.base_url = base_url
        self.auth_url = auth_url
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.session = requests.Session()
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session.headers.update(self.headers)
        
        self.access_token = None
        self.refresh_token = None
        self.previous_slots = []
        self.notification_history = []
    
    def login_oidc(self, username, password):
        """Connexion via OpenID Connect / Keycloak avec parsing amélioré"""
        try:
            print("🔐 Connexion en cours...")
            
            # ÉTAPE 1: Initier le flow OAuth
            initial_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'scope': 'openid email profile',
                'state': self._generate_state(),
                'nonce': self._generate_nonce()
            }
            
            auth_init_url = f"{self.auth_url}?{urlencode(initial_params)}"
            print(f"📡 Requête vers: {self.auth_url}")
            
            response = self.session.get(auth_init_url, allow_redirects=True)
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                return False
            
            print(f"✅ Page de connexion récupérée")
            
            # ÉTAPE 2: Parser le formulaire
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Chercher le formulaire de login
            form = soup.find('form', {'id': 'kc-form-login'})
            if not form:
                form = soup.find('form')  # Fallback sur le premier formulaire
            
            if not form:
                print("❌ Formulaire de connexion non trouvé")
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print("   📄 Page sauvegardée dans debug_page.html")
                return False
            
            print("✅ Formulaire trouvé")
            
            # Extraire l'action du formulaire
            form_action = form.get('action')
            if not form_action.startswith('http'):
                parsed = urlparse(response.url)
                form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
            
            print(f"📤 Soumission vers: {form_action}")
            
            # Construire les données du formulaire
            login_data = {}
            
            # IMPORTANT: Récupérer TOUS les inputs (pas seulement les hidden)
            for input_field in form.find_all('input'):
                name = input_field.get('name')
                if not name:
                    continue
                
                input_type = input_field.get('type', 'text').lower()
                value = input_field.get('value', '')
                
                # Ne pas écraser username/password
                if name == 'username':
                    login_data[name] = username
                elif name == 'password':
                    login_data[name] = password
                elif input_type in ['hidden', 'submit']:
                    login_data[name] = value
                    print(f"   📋 Ajout de {name} = {value[:50] if value else '(vide)'}")
            
            # S'assurer que username et password sont bien présents
            if 'username' not in login_data:
                login_data['username'] = username
            if 'password' not in login_data:
                login_data['password'] = password
            
            print(f"   ✅ Total: {len(login_data)} champ(s) dans le formulaire")
            
            # Soumettre le formulaire
            login_response = self.session.post(
                form_action, 
                data=login_data, 
                allow_redirects=False,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': response.url
                }
            )
            
            print(f"   📊 Status de la soumission: {login_response.status_code}")
            
            # Vérifier la redirection
            redirect_location = login_response.headers.get('Location')
            
            if not redirect_location:
                print("❌ Échec de connexion - Pas de redirection")
                print(f"   Status: {login_response.status_code}")
                
                # Chercher un message d'erreur
                if login_response.status_code in [200, 400]:
                    error_soup = BeautifulSoup(login_response.text, 'html.parser')
                    
                    # Essayer plusieurs sélecteurs d'erreur Keycloak
                    error_selectors = [
                        ('span', {'class': 'kc-feedback-text'}),
                        ('div', {'class': 'alert-error'}),
                        ('div', {'class': 'kc-feedback-text'}),
                        ('div', {'id': 'input-error'})
                    ]
                    
                    for tag, attrs in error_selectors:
                        error_msg = error_soup.find(tag, attrs)
                        if error_msg:
                            print(f"   ⚠️  Message: {error_msg.text.strip()}")
                            break
                    
                    # Sauvegarder pour debug
                    with open('debug_error.html', 'w', encoding='utf-8') as f:
                        f.write(login_response.text)
                    print("   📄 Réponse sauvegardée dans debug_error.html")
                
                return False
            
            print(f"✅ Authentification réussie")
            print(f"🔄 Redirection vers: {redirect_location[:100]}...")
            
            # Suivre la redirection pour obtenir le code
            final_response = self.session.get(redirect_location, allow_redirects=True)
            parsed_url = urlparse(final_response.url)
            query_params = parse_qs(parsed_url.query)
            auth_code = query_params.get('code', [None])[0]
            
            if not auth_code:
                print("❌ Code d'autorisation non obtenu")
                print(f"   URL finale: {final_response.url}")
                return False
            
            print(f"✅ Code d'autorisation obtenu")
            
            # Échanger le code contre des tokens
            token_url = self.auth_url.replace('/auth', '/token')
            print(f"🔄 Échange de code vers: {token_url}")
            
            token_data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id
            }
            
            token_response = self.session.post(token_url, data=token_data)
            
            if token_response.status_code == 200:
                tokens = token_response.json()
                self.access_token = tokens.get('access_token')
                self.refresh_token = tokens.get('refresh_token')
                
                if self.access_token:
                    self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
                    print("✅ Connecté avec succès!")
                    return True
                else:
                    print("❌ Token non reçu dans la réponse")
                    return False
            else:
                print(f"❌ Erreur lors de l'échange de token: {token_response.status_code}")
                try:
                    print(f"   Réponse: {token_response.json()}")
                except:
                    print(f"   Réponse: {token_response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _generate_state(self):
        import secrets
        return secrets.token_urlsafe(32)
    
    def _generate_nonce(self):
        import secrets
        return secrets.token_urlsafe(32)
    
    def check_available_slots(self) -> List[ExamSlot]:
        """
        Vérifie les créneaux disponibles
        À adapter selon la structure HTML réelle du site
        """
        try:
            # URL à adapter selon le site réel
            slots_url = f"{self.base_url}/reservations/disponibilites"
            response = self.session.get(slots_url)
            
            if response.status_code != 200:
                print(f"⚠️ Erreur {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            slots = []
            
            # EXEMPLE de parsing - À ADAPTER selon la structure réelle
            # Chercher les créneaux disponibles
            slot_elements = soup.find_all('div', class_='slot-disponible')
            
            for element in slot_elements:
                try:
                    date = element.find('span', class_='date').text.strip()
                    hour = element.find('span', class_='heure').text.strip()
                    location = element.find('span', class_='lieu').text.strip()
                    exam_type = element.get('data-type', 'conduite')
                    
                    # Nombre de places
                    places_text = element.find('span', class_='places').text
                    places = int(places_text.split()[0])
                    
                    slot = ExamSlot(
                        date=date,
                        hour=hour,
                        location=location,
                        exam_type=exam_type,
                        places_available=places
                    )
                    slots.append(slot)
                    
                except Exception as e:
                    continue
            
            return slots
            
        except Exception as e:
            print(f"❌ Erreur lors de la vérification: {e}")
            return []
    
    def detect_new_slots(self, current_slots: List[ExamSlot]) -> List[ExamSlot]:
        """Détecte les nouveaux créneaux par rapport à la dernière vérification"""
        new_slots = []
        
        for slot in current_slots:
            is_new = True
            for prev_slot in self.previous_slots:
                if (slot.date == prev_slot.date and 
                    slot.hour == prev_slot.hour and 
                    slot.location == prev_slot.location):
                    is_new = False
                    break
            
            if is_new:
                new_slots.append(slot)
        
        self.previous_slots = current_slots
        return new_slots
    
    def send_email_notification(self, slots: List[ExamSlot], 
                                smtp_server: str, smtp_port: int,
                                sender_email: str, sender_password: str,
                                recipient_email: str):
        """Envoie une notification par email"""
        try:
            message = MIMEMultipart()
            message['From'] = sender_email
            message['To'] = recipient_email
            message['Subject'] = f"🚗 {len(slots)} nouveau(x) créneau(x) disponible(s) !"
            
            body = "Nouveaux créneaux d'examen disponibles :\n\n"
            for slot in slots:
                body += f"• {slot}\n"
            
            body += f"\n📅 Vérification effectuée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
            
            message.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(message)
            
            print(f"📧 Email envoyé à {recipient_email}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur email: {e}")
            return False
    
    def send_telegram_notification(self, slots: List[ExamSlot], 
                                   bot_token: str, chat_id: str):
        """Envoie une notification via Telegram"""
        try:
            message = f"🚗 *{len(slots)} nouveau(x) créneau(x) disponible(s) !*\n\n"
            
            for slot in slots:
                message += f"📅 {slot.date} à {slot.hour}\n"
                message += f"📍 {slot.location}\n"
                message += f"👥 {slot.places_available} place(s)\n\n"
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                print("📱 Notification Telegram envoyée")
                return True
            else:
                print(f"❌ Erreur Telegram: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur Telegram: {e}")
            return False
    
    def send_webhook_notification(self, slots: List[ExamSlot], webhook_url: str):
        """Envoie une notification vers un webhook (Discord, Slack, etc.)"""
        try:
            payload = {
                'content': f"🚗 {len(slots)} nouveau(x) créneau(x) disponible(s) !",
                'embeds': [{
                    'title': 'Créneaux d\'examen disponibles',
                    'color': 3066993,
                    'fields': [
                        {
                            'name': f"{slot.date} à {slot.hour}",
                            'value': f"{slot.location} - {slot.places_available} place(s)",
                            'inline': False
                        } for slot in slots
                    ],
                    'timestamp': datetime.now().isoformat()
                }]
            }
            
            response = requests.post(webhook_url, json=payload)
            
            if response.status_code in [200, 204]:
                print("🔔 Webhook notification envoyée")
                return True
            else:
                print(f"❌ Erreur webhook: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur webhook: {e}")
            return False
    
    def save_slots_to_file(self, slots: List[ExamSlot], filename='slots_history.json'):
        """Sauvegarde l'historique des créneaux"""
        try:
            history = {
                'timestamp': datetime.now().isoformat(),
                'total_slots': len(slots),
                'slots': [
                    {
                        'date': slot.date,
                        'hour': slot.hour,
                        'location': slot.location,
                        'exam_type': slot.exam_type,
                        'places_available': slot.places_available
                    } for slot in slots
                ]
            }
            
            # Charger l'historique existant
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    all_history = json.load(f)
            except FileNotFoundError:
                all_history = []
            
            all_history.append(history)
            
            # Garder seulement les 100 dernières vérifications
            all_history = all_history[-100:]
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_history, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Historique sauvegardé dans {filename}")
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
    
    def monitor_loop(self, check_interval_minutes=5, 
                    notification_config=None):
        """
        Boucle de surveillance continue
        
        Args:
            check_interval_minutes: Intervalle entre chaque vérification
            notification_config: Dict avec config notifications
        """
        print(f"🔍 Démarrage de la surveillance (vérification toutes les {check_interval_minutes} min)")
        
        while True:
            try:
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                print(f"\n[{timestamp}] Vérification en cours...")
                
                # Vérifier les créneaux
                current_slots = self.check_available_slots()
                print(f"📊 {len(current_slots)} créneau(x) disponible(s)")
                
                # Détecter les nouveaux
                new_slots = self.detect_new_slots(current_slots)
                
                if new_slots:
                    print(f"🆕 {len(new_slots)} nouveau(x) créneau(x) détecté(s) !")
                    
                    # Afficher les détails
                    for slot in new_slots:
                        print(f"  • {slot}")
                    
                    # Envoyer notifications si configurées
                    if notification_config:
                        if notification_config.get('email'):
                            self.send_email_notification(
                                new_slots,
                                **notification_config['email']
                            )
                        
                        if notification_config.get('telegram'):
                            self.send_telegram_notification(
                                new_slots,
                                **notification_config['telegram']
                            )
                        
                        if notification_config.get('webhook'):
                            self.send_webhook_notification(
                                new_slots,
                                notification_config['webhook']['url']
                            )
                    
                    # Sauvegarder
                    self.save_slots_to_file(new_slots)
                else:
                    print("⏸️ Aucun nouveau créneau")
                
                # Attendre avant la prochaine vérification
                print(f"⏰ Prochaine vérification dans {check_interval_minutes} minutes...")
                time.sleep(check_interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\n\n👋 Arrêt de la surveillance")
                break
            except Exception as e:
                print(f"❌ Erreur: {e}")
                print("⏰ Nouvelle tentative dans 1 minute...")
                time.sleep(60)


# ============== CONFIGURATION ET LANCEMENT ==============

def main():
    """Configuration et lancement du bot"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # Configuration du scraper
    bot = PermisNotificationBot(
        base_url="https://pro.permisdeconduire.gouv.fr",
        auth_url="https://auth.permisdeconduire.gouv.fr/realms/formation/protocol/openid-connect/auth",
        client_id="formation_1",
        redirect_uri="https://pro.permisdeconduire.gouv.fr/oidc-callback"
    )
    
    # Connexion
    username = os.getenv('PDC_USERNAME')
    password = os.getenv('PDC_PASSWORD')
    
    if not bot.login_oidc(username, password):
        print("❌ Impossible de se connecter")
        return
    
    # Configuration des notifications
    notification_config = {
        # Email (optionnel)
        'email': {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': os.getenv('EMAIL_SENDER'),
            'sender_password': os.getenv('EMAIL_PASSWORD'),
            'recipient_email': os.getenv('EMAIL_RECIPIENT')
        } if os.getenv('EMAIL_SENDER') else None,
        
        # Telegram (optionnel)
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        } if os.getenv('TELEGRAM_BOT_TOKEN') else None,
        
        # Webhook Discord/Slack (optionnel)
        'webhook': {
            'url': os.getenv('WEBHOOK_URL')
        } if os.getenv('WEBHOOK_URL') else None
    }
    
    # Lancer la surveillance
    bot.monitor_loop(
        check_interval_minutes=5,  # Vérifier toutes les 5 minutes
        notification_config=notification_config
    )

if __name__ == "__main__":
    main()